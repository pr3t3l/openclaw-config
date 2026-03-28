#!/usr/bin/env python3
"""Robotin Finance Tracker — Main CLI entry point.

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
  python3 finance.py airbnb [month]
  python3 finance.py setup-sheets
"""

import json
import sys
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from lib import config as C
from lib.rules import match_rules, add_rule, log_correction
from lib.parser import parse_text, parse_photo, parse_csv_text, check_duplicate
from lib.logger import log_transaction, log_split_receipt, format_confirmation, format_split_confirmation
from lib.budget import weekly_summary, budget_status_brief
from lib.payments import check_payments
from lib.cashflow import daily_cashflow, update_balance, update_savings, update_savings_target
from lib.analyst import monthly_report
from lib.reconcile import reconcile_csv
from lib import sheets


def cmd_parse_text(text: str):
    tx = parse_text(text)
    # Check duplicates
    try:
        recent = sheets.get_recent_transactions(days=2)
        dup = check_duplicate(tx, recent)
        if dup:
            tx["_duplicate_warning"] = (
                f"Ya registré ${tx['amount']:.2f} en {tx['merchant']} el {dup.get('date')}. "
                f"¿Es otra compra o duplicado?"
            )
    except Exception:
        pass  # Sheets not available yet, skip dup check
    print(json.dumps(tx, indent=2, ensure_ascii=False))


def cmd_parse_photo(path: str):
    tx = parse_photo(path)
    print(json.dumps(tx, indent=2, ensure_ascii=False))


def cmd_log(tx_json: str):
    tx = json.loads(tx_json)
    result = log_transaction(tx)
    msg = format_confirmation(tx, result)
    print(json.dumps({"result": result, "message": msg}, indent=2, ensure_ascii=False))


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
        print("No hay alertas de pago hoy.")


def cmd_reconcile(csv_path: str, bank: str = "auto"):
    content = Path(csv_path).read_text()
    result = reconcile_csv(content, bank)
    print(result["summary"])
    if result["probable"]:
        print("\nNecesitan confirmación:")
        for p in result["probable"]:
            print(f"  ${p['amount']:.2f} — Bank: {p['merchant_bank']} vs Receipt: {p['merchant_receipt']}")
    if result["unmatched_receipt"]:
        print("\nRecibos sin match en banco:")
        for u in result["unmatched_receipt"]:
            print(f"  ${u['amount']:.2f} en {u['merchant_receipt']} ({u['date']})")


def cmd_add_rule(pattern: str, category: str, confidence: str = "0.85"):
    result = add_rule(pattern, category, float(confidence))
    print(f"Regla {result}: {pattern} → {category} ({confidence})")


def cmd_savings(goal: str, amount: str):
    print(update_savings(goal, float(amount)))


def cmd_savings_target(goal: str, target: str):
    print(update_savings_target(goal, float(target)))


def cmd_status(category: str = None):
    from datetime import datetime
    month = f"{datetime.now().year}-{datetime.now().month:02d}"
    if category:
        total = sheets.get_month_spending(category, month)
        budgets = C.load_budgets()["categories"]
        budget = budgets.get(category, {}).get("monthly")
        if budget:
            print(f"{category}: ${total:.0f}/${budget} ({total/budget*100:.0f}%)")
        else:
            print(f"{category}: ${total:.0f} (sin presupuesto)")
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
            msg += f" [Deducible: {tx.get('tax_category')}]"
        if budget.get("alert_msg"):
            msg += f"\n    {budget['alert_msg']}"
        messages.append(msg)
    print(f"Registradas {len(results)} transacciones:\n" + "\n".join(messages))


def cmd_taxes(year: str = None):
    from datetime import datetime
    year = year or str(datetime.now().year)
    deductions = sheets.get_tax_deductions(year=year)

    # Group by tax_category
    groups: dict[str, list] = {}
    for d in deductions:
        cat = d.get("tax_category", "other")
        groups.setdefault(cat, []).append(d)

    lines = [f"DEDUCCIONES FISCALES {year} (Airbnb Goose Creek)", ""]
    airbnb_total = 0
    for cat_key, label in [
        ("airbnb_supplies", "Supplies (limpieza, toallas, sábanas)"),
        ("airbnb_repair", "Repairs (reparaciones, herramientas)"),
        ("airbnb_cleaning", "Cleaning services"),
        ("airbnb_utilities", "Utilities"),
        ("airbnb_insurance", "Insurance"),
        ("airbnb_mortgage_interest", "Mortgage interest"),
    ]:
        items = groups.get(cat_key, [])
        total = sum(float(i.get("amount", 0)) for i in items)
        airbnb_total += total
        if total > 0 or cat_key in ("airbnb_supplies", "airbnb_repair", "airbnb_cleaning"):
            lines.append(f"{label}: ${total:,.2f} ({len(items)} items)")

    lines.append(f"\nTotal deducible Airbnb: ${airbnb_total:,.2f}")

    biz_items = groups.get("business_expense", [])
    biz_total = sum(float(i.get("amount", 0)) for i in biz_items)
    lines.append(f"\nBusiness expenses (Work_Tools): ${biz_total:,.2f}")
    lines.append("\nNota: Esto NO es asesoría fiscal. Comparte con Walker Dunn.")

    print("\n".join(lines))


