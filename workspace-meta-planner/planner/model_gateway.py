"""Unified model gateway for all LLM calls in the SDD Planner.

Routes calls through LiteLLM proxy, handles retries, degraded mode fallback,
and logs costs. See spec.md §4 (Model Selection + Degraded Mode).
"""

import json
import logging
import random
import subprocess
import time
from typing import Any, Callable, Optional

from planner import cost_tracker

logger = logging.getLogger(__name__)

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

        Uses streaming to handle WSL >30s timeout issue (LL-INFRA-001).
        """
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        try:
            result = subprocess.run(
                [
                    "curl", "-s", "--max-time", "300",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps(payload),
                    f"{self.base_url}/v1/chat/completions",
                ],
                capture_output=True,
                text=True,
                timeout=350,
            )
        except subprocess.TimeoutExpired:
            raise ProviderError(f"Timeout calling {model} via LiteLLM")

        if result.returncode != 0:
            raise ProviderError(f"curl failed (rc={result.returncode}): {result.stderr}")

        return self._parse_streaming_response(result.stdout)

    def _parse_streaming_response(self, raw: str) -> dict:
        """Parse SSE streaming response from LiteLLM."""
        content_parts = []
        tokens_in = 0
        tokens_out = 0

        for line in raw.strip().split("\n"):
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if "content" in delta:
                    content_parts.append(delta["content"])
                usage = chunk.get("usage")
                if usage:
                    tokens_in = usage.get("prompt_tokens", tokens_in)
                    tokens_out = usage.get("completion_tokens", tokens_out)
            except json.JSONDecodeError:
                continue

        return {
            "content": "".join(content_parts),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
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
