"""Paths, constants, and config loaders for the finance tracker."""

import json
from pathlib import Path

# Paths — use relative + $HOME, never hardcoded username
SKILL_DIR = Path(__file__).resolve().parent.parent.parent  # finance-tracker/
CONFIG_DIR = SKILL_DIR / "config"
SCRIPTS_DIR = SKILL_DIR / "scripts"
# AI model config
LITELLM_URL = "http://127.0.0.1:4000/v1/chat/completions"
LITELLM_KEY = "sk-litellm-local"
PARSE_MODEL = "chatgpt-gpt54"
CLASSIFY_MODEL = "chatgpt-gpt54"
ANALYSIS_MODEL = "chatgpt-gpt54-thinking"

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