def cmd_airbnb(month: str = None):
    from datetime import datetime
    if not month:
        month = f"{datetime.now().year}-{datetime.now().month:02d}"
    elif len(month) <= 2:
        # User said "marzo" or "3" — convert to YYYY-MM
        month_names = {
            "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        mm = month_names.get(month.lower(), month.zfill(2))
        month = f"{datetime.now().year}-{mm}"

    deductions = sheets.get_tax_deductions(month=month)
    if not deductions:
        print(f"No hay deducciones Airbnb para {month}.")
        return

    total = sum(float(d.get("amount", 0)) for d in deductions)
    lines = [f"DEDUCCIONES AIRBNB — {month}", ""]
    for d in deductions:
        lines.append(f"  ${float(d.get('amount', 0)):,.2f} — {d.get('merchant', '?')} [{d.get('tax_category', '?')}]")
    lines.append(f"\nTotal: ${total:,.2f} ({len(deductions)} items)")
    print("\n".join(lines))


def cmd_setup_sheets():
    """Create the Google Spreadsheet with all required tabs."""
    client = sheets.get_client(allow_interactive=True)

    try:
        ss = client.open(C.SPREADSHEET_NAME)
        print(f"Spreadsheet '{C.SPREADSHEET_NAME}' already exists.")
    except Exception:
        ss = client.create(C.SPREADSHEET_NAME)
        print(f"Created spreadsheet: {C.SPREADSHEET_NAME}")

    existing_tabs = [ws.title for ws in ss.worksheets()]

    tab_headers = {
        C.TAB_TRANSACTIONS: [
            "date", "amount", "merchant", "category", "subcategory",
            "card", "input_method", "confidence", "matched", "source",
            "notes", "timestamp", "month",
            "receipt_id", "receipt_number", "store_address",
            "tax_deductible", "tax_category"
        ],
        C.TAB_BUDGET: [
            "category", "monthly_budget", "alert_threshold"
        ],
        C.TAB_PAYMENTS: [
            "name", "due_day", "amount", "account", "autopay", "apr", "promo_expiry"
        ],
        C.TAB_MONTHLY: [
            "month", "total_spent", "total_budget", "categories_over", "top_merchant", "notes"
        ],
        "Debt Tracker": [
            "month", "creditor", "balance", "minimum_payment", "apr", "notes"
        ],
        C.TAB_RULES: [
            "merchant_pattern", "category", "subcategory", "default_account",
            "confidence", "amount_condition", "last_updated", "created_by"
        ],
        C.TAB_RECONCILIATION: [
            "date", "amount", "merchant_bank", "merchant_receipt",
            "status", "receipt_row", "csv_row", "resolved_by", "notes"
        ],
    }

    for tab_name, headers in tab_headers.items():
        if tab_name in existing_tabs:
            print(f"  Tab '{tab_name}' already exists, skipping.")
            continue
        ws = ss.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
        ws.update(range_name="A1", values=[headers])
        print(f"  Created tab: {tab_name}")

    # Populate Budget tab with defaults
    budget_ws = ss.worksheet(C.TAB_BUDGET)
    if len(budget_ws.get_all_values()) <= 1:
        budgets = C.load_budgets()["categories"]
        rows = []
        for cat, vals in budgets.items():
            rows.append([cat, vals.get("monthly") or "", vals.get("threshold") or ""])
        budget_ws.update(range_name="A2", values=rows)
        print("  Populated Budget tab with defaults.")

    # Populate Payment Calendar
    payments_ws = ss.worksheet(C.TAB_PAYMENTS)
    if len(payments_ws.get_all_values()) <= 1:
        payments = C.load_payments()
        rows = [[p["name"], p["due_day"], p["amount"], p["account"],
                 p.get("autopay", False), p.get("apr", ""), p.get("promo_expiry", "")]
                for p in payments]
        payments_ws.update(range_name="A2", values=rows)
        print("  Populated Payment Calendar tab.")

    # Populate Rules tab
    rules_ws = ss.worksheet(C.TAB_RULES)
    if len(rules_ws.get_all_values()) <= 1:
        rules = C.load_rules()
        from datetime import datetime
        rows = [[r["merchant_pattern"], r["category"], r.get("subcategory", ""),
                 r.get("default_account", ""), r.get("confidence", 0.9),
                 r.get("amount_condition", "any"),
                 datetime.now().strftime("%Y-%m-%d"), r.get("created_by", "manual")]
                for r in rules]
        rules_ws.update(range_name="A2", values=rows)
        print("  Populated Rules tab with initial rules.")

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

    commands = {
        "parse-text": lambda: cmd_parse_text(" ".join(args)),
        "parse-photo": lambda: cmd_parse_photo(args[0]),
        "log": lambda: cmd_log(args[0]),
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
        "airbnb": lambda: cmd_airbnb(args[0] if args else None),
        "setup-sheets": cmd_setup_sheets,
    }

    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    commands[cmd]()


if __name__ == "__main__":
    main()
