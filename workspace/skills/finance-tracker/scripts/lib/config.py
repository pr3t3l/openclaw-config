"""Paths, constants, and config loaders for the finance tracker."""

import json
from pathlib import Path

SKILL_DIR = Path("/home/robotin/.openclaw/workspace/skills/finance-tracker")
CONFIG_DIR = SKILL_DIR / "config"
SCRIPTS_DIR = SKILL_DIR / "scripts"
CREDENTIALS_DIR = Path("/home/robotin/.openclaw/credentials")

GOOGLE_CLIENT_FILE = CREDENTIALS_DIR / "google-client.json"
GOOGLE_TOKEN_FILE = CREDENTIALS_DIR / "finance-tracker-token.json"

SPREADSHEET_NAME = "Robotin Finance 2026"

LITELLM_URL = "http://127.0.0.1:4000/v1/chat/completions"
LITELLM_KEY = "sk-litellm-local"
PARSE_MODEL = "chatgpt-gpt54"
CLASSIFY_MODEL = "chatgpt-gpt54"
ANALYSIS_MODEL = "chatgpt-gpt54-thinking"

CATEGORIES = [
    "Groceries", "Restaurants", "Gas", "Shopping", "Entertainment",
    "Subscriptions_AI", "Subscriptions_Other", "Childcare", "Home",
    "Personal", "Travel", "Work_Tools", "Health", "Other",
    "Pets", "Debt_Interest", "Bank_Fees", "Refunds",
]

CARDS = ["Chase", "Discover", "Citi", "WellsFargo", "Cash"]

# Tab names in the spreadsheet
TAB_TRANSACTIONS = "Transactions"
TAB_BUDGET = "Budget"
TAB_PAYMENTS = "Payment Calendar"
TAB_MONTHLY = "Monthly Summary"
TAB_DEBT = "Debt Tracker"
TAB_RULES = "Rules"
TAB_RECONCILIATION = "Reconciliation_Log"
TAB_CASHFLOW = "Cashflow_Ledger"


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_rules() -> list[dict]:
    return load_json(CONFIG_DIR / "rules.json")


def save_rules(rules: list[dict]):
    save_json(CONFIG_DIR / "rules.json", rules)


def load_budgets() -> dict:
    return load_json(CONFIG_DIR / "budgets.json")


def load_payments() -> list[dict]:
    return load_json(CONFIG_DIR / "payments.json")


def load_savings() -> list[dict]:
    return load_json(CONFIG_DIR / "savings.json")
