#!/usr/bin/env python3
"""Finance Tracker v2 — CLI entry point.

Every command returns JSON to stdout. The LLM never controls flow.
"""

import json
import sys
from datetime import date, datetime
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
    if not C.is_setup_complete():
        _err(FinanceError(ErrorCode.SETUP_INCOMPLETE,
                          'Setup not complete. Run: finance.py setup-next "start"'))

def _with_onboarding(command: str, result: dict) -> dict:
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
        _out(sm.process(user_input))
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


# ── Add transaction ───────────────────────────────────

def cmd_add(text: str):
    _require_setup()
    from lib.parser import parse_text
    from lib.merchant_rules import save_merchant_rule
    from lib.budget import check_budget_alerts

    tx = parse_text(text)
    if tx.get("llm_request"):
        _out(tx)
        return

    # Auto-learn merchant rule
    if (tx.get("confidence", 0) >= 0.8 and tx.get("merchant")
            and tx.get("category") and tx.get("category") != "Other"
            and not tx.get("requires_line_items")):
        save_merchant_rule(tx["merchant"], tx["category"],
                           confidence=tx.get("confidence", 0.85), created_by="auto")

    # Write to Sheets
    _try_write_tx(tx)

    # Check budget alerts
    alerts = check_budget_alerts(tx.get("category", "Other"), tx.get("amount", 0))
    if alerts:
        tx["_budget_alerts"] = alerts

    # Implicit confirm for high confidence
    lang = C.get_language()
    if tx.get("confidence", 0) >= 0.9 and not tx.get("needs_confirmation"):
        tx["_implicit_confirm"] = True
        if lang == "es":
            tx["_message"] = (f"Registrado: ${tx.get('amount', 0):.2f} → "
                              f"{tx.get('category', 'Other')} ({tx.get('merchant', '')}). "
                              f"Responde 'undo' para revertir.")
        else:
            tx["_message"] = (f"Added: ${tx.get('amount', 0):.2f} → "
                              f"{tx.get('category', 'Other')} ({tx.get('merchant', '')}). "
                              f"Reply 'undo' to revert.")

    # Save for undo
    _save_last_tx(tx)
    _out(_with_onboarding("add", tx))


def cmd_add_photo(path: str):
    _require_setup()
    from lib.parser import parse_photo
    tx = parse_photo(path)
    if tx:
        _out(_with_onboarding("add-photo", tx))
    else:
        _out({"error": True, "message": "Failed to parse receipt photo."})


def _try_write_tx(tx: dict):
    """Try to write transaction to Sheets. Silently skip if not available."""
    try:
        from lib import sheets
        if sheets.load_sheets_config():
            tx.setdefault("timestamp", datetime.now().isoformat())
            tx.setdefault("month", tx.get("date", "")[:7])
            tx.setdefault("matched", False)
            tx.setdefault("source", "manual")
            sheets.write_transaction(tx)
            tx["_written_to_sheets"] = True
    except Exception:
        tx["_written_to_sheets"] = False


def _save_last_tx(tx: dict):
    """Save last transaction for undo."""
    C.save_json(C.get_config_dir() / "last_transaction.json", {
        "tx": tx, "timestamp": datetime.now().isoformat(),
    })


# ── Undo ──────────────────────────────────────────────

def cmd_undo():
    _require_setup()
    path = C.get_config_dir() / "last_transaction.json"
    if not path.exists():
        _out({"error": True, "message": "Nothing to undo."})
        return
    data = C.load_json(path)
    ts = data.get("timestamp", "")
    try:
        from datetime import datetime as dt
        saved_at = dt.fromisoformat(ts)
        if (dt.now() - saved_at).total_seconds() > 300:
            _out({"error": True, "message": "Undo window expired (5 minutes)."})
            return
    except Exception:
        pass
    # TODO: remove from Sheets by row matching
    path.unlink()
    _out({"undone": True, "transaction": data.get("tx", {}),
          "message": "Transaction marked for removal."})


# ── Budget ────────────────────────────────────────────

def cmd_budget_status():
    _require_setup()
    from lib.budget import get_budget_status, format_budget_status
    status = get_budget_status()
    status["_formatted"] = format_budget_status(status)
    _out(_with_onboarding("budget-status", status))


# ── Cashflow ──────────────────────────────────────────

def cmd_safe_to_spend():
    _require_setup()
    from lib.cashflow import safe_to_spend, format_cashflow
    data = safe_to_spend()
    data["_formatted"] = format_cashflow(data)
    _out(_with_onboarding("cashflow", data))


def cmd_daily_cashflow_report():
    _require_setup()
    from lib.reports import daily_cashflow_report
    _out(daily_cashflow_report())


# ── Reports ───────────────────────────────────────────

