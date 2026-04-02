"""Paths, constants, and config loaders for the finance tracker."""

import json
import os
from pathlib import Path

# Paths — use relative + $HOME, never hardcoded username
SKILL_DIR = Path(__file__).resolve().parent.parent.parent  # finance-tracker/
CONFIG_DIR = SKILL_DIR / "config"
SCRIPTS_DIR = SKILL_DIR / "scripts"
WORKSPACE_DIR = SKILL_DIR.parent.parent  # ~/.openclaw/workspace/


def read_user_md() -> dict:
    """Read name and language from workspace USER.md (set by OpenClaw)."""
    user_md = WORKSPACE_DIR / "USER.md"
    result = {"name": None, "language": None}
    if not user_md.exists():
        return result
    text = user_md.read_text()
    for line in text.splitlines():
        low = line.lower().strip()
        if low.startswith("- **name:**") or low.startswith("**name:**"):
            # Extract: "- **Name:** First Last (Nick)" → "First"
            val = line.split(":**", 1)[-1].strip()
            # Take first name only, remove parenthetical
            val = val.split("(")[0].strip()
            if val:
                result["name"] = val.split()[0]  # first name
        if "spanish" in low and "english" in low:
            result["language"] = "es"  # bilingual → prefer Spanish
        elif "spanish" in low or "español" in low:
            result["language"] = "es"
        elif "english" in low:
            result["language"] = "en"
    return result


# ═══════════════════════════════════════════
# AI MODEL AUTO-DETECTION
# Priority: openclaw.json custom provider → openclaw.json env → system env → defaults
# Supports: LiteLLM proxy, OpenAI direct, any OpenAI-compatible endpoint
# ═══════════════════════════════════════════

def _detect_ai_config() -> dict:
    """Auto-detect AI config from OpenClaw's openclaw.json and environment."""
    result = {}
    oc_path = Path.home() / ".openclaw" / "openclaw.json"

    if oc_path.exists():
        try:
            oc = json.loads(oc_path.read_text())
            # --- Try 1: Custom provider with baseUrl (LiteLLM, Ollama, etc.) ---
            providers = oc.get("models", {}).get("providers", {})
            for name, prov in providers.items():
                if prov.get("baseUrl") and prov.get("apiKey"):
                    base = prov["baseUrl"].rstrip("/")
                    # Normalize: add /v1/chat/completions if not already a full path
                    if "/chat/completions" not in base:
                        if not base.endswith("/v1"):
                            base += "/v1"
                        base += "/chat/completions"
                    result["url"] = base
                    result["key"] = prov["apiKey"]
                    # Pick models from this provider's catalog
                    models = prov.get("models", [])
                    if models:
                        _pick_models(result, models)
                    break  # Use first provider with baseUrl

            # --- Try 2: env section in openclaw.json ---
            oc_env = oc.get("env", {})
            if not result.get("key"):
                if oc_env.get("OPENAI_API_KEY"):
                    result["url"] = "https://api.openai.com/v1/chat/completions"
                    result["key"] = oc_env["OPENAI_API_KEY"]
                    result.setdefault("parse_model", "gpt-4o-mini")
                    result.setdefault("classify_model", "gpt-4o-mini")
                    result.setdefault("analysis_model", "gpt-4o")

            # --- Try 3: Infer from agents.defaults.model ---
            if not result.get("key"):
                default_model = (oc.get("agents", {}).get("defaults", {})
                                 .get("model", {}).get("primary", ""))
                if "/" in default_model:
                    provider, model_id = default_model.split("/", 1)
                    if provider == "openai":
                        result.setdefault("parse_model", "gpt-4o-mini")
                        result.setdefault("classify_model", "gpt-4o-mini")
                        result.setdefault("analysis_model", model_id)
                    elif provider == "anthropic":
                        # Anthropic via OpenAI-compatible proxy is handled by LiteLLM above
                        # For direct Anthropic users, they need a proxy or LiteLLM
                        result.setdefault("parse_model", model_id)
                        result.setdefault("classify_model", model_id)
                        result.setdefault("analysis_model", model_id)
        except Exception:
            pass

    # --- Try 4: System environment variables ---
    if not result.get("key"):
        for env_key, api_url in [
            ("OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions"),
            ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/chat/completions"),
        ]:
            val = os.environ.get(env_key)
            if val:
                result["url"] = api_url
                result["key"] = val
                result.setdefault("parse_model", "gpt-4o-mini")
                result.setdefault("classify_model", "gpt-4o-mini")
                result.setdefault("analysis_model", "gpt-4o")
                break

    return result


def _pick_models(result: dict, models: list[dict]):
    """Pick parse/classify (cheap) and analysis (reasoning) models from a catalog."""
    ids = [m.get("id", "") for m in models]

    # Parse/classify: prefer cheapest non-reasoning
    for candidate in ["gpt5-mini", "gpt-4o-mini", "gpt41-mini"]:
        if candidate in ids:
            result["parse_model"] = candidate
            result["classify_model"] = candidate
            break
    if "parse_model" not in result:
        non_reasoning = [m for m in models if not m.get("reasoning")]
        if non_reasoning:
            result["parse_model"] = non_reasoning[0]["id"]
            result["classify_model"] = non_reasoning[0]["id"]
        elif ids:
            result["parse_model"] = ids[0]
            result["classify_model"] = ids[0]

    # Analysis: prefer reasoning model
    for candidate in ["gpt52-medium", "gpt52-thinking", "gpt-4o", "gpt52-none"]:
        if candidate in ids:
            result["analysis_model"] = candidate
            break
    if "analysis_model" not in result:
        reasoning = [m for m in models if m.get("reasoning")]
        if reasoning:
            result["analysis_model"] = reasoning[0]["id"]
        else:
            result["analysis_model"] = result.get("parse_model", ids[0] if ids else "gpt-4o-mini")


