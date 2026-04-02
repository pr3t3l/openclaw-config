"""001_initial — Baseline migration for v2.0.0.

Sets up the initial config structure. Idempotent.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from lib import config as C


def migrate():
    """Ensure baseline config fields exist."""
    cfg = C._load_tracker_config()

    # Ensure all required top-level keys
    cfg.setdefault("user", {})
    cfg["user"].setdefault("name", "User")
    cfg["user"].setdefault("language", "en")
    cfg["user"].setdefault("currency", "USD")
    cfg["user"].setdefault("cards", ["Card 1", "Cash"])
    cfg["user"].setdefault("setup_complete", False)

    cfg.setdefault("categories", {"Other": {"monthly": 50, "type": "variable", "threshold": 0.8}})
    cfg.setdefault("balance", {"available": 0, "pay_schedule": "biweekly", "pay_dates": [1, 15], "expected_paycheck": 0})
    cfg.setdefault("tax", {"enabled": False, "rulepacks": [], "deductible_categories": []})
    cfg.setdefault("payments", [])
    cfg.setdefault("savings", [])
    cfg.setdefault("income", [])
    cfg.setdefault("debts", [])
    cfg.setdefault("telemetry", {"enabled": False})
    cfg.setdefault("onboarding", {"mission_1": False, "mission_2": False, "mission_3": False, "all_complete": False})
    cfg.setdefault("migrations_applied", [])

    C.save_tracker_config(cfg)
