#!/usr/bin/env python3
"""Finance Tracker — Main CLI entry point.

Usage:
  python3 finance.py parse-text "$45 Publix Chase"
  python3 finance.py parse-photo /path/to/receipt.jpg
  python3 finance.py log '{"amount":45,"merchant":"Publix",...}'
  python3 finance.py balance 3200
  python3 finance.py cashflow
  python3 finance.py weekly-summary
  python3 finance.py monthly-report [YYYY-MM]
  python3 finance.py payment-check
  python3 finance.py reconcile /path/to/bank.csv [Chase|Discover|Citi]
  python3 finance.py add-rule "pattern" Category [confidence]
  python3 finance.py savings <goal> <amount>
  python3 finance.py savings-target <goal> <target>
  python3 finance.py status [category]
  python3 finance.py log-split '{"receipt_id":"...","transactions":[...]}'
  python3 finance.py taxes [year]
  python3 finance.py setup
  python3 finance.py setup-sheets
  python3 finance.py new-tax-profile
  python3 finance.py update-tax-profile
  python3 finance.py current-tax-profile
  python3 finance.py list-categories
  python3 finance.py add-category <name> <budget> [threshold]
  python3 finance.py modify-budget <category> <amount>
  python3 finance.py remove-category <name>
  python3 finance.py list-payments
  python3 finance.py add-payment <name> <amount> <due_day> [account] [autopay]
  python3 finance.py remove-payment <name>
  python3 finance.py list-debts
  python3 finance.py add-card <name>
  python3 finance.py remove-card <name>
  python3 finance.py list-goals
  python3 finance.py add-goal <name> <target> [deadline]
  python3 finance.py save <goal> <amount>
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from lib import config as C
from lib.rules import match_rules, add_rule, log_correction
from lib.parser import parse_text, parse_photo, parse_csv_text, check_duplicate
from lib.logger import log_transaction, log_income, log_split_receipt, format_confirmation, format_income_confirmation, format_split_confirmation
from lib.budget import weekly_summary, budget_status_brief
from lib.payments import check_payments
from lib.cashflow import daily_cashflow, update_balance, update_savings, update_savings_target, update_payday
from lib.analyst import monthly_report
from lib.reconcile import reconcile_csv
from lib import sheets


def cmd_parse_text(text: str):
    lang = C.get_language()
    tx = parse_text(text)
    # If income, skip duplicate check
    if tx.get("type") == "income":
        print(json.dumps(tx, indent=2, ensure_ascii=False))
        return
    # Check duplicates for expenses
    try:
        recent = sheets.get_recent_transactions(days=2)
        dup = check_duplicate(tx, recent)
        if dup:
            if lang == "es":
                tx["_duplicate_warning"] = (
                    f"Ya registré ${tx['amount']:.2f} en {tx['merchant']} el {dup.get('date')}. "
                    f"¿Es otra compra o duplicado?"
                )
            else:
                tx["_duplicate_warning"] = (
                    f"Already logged ${tx['amount']:.2f} at {tx['merchant']} on {dup.get('date')}. "
                    f"Is this another purchase or a duplicate?"
                )
    except Exception:
        pass  # Sheets not available yet, skip dup check
    print(json.dumps(tx, indent=2, ensure_ascii=False))


def cmd_parse_photo(path: str):
    tx = parse_photo(path)
    print(json.dumps(tx, indent=2, ensure_ascii=False))


def cmd_log(tx_json: str):
    tx = json.loads(tx_json)
    if tx.get("type") == "income":
        result = log_income(tx)
        msg = format_income_confirmation(tx, result)
    else:
        result = log_transaction(tx)
        msg = format_confirmation(tx, result)
    print(json.dumps({"result": result, "message": msg}, indent=2, ensure_ascii=False))


def cmd_income(text: str):
    """Quick income registration: income 2800 or income 2800 paycheck"""
    from lib.parser import parse_income
    parts = text.strip().split()
    amount = float(parts[0]) if parts else 0
    source = parts[1] if len(parts) > 1 else "paycheck"
    tx = {
        "type": "income",
        "amount": amount,
        "merchant": "Income",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "category": "Income",
        "subcategory": source,
        "card": "Bank",
        "input_method": "text",
        "confidence": 1.0,
        "notes": f"Income: {text.strip()}",
    }
    result = log_income(tx)
    msg = format_income_confirmation(tx, result)
    print(json.dumps({"result": result, "message": msg}, indent=2, ensure_ascii=False))


def cmd_payday(text: str):
    """Set payday schedule: 'biweekly 2800' or 'monthly 5000 15'"""
    parts = text.strip().split()
    schedule = parts[0] if parts else "biweekly"
    amount = float(parts[1]) if len(parts) > 1 else 0
    dates = None
    if len(parts) > 2:
        dates = [int(d) for d in parts[2].split(",")]
    result = update_payday(schedule, amount, dates)
    print(result)


def cmd_balance(amount: str):
    result = update_balance(float(amount))
    print(result)


def cmd_cashflow():
    print(daily_cashflow())


def cmd_weekly():
    print(weekly_summary())


def cmd_monthly(month: str = None):
    print(monthly_report(month))


def cmd_payments():
    alerts = check_payments()
    if alerts:
        print("\n".join(alerts))
    else:
        lang = C.get_language()
        if lang == "es":
            print("No hay alertas de pago hoy.")
        else:
            print("No payment alerts today.")


def cmd_reconcile(csv_path: str, bank: str = "auto"):
    content = Path(csv_path).read_text()
    result = reconcile_csv(content, bank)
    print(result["summary"])
    lang = C.get_language()
    if result["probable"]:
        header = "Necesitan confirmación:" if lang == "es" else "Need confirmation:"
        print(f"\n{header}")
        for p in result["probable"]:
            print(f"  ${p['amount']:.2f} — Bank: {p['merchant_bank']} vs Receipt: {p['merchant_receipt']}")
    if result["unmatched_receipt"]:
        header = "Recibos sin match en banco:" if lang == "es" else "Receipts without bank match:"
        print(f"\n{header}")
        for u in result["unmatched_receipt"]:
            print(f"  ${u['amount']:.2f} en {u['merchant_receipt']} ({u['date']})")


def cmd_add_rule(pattern: str, category: str, confidence: str = "0.85"):
    result = add_rule(pattern, category, float(confidence))
    print(f"Rule {result}: {pattern} → {category} ({confidence})")


def cmd_savings(goal: str, amount: str):
    print(update_savings(goal, float(amount)))


def cmd_savings_target(goal: str, target: str):
    print(update_savings_target(goal, float(target)))


def cmd_status(category: str = None):
    from datetime import datetime
    month = f"{datetime.now().year}-{datetime.now().month:02d}"
    if category:
        total = sheets.get_month_spending(category, month)
        budgets = C.get_category_budgets()
        budget = budgets.get(category, {}).get("monthly")
        if budget:
            print(f"{category}: ${total:.0f}/${budget} ({total/budget*100:.0f}%)")
        else:
            lang = C.get_language()
            no_budget = "sin presupuesto" if lang == "es" else "no budget"
            print(f"{category}: ${total:.0f} ({no_budget})")
    else:
        print(budget_status_brief(month))


def cmd_log_split(receipt_json: str):
    receipt = json.loads(receipt_json)
    results = log_split_receipt(receipt)
    messages = []
    for r in results:
        tx, budget = r["tx"], r["budget"]
        msg = f"  ✔ ${tx['amount']:.2f} → {tx['category']}"
        if tx.get("tax_deductible"):
            msg += f" [Deductible: {tx.get('tax_category')}]"
        if budget.get("alert_msg"):
            msg += f"\n    {budget['alert_msg']}"
        messages.append(msg)
    lang = C.get_language()
    header = f"Registradas {len(results)} transacciones:" if lang == "es" else f"Logged {len(results)} transactions:"
    print(header + "\n" + "\n".join(messages))


def cmd_taxes(year: str = None):
    """Tax deduction report — reads from tracker_config.json tax section."""
    tax_profile = C.get_tax_profile()
    if not tax_profile.get("enabled"):
        print("Tax tracking is not enabled.")
        print("Run: finance.py new-tax-profile")
        return

    year = year or str(datetime.now().year)
    deductions = sheets.get_tax_deductions(year=year)

    biz_name = tax_profile.get("business_name") or tax_profile.get("business_type", "Business")
    schedule = tax_profile.get("schedule_type", "")

    lines = [f"TAX DEDUCTIONS {year} — {biz_name} ({schedule})", ""]
    total = 0

    for cat in tax_profile.get("tax_categories", []):
        cat_deductions = [d for d in deductions if d.get("tax_category") == cat["id"]]
        cat_total = sum(float(d.get("amount", 0)) for d in cat_deductions)
        if cat_total > 0:
            lines.append(f"  {cat['label']}: ${cat_total:,.2f} ({len(cat_deductions)} items)")
            total += cat_total

    lines.append(f"\n  TOTAL DEDUCTIBLE: ${total:,.2f}")
    print("\n".join(lines))


def cmd_new_tax_profile():
    """Create a new tax profile via AI-powered wizard."""
    from lib.setup_wizard import run_tax_setup
    run_tax_setup()


def cmd_update_tax_profile():
    """Update existing tax profile — add/remove rules."""
    tax_profile = C.get_tax_profile()
    if not tax_profile.get("enabled"):
        print("No tax profile exists. Run: finance.py new-tax-profile")
        return
    print(f"Current profile: {tax_profile.get('business_type')}")
    print(f"Schedule: {tax_profile.get('schedule_type')}")
    print(f"Rules: {len(tax_profile.get('ask_rules', []))}")
    for i, rule in enumerate(tax_profile.get("ask_rules", []), 1):
        print(f"  {i}. {rule['trigger']} ({len(rule['keywords'])} keywords)")
    print()
    print("Options:")
    print("  1. Regenerate entire profile with AI")
    print("  2. Add a new rule")
    print("  3. Remove a rule")
    print("  4. Add keywords to existing rule")
    choice = input("→ ").strip()

    if choice == "1":
        from lib.setup_wizard import run_tax_setup
        run_tax_setup()
    elif choice == "3" and tax_profile.get("ask_rules"):
        idx = int(input("Rule number to remove: ").strip()) - 1
        if 0 <= idx < len(tax_profile["ask_rules"]):
            removed = tax_profile["ask_rules"].pop(idx)
            config = C._load_tracker_config()
            config["tax"] = tax_profile
            C.save_tracker_config(config)
            print(f"Removed rule: {removed['trigger']}")
    elif choice == "4" and tax_profile.get("ask_rules"):
        idx = int(input("Rule number to update: ").strip()) - 1
        if 0 <= idx < len(tax_profile["ask_rules"]):
            new_kw = input("New keywords (comma-separated): ").strip()
            keywords = [k.strip().lower() for k in new_kw.split(",") if k.strip()]
            tax_profile["ask_rules"][idx]["keywords"].extend(keywords)
            config = C._load_tracker_config()
            config["tax"] = tax_profile
            C.save_tracker_config(config)
            print(f"Added {len(keywords)} keywords to rule: {tax_profile['ask_rules'][idx]['trigger']}")


def cmd_current_tax_profile():
    """Show current tax profile."""
    tax_profile = C.get_tax_profile()
    if not tax_profile.get("enabled"):
        print("Tax tracking: DISABLED")
        print("Run: finance.py new-tax-profile")
        return
    print(f"Business: {tax_profile.get('business_type')}")
    print(f"Schedule: {tax_profile.get('schedule_type')}")
    if tax_profile.get("business_name"):
        print(f"Name: {tax_profile['business_name']}")
    print(f"Deduction rules ({len(tax_profile.get('ask_rules', []))}):")
    for rule in tax_profile.get("ask_rules", []):
        kw_preview = ", ".join(rule["keywords"][:5])
        print(f"  • {rule['trigger']}: {kw_preview}...")
    print(f"Never ask about: {', '.join(tax_profile.get('never_ask', [])[:8])}...")


def cmd_list_categories():
    """Show all categories with budget, threshold, and current month spending."""
    budgets = C.get_category_budgets()
    month = f"{datetime.now().year}-{datetime.now().month:02d}"
    try:
        spending = sheets.get_all_month_spending(month)
    except Exception:
        spending = {}

    for cat in C.get_categories():
        info = budgets.get(cat, {})
        budget = info.get("monthly")
        threshold = info.get("threshold")
        spent = spending.get(cat, 0)
        if budget:
            pct = spent / budget * 100
            if pct >= 100:
                flag = "OVER"
            elif pct >= 95:
                flag = "ALERT"
            elif pct >= 80:
                flag = "CAUTION"
            else:
                flag = "OK"
            print(f"  {cat}: ${spent:.0f}/${budget} ({pct:.0f}%) [{flag}]  threshold={threshold}")
        else:
            print(f"  {cat}: ${spent:.0f} (no budget)  threshold={threshold}")


def cmd_add_category(name: str, budget: str, threshold: str = "0.8"):
    """Add a category to tracker_config.json."""
    config = C._load_tracker_config()
    thr = None if threshold == "null" else float(threshold)
    config.setdefault("categories", {})[name] = {"monthly": int(budget), "threshold": thr}
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ Category '{name}' added: ${budget}/mo, threshold={thr}")


def cmd_modify_budget(category: str, amount: str):
    """Change the monthly budget for a category."""
    config = C._load_tracker_config()
    cats = config.get("categories", {})
    if category not in cats:
        print(f"Category '{category}' not found.")
        return
    old = cats[category].get("monthly")
    cats[category]["monthly"] = int(amount)
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ {category} budget: ${old} → ${amount}")


def cmd_remove_category(name: str):
    """Remove a category (asks for confirmation)."""
    config = C._load_tracker_config()
    cats = config.get("categories", {})
    if name not in cats:
        print(f"Category '{name}' not found.")
        return
    confirm = input(f"Remove category '{name}'? (y/N) → ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    del cats[name]
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ Category '{name}' removed.")


def cmd_list_payments():
    """Show all payments with details."""
    payments = C.get_payments()
    if not payments:
        print("No payments configured.")
        return
    total = 0
    for p in payments:
        autopay = "autopay" if p.get("autopay") else "manual"
        promo = f"  promo {p['apr']}% until {p['promo_expiry']}" if p.get("promo_expiry") else f"  APR {p.get('apr', '?')}%"
        print(f"  {p['name']}: ${p['amount']} due day {p['due_day']} ({p.get('account', '?')}) [{autopay}]{promo}")
        total += p["amount"]
    print(f"\n  Total fixed monthly: ${total:,}")


def cmd_add_payment(name: str, amount: str, due_day: str, account: str = "Bank", autopay: str = "true"):
    """Add a payment to tracker_config.json."""
    config = C._load_tracker_config()
    payment = {
        "name": name,
        "amount": float(amount),
        "due_day": int(due_day),
        "account": account,
        "autopay": autopay.lower() in ("true", "yes", "1"),
        "apr": 0,
        "promo_expiry": None,
    }
    config.setdefault("payments", []).append(payment)
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ Payment '{name}' added: ${amount} due day {due_day}")


def cmd_remove_payment(name: str):
    """Remove a payment by name."""
    config = C._load_tracker_config()
    payments = config.get("payments", [])
    idx = next((i for i, p in enumerate(payments) if p["name"].lower() == name.lower()), None)
    if idx is None:
        print(f"Payment '{name}' not found.")
        return
    removed = payments.pop(idx)
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ Payment '{removed['name']}' removed.")


def cmd_list_debts():
    """Show debts from the Debt Tracker tab in Sheets."""
    try:
        ws = sheets.get_sheet(C.TAB_DEBT)
        rows = ws.get_all_records()
        if not rows:
            print("No debts in Debt Tracker tab.")
            return
        for r in rows:
            print(f"  {r.get('creditor', '?')}: ${r.get('balance', 0):,} (APR {r.get('apr', '?')}%) min ${r.get('minimum_payment', '?')}")
    except Exception as e:
        print(f"Could not read Debt Tracker tab: {e}")


def cmd_add_card(name: str):
    """Add a card to user.cards."""
    config = C._load_tracker_config()
    cards = config["user"].setdefault("cards", [])
    if name in cards:
        print(f"Card '{name}' already exists.")
        return
    cards.append(name)
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ Card '{name}' added. Cards: {cards}")


def cmd_remove_card(name: str):
    """Remove a card from user.cards."""
    config = C._load_tracker_config()
    cards = config["user"].get("cards", [])
    matches = [c for c in cards if c.lower() == name.lower()]
    if not matches:
        print(f"Card '{name}' not found. Current: {cards}")
        return
    cards.remove(matches[0])
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ Card '{matches[0]}' removed. Cards: {cards}")


def cmd_list_goals():
    """Show savings goals with progress."""
    from datetime import date
    savings = C.get_savings()
    if not savings:
        print("No savings goals configured.")
        return
    for s in savings:
        remaining = s["target"] - s.get("saved", 0)
        days_left = max((date.fromisoformat(s["deadline"]) - date.today()).days, 1)
        daily = remaining / days_left
        pct = s.get("saved", 0) / s["target"] * 100 if s["target"] else 0
        print(f"  {s['goal']}: ${s.get('saved', 0):,.0f}/${s['target']:,.0f} ({pct:.0f}%) — ${daily:.0f}/day — deadline {s['deadline']} ({days_left}d)")


def cmd_add_goal(name: str, target: str, deadline: str = None):
    """Add a savings goal."""
    from datetime import date
    if not deadline:
        # Default: 6 months from now
        from dateutil.relativedelta import relativedelta
        deadline = (date.today() + relativedelta(months=6)).isoformat()
    config = C._load_tracker_config()
    config.setdefault("savings", []).append({
        "goal": name,
        "target": float(target),
        "saved": 0,
        "deadline": deadline,
    })
    C.save_tracker_config(config)
    C.invalidate_config_cache()
    print(f"✅ Goal '{name}' added: ${target} by {deadline}")


def cmd_setup():
    """Run the first-time setup wizard."""
    from lib.setup_wizard import run_setup_wizard
    run_setup_wizard()


def cmd_batch_receipts(file_path: str, account: str = "Chase"):
    from lib.batch_receipts import process_receipt_batch
    with open(file_path) as f:
        links = [line.strip() for line in f if line.strip() and line.strip().startswith("http")]
    result = process_receipt_batch(links, account)
    print(result["summary"])
    if result.get("pending_airbnb"):
        print(result["airbnb_prompt"])


def cmd_setup_sheets():
    """Create the Google Spreadsheet with all required tabs (5 data tabs)."""
    client = sheets.get_client(allow_interactive=True)
    spreadsheet_name = C.get_spreadsheet_name()

    try:
        ss = client.open(spreadsheet_name)
        print(f"Spreadsheet '{spreadsheet_name}' already exists.")
    except Exception:
        ss = client.create(spreadsheet_name)
        print(f"Created spreadsheet: {spreadsheet_name}")

    existing_tabs = [ws.title for ws in ss.worksheets()]

    tab_headers = {
        C.TAB_TRANSACTIONS: [
            "date", "amount", "merchant", "category", "subcategory",
            "card", "input_method", "confidence", "matched", "source",
            "notes", "timestamp", "month",
            "receipt_id", "receipt_number", "store_address",
            "tax_deductible", "tax_category", "type"
        ],
        C.TAB_MONTHLY: [
            "month", "total_spent", "total_budget", "categories_over", "top_merchant", "notes"
        ],
        C.TAB_DEBT: [
            "month", "creditor", "balance", "minimum_payment", "apr", "notes"
        ],
        C.TAB_RECONCILIATION: [
            "date", "amount", "merchant_bank", "merchant_receipt",
            "status", "receipt_row", "csv_row", "resolved_by", "notes"
        ],
        C.TAB_CASHFLOW: [
            "date", "account", "merchant", "amount_signed", "flow_type",
            "category", "subcategory", "notes", "source", "timestamp", "month"
        ],
    }

    for tab_name, headers in tab_headers.items():
        if tab_name in existing_tabs:
            print(f"  Tab '{tab_name}' already exists, skipping.")
            continue
        ws = ss.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
        ws.update(range_name="A1", values=[headers])
        print(f"  Created tab: {tab_name}")

    # Remove default Sheet1 if other tabs exist
    if "Sheet1" in existing_tabs and len(ss.worksheets()) > 1:
        try:
            ss.del_worksheet(ss.worksheet("Sheet1"))
            print("  Removed default Sheet1.")
        except Exception:
            pass

    print(f"\n✓ Spreadsheet ready: {ss.url}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Setup check — gentle reminder on first run
    if not C.is_setup_complete() and cmd not in ("setup", "setup-sheets"):
        print("First time? Run the setup wizard first:")
        print("   python3 finance.py setup")
        print()

    commands = {
        "parse-text": lambda: cmd_parse_text(" ".join(args)),
        "parse-photo": lambda: cmd_parse_photo(args[0]),
        "log": lambda: cmd_log(args[0]),
        "income": lambda: cmd_income(" ".join(args)),
        "payday": lambda: cmd_payday(" ".join(args)),
        "balance": lambda: cmd_balance(args[0]),
        "cashflow": cmd_cashflow,
        "weekly-summary": cmd_weekly,
        "monthly-report": lambda: cmd_monthly(args[0] if args else None),
        "payment-check": cmd_payments,
        "reconcile": lambda: cmd_reconcile(args[0], args[1] if len(args) > 1 else "auto"),
        "add-rule": lambda: cmd_add_rule(args[0], args[1], args[2] if len(args) > 2 else "0.85"),
        "savings": lambda: cmd_savings(args[0], args[1]),
        "savings-target": lambda: cmd_savings_target(args[0], args[1]),
        "status": lambda: cmd_status(args[0] if args else None),
        "log-split": lambda: cmd_log_split(args[0]),
        "taxes": lambda: cmd_taxes(args[0] if args else None),
        "batch-receipts": lambda: cmd_batch_receipts(args[0], args[1] if len(args) > 1 else "Chase"),
        "setup-sheets": cmd_setup_sheets,
        "setup": cmd_setup,
        "new-tax-profile": cmd_new_tax_profile,
        "update-tax-profile": cmd_update_tax_profile,
        "current-tax-profile": cmd_current_tax_profile,
        "list-categories": cmd_list_categories,
        "add-category": lambda: cmd_add_category(args[0], args[1], args[2] if len(args) > 2 else "0.8"),
        "modify-budget": lambda: cmd_modify_budget(args[0], args[1]),
        "remove-category": lambda: cmd_remove_category(args[0]),
        "list-payments": cmd_list_payments,
        "add-payment": lambda: cmd_add_payment(args[0], args[1], args[2], args[3] if len(args) > 3 else "Bank", args[4] if len(args) > 4 else "true"),
        "remove-payment": lambda: cmd_remove_payment(args[0]),
        "list-debts": cmd_list_debts,
        "add-card": lambda: cmd_add_card(args[0]),
        "remove-card": lambda: cmd_remove_card(args[0]),
        "list-goals": cmd_list_goals,
        "add-goal": lambda: cmd_add_goal(args[0], args[1], args[2] if len(args) > 2 else None),
        "save": lambda: cmd_savings(args[0], args[1]),
    }

    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    commands[cmd]()


if __name__ == "__main__":
    main()