def cmd_weekly_review():
    _require_setup()
    from lib.reports import weekly_review
    _out(weekly_review())

def cmd_monthly_report(month: str = ""):
    _require_setup()
    from lib.reports import monthly_report
    _out(monthly_report(month or None))


# ── Transactions ──────────────────────────────────────

def cmd_transactions(count: int = 10):
    _require_setup()
    try:
        from lib import sheets
        txs = sheets.read_transactions(limit=count)
        _out({"transactions": txs, "count": len(txs)})
    except Exception:
        _out({"transactions": [], "count": 0, "message": "Sheets not available."})


# ── Categories ────────────────────────────────────────

def cmd_list_categories():
    _require_setup()
    budgets = C.get_category_budgets()
    categories = [{"category": n, "monthly": d.get("monthly", 0),
                    "type": d.get("type", "variable"), "threshold": d.get("threshold", 0.8)}
                   for n, d in budgets.items()]
    _out({"categories": categories, "count": len(categories)})

def cmd_add_category(name: str, budget: float, btype: str = "variable"):
    _require_setup()
    config = C._load_tracker_config()
    if name in config.get("categories", {}):
        _out({"error": True, "message": f"Category '{name}' already exists."})
        return
    config.setdefault("categories", {})[name] = {"monthly": budget, "type": btype, "threshold": 0.8}
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


# ── Rules ─────────────────────────────────────────────

def cmd_list_rules():
    _require_setup()
    from lib.merchant_rules import list_rules
    _out({"rules": list_rules(), "count": len(list_rules())})

def cmd_add_rule(pattern: str, category: str, confidence: float = 0.9):
    _require_setup()
    from lib.merchant_rules import save_merchant_rule
    save_merchant_rule(pattern, category, confidence=confidence, created_by="manual")
    _out({"added": True, "pattern": pattern, "category": category, "confidence": confidence})


# ── Balance ───────────────────────────────────────────

def cmd_update_balance(account: str, amount: float):
    _require_setup()
    from lib.cashflow import update_balance
    _out(update_balance(account, amount))


# ── Payments ──────────────────────────────────────────

def cmd_payment_check():
    _require_setup()
    from lib.payments import check_due_soon, get_upcoming_payments
    _out({"alerts": check_due_soon(days=3), "upcoming_7d": get_upcoming_payments(days=7)})


# ── Reconciliation ────────────────────────────────────

def cmd_reconcile(csv_path: str):
    _require_setup()
    from lib.reconcile import reconcile_csv
    if not Path(csv_path).exists():
        _out({"error": True, "message": f"File not found: {csv_path}"})
        return
    _out(reconcile_csv(csv_path))

def cmd_analyze_csv(csv_path: str):
    _require_setup()
    from lib.csv_analyzer import analyze_csv
    if not Path(csv_path).exists():
        _out({"error": True, "message": f"File not found: {csv_path}"})
        return
    _out(analyze_csv(csv_path))


# ── Tax ───────────────────────────────────────────────

def cmd_tax_summary(year: str = ""):
    _require_setup()
    if not year:
        year = str(date.today().year)
    try:
        from lib import sheets
        deductions = sheets.get_tax_deductions(year=year)
    except Exception:
        deductions = []

    by_category = {}
    total = 0
    for d in deductions:
        cat = d.get("tax_category", "other")
        amt = float(d.get("amount", 0))
        by_category.setdefault(cat, {"count": 0, "total": 0})
        by_category[cat]["count"] += 1
        by_category[cat]["total"] += amt
        total += amt

    config = C._load_tracker_config()
    rulepacks = config.get("tax", {}).get("rulepacks", [])
    _out({
        "year": year,
        "total_deductible": round(total, 2),
        "by_category": {k: {"count": v["count"], "total": round(v["total"], 2)}
                        for k, v in by_category.items()},
        "rulepacks": rulepacks,
        "transaction_count": len(deductions),
    })

def cmd_tax_export(year: str = ""):
    _require_setup()
    if not year:
        year = str(date.today().year)
    try:
        from lib import sheets
        deductions = sheets.get_tax_deductions(year=year)
    except Exception:
        deductions = []

    # Format as CSV-ready rows
    rows = []
    for d in deductions:
        rows.append({
            "date": d.get("date", ""),
            "amount": d.get("amount", 0),
            "merchant": d.get("merchant", ""),
            "category": d.get("category", ""),
            "tax_category": d.get("tax_category", ""),
        })
    _out({"year": year, "rows": rows, "count": len(rows),
          "format": "Schedule E/C ready"})


# ── Debt ──────────────────────────────────────────────

def cmd_debt_strategy():
    _require_setup()
    from lib.debt_optimizer import compare_strategies, format_debt_strategy
    comparison = compare_strategies()
    comparison["_formatted"] = format_debt_strategy(comparison)
    _out(comparison)


