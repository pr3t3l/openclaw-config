"""AI parser for Finance Tracker v2.

3-level cascade for AI backend detection:
  Level 1 — llm-task: Returns prompt as request dict (agent processes via llm-task tool).
  Level 2 — LiteLLM proxy: http://127.0.0.1:4000 (discovers models dynamically).
  Level 3 — Direct API: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY from env.

Uses subprocess+curl (NOT Python requests — fails in WSL for long calls).
"""

import json
import os
import re
import subprocess
from pathlib import Path

from . import config as C


# ── Backend detection ─────────────────────────────────

def _check_litellm_health() -> bool:
    """Check if LiteLLM proxy is running at localhost:4000."""
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "3", "http://127.0.0.1:4000/health"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and r.stdout.strip().startswith("{")
    except Exception:
        return False


def _discover_litellm_models() -> list[str]:
    """GET /models from LiteLLM and return model IDs."""
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "5", "http://127.0.0.1:4000/v1/models"],
            capture_output=True, text=True, timeout=7,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return []
        data = json.loads(r.stdout)
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception:
        return []


def _pick_cheapest_model(models: list[str]) -> str:
    """Pick the smallest/cheapest model from a list for parsing tasks."""
    # Prefer small/mini models for parsing (cheap + fast)
    preferences = [
        "gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1-nano",
        "claude-3-5-haiku", "claude-haiku", "claude-3-haiku",
        "gemini-2.0-flash", "gemini-1.5-flash",
        "gpt-3.5-turbo",
    ]
    for pref in preferences:
        for m in models:
            if pref in m.lower():
                return m
    # Fallback: shortest model name (heuristic: shorter = simpler)
    return min(models, key=len) if models else ""


def detect_ai_backend() -> dict:
    """Detect available AI backend. Returns {backend, model, url, key}.

    Level 2 — LiteLLM proxy (fast, local)
    Level 3 — Direct API (env vars)
    Level 1 — llm-task (handled outside Python by SKILL.md)
    """
    # Level 2: LiteLLM proxy
    if _check_litellm_health():
        models = _discover_litellm_models()
        if models:
            model = _pick_cheapest_model(models)
            return {
                "backend": "litellm",
                "model": model,
                "url": "http://127.0.0.1:4000/v1/chat/completions",
                "key": "sk-litellm",  # LiteLLM default key
            }

    # Level 3: Direct API from env vars
    # Check openclaw.json env section first
    oc_path = Path.home() / ".openclaw" / "openclaw.json"
    env_keys = {}
    if oc_path.exists():
        try:
            oc = json.loads(oc_path.read_text())
            oc_env = oc.get("env", {})
            for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
                if oc_env.get(k):
                    env_keys[k] = oc_env[k]

            # Also check providers
            providers = oc.get("models", {}).get("providers", {})
            for name, prov in providers.items():
                if prov.get("baseUrl") and prov.get("apiKey"):
                    base = prov["baseUrl"].rstrip("/")
                    if "/chat/completions" not in base:
                        if not base.endswith("/v1"):
                            base += "/v1"
                        base += "/chat/completions"
                    models = [m.get("id", "") for m in prov.get("models", []) if m.get("id")]
                    model = _pick_cheapest_model(models) if models else "auto"
                    return {
                        "backend": "provider",
                        "model": model,
                        "url": base,
                        "key": prov["apiKey"],
                    }
        except Exception:
            pass

    # System env vars
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        if k not in env_keys:
            val = os.environ.get(k)
            if val:
                env_keys[k] = val

    if env_keys.get("OPENAI_API_KEY"):
        return {
            "backend": "openai",
            "model": "gpt-4o-mini",
            "url": "https://api.openai.com/v1/chat/completions",
            "key": env_keys["OPENAI_API_KEY"],
        }
    if env_keys.get("ANTHROPIC_API_KEY"):
        return {
            "backend": "anthropic",
            "model": "claude-3-5-haiku-20251022",
            "url": "https://api.anthropic.com/v1/messages",
            "key": env_keys["ANTHROPIC_API_KEY"],
        }
    if env_keys.get("GEMINI_API_KEY"):
        return {
            "backend": "gemini",
            "model": "gemini-2.0-flash",
            "url": "https://generativelanguage.googleapis.com/v1beta/chat/completions",
            "key": env_keys["GEMINI_API_KEY"],
        }

    return {"backend": "none", "model": "", "url": "", "key": ""}


# Lazy-initialized backend config
_BACKEND: dict | None = None


def _get_backend() -> dict:
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = detect_ai_backend()
    return _BACKEND


# ── Core AI call via subprocess+curl ──────────────────

