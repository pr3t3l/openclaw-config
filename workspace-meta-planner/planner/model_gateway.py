"""Unified model gateway for all LLM calls in the SDD Planner.

Routes calls through LiteLLM proxy, handles retries, degraded mode fallback,
and logs costs. See spec.md §4 (Model Selection + Degraded Mode).
"""

import json
import logging
import os
import random
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional

from planner import cost_tracker

logger = logging.getLogger(__name__)

# Load model mapping config
_MAPPING_PATH = Path(__file__).parent / "config" / "model_mapping.json"
_mapping_cache: Optional[dict] = None


def _load_mapping() -> dict:
    global _mapping_cache
    if _mapping_cache is None:
        with open(_MAPPING_PATH) as f:
            _mapping_cache = json.load(f)
    return _mapping_cache


def resolve_litellm_name(spec_name: str) -> str:
    """Translate spec model name to LiteLLM registered name.

    E.g., 'claude-opus-4-6' → 'claude-opus46'
    """
    mapping = _load_mapping()
    return mapping["models"].get(spec_name, spec_name)


LITELLM_BASE_URL = "http://127.0.0.1:4000"

# Model mapping: role → (model, provider)
MODEL_ROLES: dict[str, dict[str, str]] = {
    "primary": {"model": "claude-opus-4-6", "provider": "anthropic"},
    "ideation_a": {"model": "gpt-5.4", "provider": "openai"},
    "ideation_b": {"model": "gemini-3.1-pro", "provider": "google"},
    "auditor_gpt": {"model": "gpt-5.4", "provider": "openai"},
    "auditor_gemini": {"model": "gemini-3.1-pro", "provider": "google"},
    "degraded_primary": {"model": "gpt-5.4", "provider": "openai"},
}

# Max retries per failure type
MAX_RETRIES = 2
RATE_LIMIT_MAX_RETRIES = 3


class DegradedModeError(Exception):
    """Raised when primary model is unreachable and degraded mode not approved."""
    pass


class ModelCallError(Exception):
    """Raised when a model call fails after all retries."""

    def __init__(self, model: str, error: str, retries: int) -> None:
        self.model = model
        self.error = error
        self.retries = retries
        super().__init__(f"Model {model} failed after {retries} retries: {error}")