# ── Savings ───────────────────────────────────────────

def cmd_savings_goals():
    _require_setup()
    goals = C.get_savings()
    today = date.today()
    for g in goals:
        remaining = g.get("target", 0) - g.get("saved", 0)
        try:
            dl = date.fromisoformat(g.get("deadline", ""))
            days_left = (dl - today).days
            g["days_left"] = days_left
            g["daily_required"] = round(remaining / max(days_left, 1), 2) if remaining > 0 else 0
        except (ValueError, TypeError):
            g["days_left"] = None
            g["daily_required"] = 0
    _out({"savings_goals": goals, "count": len(goals)})

def cmd_add_savings_goal(name: str, target: float, deadline: str = ""):
    _require_setup()
    config = C._load_tracker_config()
    config.setdefault("savings", []).append({
        "goal": name, "target": target, "saved": 0,
        "deadline": deadline or (date.today().replace(year=date.today().year + 1)).isoformat(),
    })
    C.save_tracker_config(config)
    _out({"added": True, "goal": name, "target": target, "deadline": deadline})


# ── Sheet management ──────────────────────────────────

def cmd_repair_sheet():
    _require_setup()
    from lib import sheets
    sc = sheets.load_sheets_config()
    if not sc:
        _out({"error": True, "message": "No sheets_config.json found."})
        return
    results = sheets.validate_schema(sc["spreadsheet_id"], sc)
    _out({"validation": results, "all_ok": all(r["ok"] for r in results.values())})

def cmd_reconnect_sheets():
    _require_setup()
    from lib import sheets
    try:
        sheets._CLIENT = None
        sheets._SPREADSHEET = None
        creds = sheets.get_credentials()
        _out({"reconnected": True, "message": "Google OAuth token refreshed."})
    except Exception as e:
        _out({"error": True, "message": str(e)})


# ── AI backend ────────────────────────────────────────

def cmd_ai_backend():
    from lib.ai_parser import detect_ai_backend
    _out(detect_ai_backend())


# ── Main dispatcher ───────────────────────────────────

def main():
    if len(sys.argv) < 2:
        _err(FinanceError(ErrorCode.INVALID_ARGS, "Usage: finance.py <command> [args]"))

    cmd = sys.argv[1]
    args = sys.argv[2:]

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

    runtime_commands = {
        "add": lambda: cmd_add(" ".join(args)),
        "add-photo": lambda: cmd_add_photo(args[0] if args else ""),
        "budget-status": cmd_budget_status,
        "safe-to-spend": cmd_safe_to_spend,
        "cashflow": cmd_daily_cashflow_report,
        "weekly-review": cmd_weekly_review,
        "monthly-report": lambda: cmd_monthly_report(args[0] if args else ""),
        "transactions": lambda: cmd_transactions(int(args[0]) if args else 10),
        "list-categories": cmd_list_categories,
        "add-category": lambda: cmd_add_category(args[0] if args else "", float(args[1]) if len(args) > 1 else 0, args[2] if len(args) > 2 else "variable"),
        "remove-category": lambda: cmd_remove_category(args[0] if args else ""),
        "list-rules": cmd_list_rules,
        "add-rule": lambda: cmd_add_rule(args[0] if args else "", args[1] if len(args) > 1 else "Other", float(args[2]) if len(args) > 2 else 0.9),
        "update-balance": lambda: cmd_update_balance(args[0] if args else "Bank", float(args[1]) if len(args) > 1 else 0),
        "payment-check": cmd_payment_check,
        "reconcile": lambda: cmd_reconcile(args[0] if args else ""),
        "analyze-csv": lambda: cmd_analyze_csv(args[0] if args else ""),
        "tax-summary": lambda: cmd_tax_summary(args[0] if args else ""),
        "tax-export": lambda: cmd_tax_export(args[0] if args else ""),
        "debt-strategy": cmd_debt_strategy,
        "savings-goals": cmd_savings_goals,
        "add-savings-goal": lambda: cmd_add_savings_goal(args[0] if args else "", float(args[1]) if len(args) > 1 else 0, args[2] if len(args) > 2 else ""),
        "repair-sheet": cmd_repair_sheet,
        "reconnect-sheets": cmd_reconnect_sheets,
        "undo": cmd_undo,
        "status": cmd_budget_status,
    }

    if cmd in runtime_commands:
        runtime_commands[cmd]()
        return

    all_cmds = list(setup_commands.keys()) + ["setup-next", "onboarding-check"] + list(runtime_commands.keys())
    _err(FinanceError(ErrorCode.UNKNOWN_COMMAND, f"Unknown command: {cmd}", {"available": all_cmds}))


if __name__ == "__main__":
    main()
