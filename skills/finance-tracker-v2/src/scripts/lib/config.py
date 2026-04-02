"""Unified config access for Finance Tracker v2.

Single source of truth: tracker_config.json
All writes are atomic (write .tmp then os.replace).
Setup state tracked separately in setup_state.json for resume.
"""

import json
import os
from pathlib import Path

from .errors import FinanceError, ErrorCode

# ── Paths ──────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent.parent.parent          # src/
SKILL_DIR = SRC_DIR                                               # src/ is the skill root in v2
SCRIPTS_DIR = SRC_DIR / "scripts"
INSTALL_DIR = SRC_DIR / "install"
SCHEMAS_DIR = INSTALL_DIR / "schemas"


def get_base_dir() -> Path:
    """Runtime data directory: ~/.openclaw/products/finance-tracker/"""
    base = Path.home() / ".openclaw" / "products" / "finance-tracker"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_config_dir() -> Path:
    d = get_base_dir() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Atomic JSON I/O ───────────────────────────────────

def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    """Atomic write: write to .tmp then rename."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


# ── Tracker config ────────────────────────────────────

_CONFIG_CACHE: dict | None = None


def _load_tracker_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    path = get_config_dir() / "tracker_config.json"
    if path.exists():
        try:
            _CONFIG_CACHE = load_json(path)
            return _CONFIG_CACHE
        except (json.JSONDecodeError, OSError):
            raise FinanceError(ErrorCode.CONFIG_CORRUPT,
                               f"Config corrupt: {path}")
    return _defaults()


def _defaults() -> dict:
    return {
        "user": {
            "name": "User", "language": "en", "currency": "USD",
            "spreadsheet_name": "My Finance Tracker",
            "cards": ["Card 1", "Cash"], "setup_complete": False,
        },
        "categories": {"Other": {"monthly": 50, "threshold": 0.8}},
        "balance": {
            "available": 0, "pay_schedule": "biweekly",
            "pay_dates": [1, 15], "expected_paycheck": 0,
        },
        "tax": {"enabled": False, "tax_categories": [], "ask_rules": [], "never_ask": []},
        "payments": [],
        "savings": [],
    }


def save_tracker_config(config: dict) -> None:
    global _CONFIG_CACHE
    save_json(get_config_dir() / "tracker_config.json", config)
    _CONFIG_CACHE = config


def invalidate_config_cache() -> None:
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


# ── Accessor functions ────────────────────────────────

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


# ── Setup state (separate file for resume) ────────────

def load_setup_state() -> dict:
    path = get_config_dir() / "setup_state.json"
    if path.exists():
        try:
            return load_json(path)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_setup_state(state: dict) -> None:
    save_json(get_config_dir() / "setup_state.json", state)


def clear_setup_state() -> None:
    path = get_config_dir() / "setup_state.json"
    if path.exists():
        path.unlink()


# ── User auto-detection (cherry-picked from v1) ──────

def read_user_md() -> dict:
    """Read name and language from workspace USER.md."""
    user_md = Path.home() / ".openclaw" / "workspace" / "USER.md"
    result = {"name": None, "language": None}
    if not user_md.exists():
        return result
    text = user_md.read_text()
    for line in text.splitlines():
        low = line.lower().strip()
        if low.startswith("- **name:**") or low.startswith("**name:**"):
            val = line.split(":**", 1)[-1].strip()
            val = val.split("(")[0].strip()
            if val:
                result["name"] = val.split()[0]
        if "spanish" in low and "english" in low:
            result["language"] = "es"
        elif "spanish" in low or "español" in low:
            result["language"] = "es"
        elif "english" in low:
            result["language"] = "en"
    return result
