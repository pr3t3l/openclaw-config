"""AI parser for Finance Tracker v2.

Uses subprocess + curl to LiteLLM (NOT Python requests — fails in WSL for long calls).
Cherry-picked from v1 config.py ai_call pattern.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from . import config as C


# ── AI config auto-detection (cherry-picked from v1) ──

def _detect_ai_config() -> dict:
    """Auto-detect AI endpoint and model from openclaw.json or env."""
    result = {}
    oc_path = Path.home() / ".openclaw" / "openclaw.json"

    if oc_path.exists():
        try:
            oc = json.loads(oc_path.read_text())

            # Try 1: Custom provider with baseUrl
            providers = oc.get("models", {}).get("providers", {})
            for name, prov in providers.items():
                if prov.get("baseUrl") and prov.get("apiKey"):
                    base = prov["baseUrl"].rstrip("/")
                    if "/chat/completions" not in base:
                        if not base.endswith("/v1"):
                            base += "/v1"
                        base += "/chat/completions"
                    result["url"] = base
                    result["key"] = prov["apiKey"]
                    models = prov.get("models", [])
                    if models:
                        ids = [m.get("id", "") for m in models]
                        for candidate in ["gpt5-mini", "gpt-4o-mini", "gpt41-mini"]:
                            if candidate in ids:
                                result["model"] = candidate
                                break
                        if "model" not in result and ids:
                            result["model"] = ids[0]
                    break

            # Try 2: env section
            oc_env = oc.get("env", {})
            if not result.get("key") and oc_env.get("OPENAI_API_KEY"):
                result["url"] = "https://api.openai.com/v1/chat/completions"
                result["key"] = oc_env["OPENAI_API_KEY"]
                result.setdefault("model", "gpt-4o-mini")

        except Exception:
            pass

    # Try 3: System env
    if not result.get("key"):
        for env_key, api_url in [
            ("OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions"),
            ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/chat/completions"),
        ]:
            val = os.environ.get(env_key)
            if val:
                result["url"] = api_url
                result["key"] = val
                result.setdefault("model", "gpt-4o-mini")
                break

    return result


_AI = _detect_ai_config()
LITELLM_URL = _AI.get("url", "http://127.0.0.1:4000/v1/chat/completions")
LITELLM_KEY = _AI.get("key", "")
PARSE_MODEL = _AI.get("model", "gpt-4o-mini")


# ── Core AI call via subprocess+curl ──────────────────

def ai_call(payload: dict, timeout: int = 60) -> dict | None:
    """Make an AI API call via curl. Returns parsed response or None on error."""
    if not LITELLM_KEY:
        return None
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {LITELLM_KEY}",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=timeout + 5
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


def ai_extract_json(payload: dict, timeout: int = 60) -> dict | list | None:
    """Make AI call, extract JSON from response text."""
    resp = ai_call(payload, timeout)
    if not resp:
        return None
    text = resp["choices"][0]["message"]["content"]
    # Strip markdown fences if present
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        text = json_match.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


# ── Income parser ─────────────────────────────────────

def parse_income(text: str, lang: str = "en") -> dict | None:
    """Parse free-form income text into structured JSON."""
    schema = _load_schema_text("income")
    prompt = f"""Parse this income description into JSON matching this schema:
{schema}

source_type must be one of: salary, freelance, rental, business, other
frequency must be one of: weekly, biweekly, monthly, irregular
is_regular should be true for salary, false for freelance/rental/business/other
account_label is the bank account name. If not mentioned, use "Primary Checking".

Input ({lang}): {text}

Respond ONLY with valid JSON, no explanation."""

    payload = {
        "model": PARSE_MODEL,
        "messages": [
            {"role": "system", "content": "You are a financial data parser. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    result = ai_extract_json(payload)
    if isinstance(result, dict):
        # Ensure required fields
        result.setdefault("is_regular", result.get("source_type") == "salary")
        result.setdefault("account_label", "Primary Checking")
        result.setdefault("frequency", "monthly")
        result.setdefault("source_type", "other")
    return result


# ── Debt parser ───────────────────────────────────────

def parse_debt(text: str, lang: str = "en") -> dict | None:
    """Parse free-form debt text into structured JSON."""
    schema = _load_schema_text("debt")
    prompt = f"""Parse this debt description into JSON matching this schema:
{schema}

type should be one of: credit_card, personal_loan, auto_loan, mortgage, student_loan, other
If APR is not mentioned, use 0. If minimum payment is not mentioned, use 0.

Input ({lang}): {text}

Respond ONLY with valid JSON, no explanation."""

    payload = {
        "model": PARSE_MODEL,
        "messages": [
            {"role": "system", "content": "You are a financial data parser. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    result = ai_extract_json(payload)
    if isinstance(result, dict):
        result.setdefault("apr", 0)
        result.setdefault("minimum_payment", 0)
    return result


# ── Transaction parser ────────────────────────────────

def parse_transaction(text: str, lang: str = "en",
                      categories: list[str] | None = None,
                      cards: list[str] | None = None) -> dict | None:
    """Parse free-form expense/income text into a transaction dict."""
    cats = categories or C.get_categories()
    accts = cards or C.get_cards()

    prompt = f"""Parse this expense or income into JSON:

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

    payload = {
        "model": PARSE_MODEL,
        "messages": [
            {"role": "system", "content": "You are a financial transaction parser. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    result = ai_extract_json(payload)
    if isinstance(result, dict):
        result.setdefault("confidence", 0.8)
        result.setdefault("needs_confirmation", True)
        result.setdefault("type", "expense")
    return result


# ── Receipt line item parser ──────────────────────────

def parse_receipt_lines(text: str, lang: str = "en",
                        categories: list[str] | None = None) -> dict | None:
    """Parse a receipt into line items with categories."""
    cats = categories or C.get_categories()

    prompt = f"""Parse this receipt into line items.

Input ({lang}): {text}

Valid categories: {json.dumps(cats)}

Return JSON with:
- "merchant": string
- "date": "YYYY-MM-DD"
- "receipt_id": "merchant-YYYYMMDD-totalcents" (e.g. "walmart-20260402-8743")
- "total": number
- "transactions": array of objects, each with:
  - "amount": number
  - "item": string (item name)
  - "category": one of valid categories
  - "tax_deductible": true, false, or null
  - "tax_category": string or "none"

Respond ONLY with valid JSON, no explanation."""

    payload = {
        "model": PARSE_MODEL,
        "messages": [
            {"role": "system", "content": "You are a receipt parser. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    return ai_extract_json(payload)


# ── Helper ────────────────────────────────────────────

def _load_schema_text(name: str) -> str:
    """Load schema as text for embedding in prompts."""
    path = C.SCHEMAS_DIR / f"{name}.v1.json"
    if path.exists():
        return path.read_text()
    return "{}"
