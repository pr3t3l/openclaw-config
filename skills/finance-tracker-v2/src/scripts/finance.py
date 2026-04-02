#!/usr/bin/env python3
"""Finance Tracker v2 — CLI entry point.

Every command returns JSON to stdout. The LLM never controls flow.

Setup commands:
  python3 finance.py install-check
  python3 finance.py preflight
  python3 finance.py setup-next "<user_input>"
  python3 finance.py setup-status
  python3 finance.py setup-reset

Runtime commands:
  python3 finance.py add "$15 Uber"
  python3 finance.py add-photo "/path/to/receipt.jpg"
  python3 finance.py budget-status
  python3 finance.py safe-to-spend
  python3 finance.py transactions [N]
  python3 finance.py list-categories
  python3 finance.py add-category "name" budget type
  python3 finance.py remove-category "name"
  python3 finance.py list-rules
  python3 finance.py add-rule "pattern" category [confidence]
  python3 finance.py update-balance "account" amount
  python3 finance.py payment-check
  python3 finance.py ai-backend
  python3 finance.py onboarding-check "command"
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import config as C
from lib.errors import FinanceError, ErrorCode
from lib.state_machine import (
    SetupStateMachine, install_check, preflight, setup_status, check_onboarding,
)


def _out(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _err(e: FinanceError) -> None:
    print(json.dumps(e.to_dict(), indent=2, ensure_ascii=False))
    sys.exit(1)


def _require_setup():
    """Check setup is complete before runtime commands."""
    if not C.is_setup_complete():
        _err(FinanceError(ErrorCode.SETUP_INCOMPLETE,
                          'Setup not complete. Run: finance.py setup-next "start"'))


def _with_onboarding(command: str, result: dict) -> dict:
    """Append onboarding message if applicable."""
    ob = check_onboarding(command)
    if ob and ob.get("onboarding_message"):
        result["_onboarding"] = ob
    return result


# ── Setup commands ────────────────────────────────────

def cmd_install_check():
    _out(install_check())

def cmd_preflight():
    _out(preflight())

def cmd_setup_next(user_input: str, mode: str = "full"):
    try:
        sm = SetupStateMachine(mode=mode)
        result = sm.process(user_input)
        _out(result)
    except FinanceError as e:
        _err(e)

def cmd_setup_status():
    _out(setup_status())

def cmd_onboarding_check(command: str):
    result = check_onboarding(command)
    _out(result if result else {"onboarding_message": None})

def cmd_setup_reset():
    C.clear_setup_state()
    C.invalidate_config_cache()
    config_path = C.get_config_dir() / "tracker_config.json"
    if config_path.exists():
        cfg = C.load_json(config_path)
        if not cfg.get("user", {}).get("setup_complete", False):
            config_path.unlink()
    _out({"reset": True, "message": "Setup state cleared."})


# ── Runtime: add transaction ──────────────────────────

def cmd_add(text: str):
    _require_setup()
    from lib.parser import parse_text
    from lib.merchant_rules import save_merchant_rule, normalize_merchant

    tx = parse_text(text)

    # If llm_request, return it for the agent to process
    if tx.get("llm_request"):
        _out(tx)
        return

    # Auto-learn merchant rule for high-confidence single-category
    if (tx.get("confidence", 0) >= 0.8
            and tx.get("merchant")
            and tx.get("category")
            and tx.get("category") != "Other"
            and not tx.get("requires_line_items")):
        save_merchant_rule(
            tx["merchant"], tx["category"],
            confidence=tx.get("confidence", 0.85),
            created_by="auto",
        )

    # Implicit confirmation for high confidence
    if tx.get("confidence", 0) >= 0.9 and not tx.get("needs_confirmation"):
        tx["_implicit_confirm"] = True
        lang = C.get_language()
        if lang == "es":
            tx["_message"] = (f"Registrado: ${tx.get('amount', 0):.2f} → "
                              f"{tx.get('category', 'Other')} ({tx.get('merchant', '')}). "
                              f"Responde 'undo' para revertir.")
        else:
            tx["_message"] = (f"Added: ${tx.get('amount', 0):.2f} → "
                              f"{tx.get('category', 'Other')} ({tx.get('merchant', '')}). "
                              f"Reply 'undo' to revert.")

    _out(_with_onboarding("add", tx))


def cmd_add_photo(path: str):
    _require_setup()
    from lib.parser import parse_photo
    tx = parse_photo(path)
    if tx:
        _out(_with_onboarding("add-photo", tx))
    else:
        _out({"error": True, "message": "Failed to parse receipt photo."})


# ── Runtime: budget ───────────────────────────────────

def cmd_budget_status():
    _require_setup()
    from lib.budget import get_budget_status, format_budget_status
    status = get_budget_status()
    status["_formatted"] = format_budget_status(status)
    _out(_with_onboarding("budget-status", status))


# ── Runtime: cashflow ─────────────────────────────────

def cmd_safe_to_spend():
    _require_setup()
    from lib.cashflow import safe_to_spend, format_cashflow
    data = safe_to_spend()
    data["_formatted"] = format_cashflow(data)
    _out(_with_onboarding("cashflow", data))


# ── Runtime: transactions ─────────────────────────────

def cmd_transactions(count: int = 10):
    _require_setup()
    # TODO Phase 4: read from Sheets
    _out({"transactions": [], "count": 0, "message": "Sheets integration pending."})


# ── Runtime: categories ───────────────────────────────

def cmd_list_categories():
    _require_setup()
    budgets = C.get_category_budgets()
    categories = []
    for name, data in budgets.items():
        categories.append({
            "category": name,
            "monthly": data.get("monthly", 0),
            "type": data.get("type", "variable"),
            "threshold": data.get("threshold", 0.8),
        })
    _out({"categories": categories, "count": len(categories)})


def cmd_add_category(name: str, budget: float, btype: str = "variable"):
    _require_setup()
    config = C._load_tracker_config()
    if name in config.get("categories", {}):
        _out({"error": True, "message": f"Category '{name}' already exists."})
        return
    config.setdefault("categories", {})[name] = {
        "monthly": budget, "type": btype, "threshold": 0.8,
    }
    C.save_tracker_config(config)
    _out({"added": True, "category": name, "monthly": budget, "type": btype})


def cmd_remove_category(name: str):
    _require_setup()
    config = C._load_tracker_config()
    if name not in config.get("categories", {}):
        _out({"error": True, "message": f"Category '{name}' not found."})
        return
    del config["categories"][name]
    C.save_tracker_config(config)
    _out({"removed": True, "category": name})


# ── Runtime: rules ────────────────────────────────────

def cmd_list_rules():
    _require_setup()
    from lib.merchant_rules import list_rules
    rules = list_rules()
    _out({"rules": rules, "count": len(rules)})


def cmd_add_rule(pattern: str, category: str, confidence: float = 0.9):
    _require_setup()
    from lib.merchant_rules import save_merchant_rule
    save_merchant_rule(pattern, category, confidence=confidence, created_by="manual")
    _out({"added": True, "pattern": pattern, "category": category, "confidence": confidence})


# ── Runtime: balance ──────────────────────────────────

def cmd_update_balance(account: str, amount: float):
    _require_setup()
    from lib.cashflow import update_balance
    result = update_balance(account, amount)
    _out(result)


# ── Runtime: payments ─────────────────────────────────

def cmd_payment_check():
    _require_setup()
    from lib.payments import check_due_soon, get_upcoming_payments
    alerts = check_due_soon(days=3)
    upcoming = get_upcoming_payments(days=7)
    _out({"alerts": alerts, "upcoming_7d": upcoming})


# ── Runtime: AI backend info ──────────────────────────

def cmd_ai_backend():
    from lib.ai_parser import detect_ai_backend
    _out(detect_ai_backend())


# ── Main dispatcher ───────────────────────────────────

def main():
    if len(sys.argv) < 2:
        _err(FinanceError(ErrorCode.INVALID_ARGS, "Usage: finance.py <command> [args]"))

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Setup commands
    setup_commands = {
        "install-check": cmd_install_check,
        "preflight": cmd_preflight,
        "setup-status": cmd_setup_status,
        "setup-reset": cmd_setup_reset,
        "ai-backend": cmd_ai_backend,
    }

    if cmd == "onboarding-check":
        cmd_onboarding_check(args[0] if args else "")
        return

    if cmd == "setup-next":
        user_input = args[0] if args else ""
        mode = "full"
        if "--mode" in sys.argv:
            idx = sys.argv.index("--mode")
            if idx + 1 < len(sys.argv):
                mode = sys.argv[idx + 1]
        cmd_setup_next(user_input, mode)
        return

    if cmd in setup_commands:
        setup_commands[cmd]()
        return

    # Runtime commands
    runtime_commands = {
        "add": lambda: cmd_add(" ".join(args)),
        "add-photo": lambda: cmd_add_photo(args[0] if args else ""),
        "budget-status": cmd_budget_status,
        "safe-to-spend": cmd_safe_to_spend,
        "cashflow": cmd_safe_to_spend,
        "transactions": lambda: cmd_transactions(int(args[0]) if args else 10),
        "list-categories": cmd_list_categories,
        "add-category": lambda: cmd_add_category(
            args[0] if args else "",
            float(args[1]) if len(args) > 1 else 0,
            args[2] if len(args) > 2 else "variable",
        ),
        "remove-category": lambda: cmd_remove_category(args[0] if args else ""),
        "list-rules": cmd_list_rules,
        "add-rule": lambda: cmd_add_rule(
            args[0] if args else "",
            args[1] if len(args) > 1 else "Other",
            float(args[2]) if len(args) > 2 else 0.9,
        ),
        "update-balance": lambda: cmd_update_balance(
            args[0] if args else "Bank",
            float(args[1]) if len(args) > 1 else 0,
        ),
        "payment-check": cmd_payment_check,
        "status": cmd_budget_status,
    }

    if cmd in runtime_commands:
        runtime_commands[cmd]()
        return

    all_commands = list(setup_commands.keys()) + ["setup-next", "onboarding-check"] + list(runtime_commands.keys())
    _err(FinanceError(ErrorCode.UNKNOWN_COMMAND, f"Unknown command: {cmd}",
                      {"available": all_commands}))


if __name__ == "__main__":
    main()