def ai_call(payload: dict, timeout: int = 60) -> dict | None:
    """Make an AI API call via curl. Returns parsed response or None."""
    backend = _get_backend()
    if backend["backend"] == "none":
        return None

    url = backend["url"]
    key = backend["key"]

    # Anthropic uses different headers/format
    if backend["backend"] == "anthropic":
        return _anthropic_call(payload, url, key, timeout)

    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), url,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {key}",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except (subprocess.TimeoutExpired, Exception):
        return None
    if result.returncode != 0 or not result.stdout or not result.stdout.strip():
        return None
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if "error" in resp or "choices" not in resp:
        return None
    return resp


def _anthropic_call(payload: dict, url: str, key: str, timeout: int) -> dict | None:
    """Anthropic Messages API has a different format."""
    messages = payload.get("messages", [])
    system_msg = ""
    user_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            user_messages.append(m)

    anthropic_payload = {
        "model": payload.get("model", "claude-3-5-haiku-20251022"),
        "max_tokens": 2048,
        "messages": user_messages,
    }
    if system_msg:
        anthropic_payload["system"] = system_msg

    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), url,
             "-H", "Content-Type: application/json",
             "-H", f"x-api-key: {key}",
             "-H", "anthropic-version: 2023-06-01",
             "-d", json.dumps(anthropic_payload)],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except (subprocess.TimeoutExpired, Exception):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    # Convert Anthropic format to OpenAI-compatible
    if "content" in resp and isinstance(resp["content"], list):
        text = resp["content"][0].get("text", "")
        return {"choices": [{"message": {"content": text}}]}
    return None


def ai_extract_json(payload: dict, timeout: int = 60) -> dict | list | None:
    """Make AI call, extract JSON from response text."""
    resp = ai_call(payload, timeout)
    if not resp:
        return None
    text = resp["choices"][0]["message"]["content"]
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        text = json_match.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _get_model() -> str:
    return _get_backend().get("model", "auto")


# ── Level 1: llm-task request mode ────────────────────

def build_llm_request(system: str, user: str) -> dict:
    """Build an llm-task request dict for the agent to process.

    The SKILL.md instructs the agent to call llm-task with this payload.
    Returns: {"llm_request": True, "system": ..., "user": ..., "response_format": "json"}
    """
    return {
        "llm_request": True,
        "system": system,
        "user": user,
        "response_format": "json",
    }


def process_llm_response(response_text: str) -> dict | list | None:
    """Process the response from an llm-task call."""
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text)
    if json_match:
        response_text = json_match.group(1)
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        return None


# ── Transaction parser ────────────────────────────────

def parse_transaction(text: str, lang: str = "en",
                      categories: list[str] | None = None,
                      cards: list[str] | None = None) -> dict | None:
    """Parse free-form expense/income text into a transaction dict."""
    cats = categories or C.get_categories()
    accts = cards or C.get_cards()

    system = "You are a financial transaction parser. Output only valid JSON."
    user = f"""Parse this expense or income into JSON:

Input ({lang}): {text}

Valid categories: {json.dumps(cats)}
Valid accounts/cards: {json.dumps(accts)}

Return JSON with these fields:
- "amount": number (positive)
- "merchant": string
- "category": one of the valid categories
- "card": one of the valid accounts (best guess from context)
- "date": "YYYY-MM-DD" (today if not specified)
- "type": "expense" or "income"
- "confidence": 0.0-1.0
- "tax_deductible": true, false, or null (null if uncertain)
- "needs_confirmation": boolean

Respond ONLY with valid JSON, no explanation."""

    backend = _get_backend()
    if backend["backend"] == "none":
        return build_llm_request(system, user)

    payload = {
        "model": _get_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
    }
    result = ai_extract_json(payload)
    if isinstance(result, dict):
        result.setdefault("confidence", 0.8)
        result.setdefault("needs_confirmation", True)
        result.setdefault("type", "expense")
    return result


def parse_receipt_lines(text: str, lang: str = "en",
                        categories: list[str] | None = None) -> dict | None:
    """Parse a receipt into line items with categories."""
    cats = categories or C.get_categories()

    system = "You are a receipt parser. Output only valid JSON."
    user = f"""Parse this receipt into line items.

Input ({lang}): {text}

Valid categories: {json.dumps(cats)}

Return JSON with:
- "merchant": string
- "date": "YYYY-MM-DD"
- "receipt_id": "merchant-YYYYMMDD-totalcents"
- "total": number
- "transactions": array of objects, each with:
  - "amount": number
  - "item": string (item name)
  - "category": one of valid categories
  - "tax_deductible": true, false, or null
  - "tax_category": string or "none"

Respond ONLY with valid JSON, no explanation."""

    backend = _get_backend()
    if backend["backend"] == "none":
        return build_llm_request(system, user)

    payload = {
        "model": _get_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
    }
    return ai_extract_json(payload)


# ── Helper ────────────────────────────────────────────

def _load_schema_text(name: str) -> str:
    path = C.SCHEMAS_DIR / f"{name}.v1.json"
    if path.exists():
        return path.read_text()
    return "{}"