class ModelGateway:
    """Unified interface for all LLM calls.

    Handles retries, degraded mode, cost tracking, and rate limiting.
    """

    def __init__(
        self,
        state: dict,
        litellm_base_url: str = LITELLM_BASE_URL,
        call_fn: Optional[Callable] = None,
    ) -> None:
        """
        Args:
            state: Planner state dict (for cost tracking).
            litellm_base_url: LiteLLM proxy URL.
            call_fn: Optional override for the actual API call (for testing).
                     Signature: call_fn(model, messages, max_tokens, temperature) -> dict
        """
        self.state = state
        self.base_url = litellm_base_url
        self._call_fn = call_fn or self._call_litellm
        self.degraded_mode = False
        self._provider_health: dict[str, bool] = {
            "anthropic": True,
            "openai": True,
            "google": True,
        }

    def call_model(
        self,
        role: str,
        prompt: str,
        context: Optional[str] = None,
        phase: str = "0",
        document: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict:
        """Make a model call with retries and cost tracking.

        Args:
            role: Agent role (used to select model if model/provider not specified).
            prompt: The user/system prompt.
            context: Optional context to include as system message.
            phase: Current phase (for cost tracking).
            document: Current document (for cost tracking).
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            provider: Override provider (optional).
            model: Override model (optional).

        Returns:
            Dict with: content, model, tokens_in, tokens_out, cost_usd, duration.

        Raises:
            ModelCallError: After all retries exhausted.
            DegradedModeError: If primary unreachable and degraded mode not approved.
        """
        if model is None or provider is None:
            resolved = self._resolve_model(role)
            model = model or resolved["model"]
            provider = provider or resolved["provider"]

        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                start = time.monotonic()
                result = self._call_fn(model, messages, max_tokens, temperature)
                duration = time.monotonic() - start

                tokens_in = result.get("tokens_in", 0)
                tokens_out = result.get("tokens_out", 0)
                content = result.get("content", "")

                record = cost_tracker.log_call(
                    self.state, model, tokens_in, tokens_out, duration, phase, document
                )

                return {
                    "content": content,
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": record["cost_usd"],
                    "duration": duration,
                }

            except RateLimitError as e:
                last_error = str(e)
                backoff = _jittered_backoff(attempt, base=5.0, max_delay=30.0)
                logger.warning(f"Rate limit hit for {model}, backing off {backoff:.1f}s")
                time.sleep(backoff)
                if attempt >= RATE_LIMIT_MAX_RETRIES:
                    raise ModelCallError(model, last_error, attempt + 1)

            except ProviderError as e:
                last_error = str(e)
                logger.warning(f"Provider error for {model} (attempt {attempt + 1}): {e}")
                if self._is_primary(role) and not self.degraded_mode:
                    self._provider_health[provider] = False
                    raise DegradedModeError(
                        f"Primary model ({model}) unreachable: {e}. "
                        "Approve degraded mode to continue with GPT-5.4."
                    )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Call failed for {model} (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(_jittered_backoff(attempt))

        raise ModelCallError(model, last_error or "Unknown error", MAX_RETRIES + 1)

    def enable_degraded_mode(self) -> None:
        """Switch primary to GPT-5.4 (human must approve first)."""
        self.degraded_mode = True
        logger.warning("DEGRADED MODE ENABLED: Primary switched to GPT-5.4")

    def disable_degraded_mode(self) -> None:
        """Restore primary to Claude Opus 4.6."""
        self.degraded_mode = False
        self._provider_health["anthropic"] = True
        logger.info("Degraded mode disabled: Primary restored to Claude Opus 4.6")

    def _resolve_model(self, role: str) -> dict[str, str]:
        """Resolve role to model+provider, respecting degraded mode."""
        if self._is_primary(role) and self.degraded_mode:
            return MODEL_ROLES["degraded_primary"]
        role_config = MODEL_ROLES.get(role)
        if role_config is None:
            return MODEL_ROLES["primary"]
        return role_config

    def _is_primary(self, role: str) -> bool:
        """Check if role uses the primary model."""
        return role in ("primary", "intake", "drafter", "finalizer", "triager")

    def _call_litellm(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        """Call LiteLLM proxy via streaming curl subprocess.

        Uses the exact pattern from litellm_stream.py:
        - Tempfile for payload (LL-INFRA-027: $(cat) fails >8KB)
        - --data-binary @file (not -d inline)
        - stream_options.include_usage for token counting
        - Bearer auth token
        - subprocess timeout > curl --max-time (LL-INFRA-005)

        See LL-INFRA-001: Python requests fails in WSL >30s.
        """
        mapping = _load_mapping()
        litellm_model = resolve_litellm_name(model)
        proxy_url = mapping.get("litellm_proxy", self.base_url)
        api_key = mapping.get("litellm_api_key", "")
        curl_max_time = mapping.get("curl_max_time", 300)
        subprocess_buffer = mapping.get("subprocess_buffer", 50)

        payload = {
            "model": litellm_model,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": messages,
        }

        payload_json = json.dumps(payload, ensure_ascii=True)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
            f.write(payload_json.encode("utf-8"))
            tmp_path = f.name

        subprocess_timeout = curl_max_time + subprocess_buffer

        try:
            cmd = [
                "curl", "-s", "-S", "--max-time", str(curl_max_time),
                "-H", "Content-Type: application/json",
            ]
            if api_key:
                cmd.extend(["-H", f"Authorization: Bearer {api_key}"])
            cmd.extend(["--data-binary", f"@{tmp_path}", f"{proxy_url}/v1/chat/completions"])

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=subprocess_timeout,
            )
        except subprocess.TimeoutExpired:
            raise ProviderError(f"Timeout calling {litellm_model} via LiteLLM")
        finally:
            os.unlink(tmp_path)

        if result.returncode != 0:
            raise ProviderError(f"curl failed (rc={result.returncode}): {result.stderr[:300]}")

        raw = result.stdout.strip()
        if not raw:
            raise ProviderError(f"Empty response from LiteLLM. stderr: {result.stderr[:300]}")

        # Check for non-streaming error response
        if raw.startswith("{"):
            try:
                response = json.loads(raw)
                if "error" in response:
                    err_msg = response["error"]
                    if isinstance(err_msg, dict):
                        err_msg = err_msg.get("message", str(err_msg))
                    raise ProviderError(f"LiteLLM error: {err_msg}")
            except json.JSONDecodeError:
                pass

        return self._parse_streaming_response(raw)

    def _parse_streaming_response(self, raw: str) -> dict:
        """Parse SSE streaming response from LiteLLM.

        Matches the exact parsing logic from litellm_stream.py.
        """
        content_parts = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0}

        for line in raw.split("\n"):
            line = line.strip()
            if not line or line == "data: [DONE]":
                continue
            if not line.startswith("data: "):
                continue

            try:
                chunk = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    content_parts.append(content)

            if "usage" in chunk:
                u = chunk["usage"]
                usage["prompt_tokens"] = u.get("prompt_tokens", usage["prompt_tokens"])
                usage["completion_tokens"] = u.get("completion_tokens", usage["completion_tokens"])

        full_content = "".join(content_parts)
        if not full_content:
            raise ProviderError("Streaming returned no content. Raw: " + raw[:500])

        return {
            "content": full_content,
            "tokens_in": usage["prompt_tokens"],
            "tokens_out": usage["completion_tokens"],
        }


class RateLimitError(Exception):
    """HTTP 429 rate limit."""
    pass


class ProviderError(Exception):
    """Provider-level error (5xx, timeout, auth)."""
    pass


def _jittered_backoff(attempt: int, base: float = 2.0, max_delay: float = 30.0) -> float:
    """Compute jittered exponential backoff delay."""
    delay = min(base * (2 ** attempt), max_delay)
    return delay * (0.5 + random.random() * 0.5)