_AI_CONFIG = _detect_ai_config()
LITELLM_URL = _AI_CONFIG.get("url", "http://127.0.0.1:4000/v1/chat/completions")
LITELLM_KEY = _AI_CONFIG.get("key", "YOUR_API_KEY")
PARSE_MODEL = _AI_CONFIG.get("parse_model", "gpt-4o-mini")
CLASSIFY_MODEL = _AI_CONFIG.get("classify_model", "gpt-4o-mini")
ANALYSIS_MODEL = _AI_CONFIG.get("analysis_model", "gpt-4o")

def ai_call(payload: dict, timeout: int = 60, _caller: str = "") -> dict | None:
    """Make an AI API call via curl. Returns parsed response or None on error.

    _caller: optional tag for telemetry (e.g., "parse-text", "tax-profile").
    """
    import subprocess
    import time as _time
    model = payload.get("model", "unknown")
    t0 = _time.time()
    status = "success"
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {LITELLM_KEY}",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=timeout + 5
        )
    except subprocess.TimeoutExpired:
        status = "timeout"
        _track_ai(model, t0, status, _caller)
        return None
    except Exception:
        status = "error"
        _track_ai(model, t0, status, _caller)
        return None
    if result.returncode != 0 or not result.stdout or not result.stdout.strip():
        status = "empty"
        _track_ai(model, t0, status, _caller)
        return None
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        status = "invalid_json"
        _track_ai(model, t0, status, _caller)
        return None
    if "error" in resp or "choices" not in resp:
        status = "api_error"
        _track_ai(model, t0, status, _caller)
        return None
    _track_ai(model, t0, status, _caller)
    return resp


def _track_ai(model: str, t0: float, status: str, caller: str):
    """Fire-and-forget AI call telemetry."""
    import time as _time
    try:
        from . import telemetry as T
        T.track_ai_call(caller or "unknown", model, int((_time.time() - t0) * 1000), status)
    except Exception:
        pass


def ai_extract_text(payload: dict, timeout: int = 60, _caller: str = "") -> str | None:
    """Make an AI call and return the text content, or None on error."""
    import re
    resp = ai_call(payload, timeout, _caller=_caller)
    if not resp:
        return None
    text = resp["choices"][0]["message"]["content"]
    # Strip markdown fences if present
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        text = json_match.group(1)
    return text.strip()


# ═══════════════════════════════════════════
# SINGLE CONFIG FILE: tracker_config.json
# ═══════════════════════════════════════════

_CONFIG_CACHE = None


def _load_tracker_config() -> dict:
    """Load the unified config or return defaults."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    path = CONFIG_DIR / "tracker_config.json"
    if path.exists():
        _CONFIG_CACHE = load_json(path)
        return _CONFIG_CACHE
    return {
        "user": {"name": "User", "language": "en", "currency": "USD",
                 "spreadsheet_name": "My Finance Tracker",
                 "cards": ["Card 1", "Cash"], "setup_complete": False},
        "categories": {"Other": {"monthly": 50, "threshold": 0.8}},
        "balance": {"available": 0, "pay_schedule": "biweekly", "pay_dates": [1, 15],
                     "expected_paycheck": 0},
        "tax": {"enabled": False, "tax_categories": [], "ask_rules": [], "never_ask": []},
        "payments": [],
        "savings": [],
    }


def save_tracker_config(config: dict):
    """Save tracker config and invalidate cache."""
    global _CONFIG_CACHE
    save_json(CONFIG_DIR / "tracker_config.json", config)
    _CONFIG_CACHE = config


def invalidate_config_cache():
    """Call after any config change."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


# Accessor functions
def get_spreadsheet_name() -> str:
    return _load_tracker_config()["user"]["spreadsheet_name"]


def get_owner_name() -> str:
    return _load_tracker_config()["user"]["name"]


def get_language() -> str:
    return _load_tracker_config()["user"].get("language", "en")


def get_currency() -> str:
    return _load_tracker_config()["user"].get("currency", "USD")


def get_cards() -> list[str]:
    return _load_tracker_config()["user"].get("cards", ["Card 1", "Cash"])


def get_categories() -> list[str]:
    return list(_load_tracker_config().get("categories", {}).keys())


def get_category_budgets() -> dict:
    return _load_tracker_config().get("categories", {})


def get_balance_info() -> dict:
    return _load_tracker_config().get("balance", {})


def get_payments() -> list[dict]:
    return _load_tracker_config().get("payments", [])


def get_savings() -> list[dict]:
    return _load_tracker_config().get("savings", [])


def get_tax_profile() -> dict:
    return _load_tracker_config().get("tax", {"enabled": False})


def is_setup_complete() -> bool:
    return _load_tracker_config()["user"].get("setup_complete", False)


# Sheets tabs — only DATA tabs that the bot writes to
TAB_TRANSACTIONS = "Transactions"
TAB_MONTHLY = "Monthly Summary"
TAB_RECONCILIATION = "Reconciliation_Log"
TAB_CASHFLOW = "Cashflow_Ledger"
TAB_DEBT = "Debt Tracker"


# JSON utility functions
def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_rules() -> list[dict]:
    rules_path = CONFIG_DIR / "rules.json"
    return load_json(rules_path) if rules_path.exists() else []


def save_rules(rules: list[dict]):
    save_json(CONFIG_DIR / "rules.json", rules)
