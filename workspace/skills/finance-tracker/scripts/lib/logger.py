"""Module 2: Transaction Logger — write to Google Sheets, calc running totals."""

from datetime import datetime
from . import config as C
from . import sheets


def log_income(tx: dict) -> dict:
    """Log an income transaction and auto-update available balance."""
    now = datetime.now()
    tx["timestamp"] = now.isoformat()
    tx["month"] = tx.get("date", now.strftime("%Y-%m-%d"))[:7]
    tx["type"] = "income"
    tx.setdefault("matched", False)
    tx.setdefault("source", "manual")
    tx.setdefault("tax_deductible", False)
    tx.setdefault("tax_category", "none")
    tx.setdefault("receipt_id", "")
    tx.setdefault("receipt_number", "")
    tx.setdefault("store_address", "")

    sheets.append_transaction(tx)

    # Auto-update available balance
    budgets = C.load_budgets()
    old_balance = budgets.get("available_balance", 0)
    new_balance = old_balance + tx["amount"]
    budgets["available_balance"] = new_balance
    budgets["last_balance_update"] = now.isoformat()
    C.save_json(C.CONFIG_DIR / "budgets.json", budgets)

    # Get month income total
    month_income = sheets.get_month_income(tx["month"])

    return {
        "logged": True,
        "type": "income",
        "amount": tx["amount"],
        "source": tx.get("subcategory", "other"),
        "old_balance": old_balance,
        "new_balance": new_balance,
        "month_income": month_income,
    }


def log_transaction(tx: dict) -> dict:
    """Log a confirmed transaction and return budget status."""
    now = datetime.now()
    tx["timestamp"] = now.isoformat()
    tx["month"] = tx.get("date", now.strftime("%Y-%m-%d"))[:7]
    tx.setdefault("matched", False)
    tx.setdefault("source", "receipt")
    tx.setdefault("type", "expense")
    tx.setdefault("tax_deductible", False)
    tx.setdefault("tax_category", "none")
    tx.setdefault("receipt_id", "")
    tx.setdefault("receipt_number", "")
    tx.setdefault("store_address", "")

    # Write to sheets
    sheets.append_transaction(tx)

    # Calculate running total for this category
    category = tx.get("category", "Other")
    month = tx["month"]
    month_total = sheets.get_month_spending(category, month)

    # Get budget info
    budgets = C.load_budgets()
    cat_budget = budgets["categories"].get(category, {})
    monthly_limit = cat_budget.get("monthly")
    threshold = cat_budget.get("threshold")

    result = {
        "logged": True,
        "category": category,
        "month_total": month_total,
        "monthly_limit": monthly_limit,
    }

    # Check budget alerts
    if monthly_limit and threshold:
        pct = month_total / monthly_limit
        remaining = monthly_limit - month_total
        result["pct"] = round(pct * 100, 1)
        result["remaining"] = round(remaining, 2)

        if pct >= 1.0:
            result["alert"] = "over_budget"
            result["alert_msg"] = f"EXCEDIDO: {category} ${month_total:.0f}/${monthly_limit}. Estás ${abs(remaining):.0f} por encima."
        elif pct >= 0.95:
            result["alert"] = "critical"
            result["alert_msg"] = f"ALERTA: {category} ${month_total:.0f}/${monthly_limit} ({result['pct']}%). Solo ${remaining:.0f} restantes."
        elif pct >= threshold:
            result["alert"] = "warning"
            result["alert_msg"] = f"Cuidado: {category} ${month_total:.0f}/${monthly_limit} ({result['pct']}%). Te quedan ${remaining:.0f}."
        else:
            result["alert"] = None

    return result


def log_split_receipt(receipt: dict) -> list[dict]:
    """Log all transactions from a split receipt."""
    results = []
    receipt_id = receipt.get("receipt_id", "")
    receipt_number = receipt.get("receipt_number", "")
    store_address = receipt.get("store_address", "")

    for tx in receipt.get("transactions", []):
        tx["receipt_id"] = receipt_id
        tx["receipt_number"] = receipt_number
        tx["store_address"] = store_address
        result = log_transaction(tx)
        results.append({"tx": tx, "budget": result})

    return results


def format_income_confirmation(tx: dict, result: dict) -> str:
    """Format the Telegram confirmation message for an income."""
    msg = (
        f"💰 Ingreso registrado: ${tx['amount']:,.2f}"
        f" ({result.get('source', 'other')})\n"
        f"Saldo anterior: ${result['old_balance']:,.2f}\n"
        f"Saldo nuevo: ${result['new_balance']:,.2f}\n"
        f"Ingresos este mes: ${result.get('month_income', 0):,.2f}"
    )
    return msg


def format_confirmation(tx: dict, budget_info: dict) -> str:
    """Format the Telegram confirmation message for a single transaction."""
    msg = f"Registrado: ${tx['amount']:.2f} en {tx['merchant']} ({tx['category']})"
    if tx.get("card"):
        msg += f" con {tx['card']}"
    msg += "."

    if tx.get("tax_deductible"):
        msg += f" [Deducible: {tx.get('tax_category', 'airbnb_supplies')}]"

    if budget_info.get("monthly_limit"):
        msg += f"\n{tx['category']} este mes: ${budget_info['month_total']:.0f}/${budget_info['monthly_limit']} ({budget_info.get('pct', 0)}%)."

    if budget_info.get("alert_msg"):
        msg += f"\n{budget_info['alert_msg']}"

    msg += "\n¿Correcto?"
    return msg


def format_split_confirmation(receipt: dict) -> str:
    """Format the Telegram message for a split receipt with tax questions."""
    total = sum(tx["amount"] for tx in receipt.get("transactions", []))
    merchant = receipt["transactions"][0]["merchant"] if receipt["transactions"] else "Unknown"
    n_groups = len(receipt["transactions"])

    auto_items = [tx for tx in receipt["transactions"] if not tx.get("needs_confirmation")]
    pending_items = [tx for tx in receipt["transactions"] if tx.get("needs_confirmation")]

    lines = [f"{merchant} ${total:.2f} — {n_groups} grupos detectados", ""]

    if auto_items:
        lines.append("Auto-registrado:")
        for tx in auto_items:
            item_desc = ", ".join(i["name"] for i in tx.get("items", [])[:3])
            lines.append(f"  ✔ ${tx['amount']:.2f} → {tx['category']} ({item_desc})")

    if pending_items:
        lines.append("")
        lines.append("¿Personal o Airbnb?")
        for i, tx in enumerate(pending_items, 1):
            item_desc = ", ".join(i_item["name"] for i_item in tx.get("items", [])[:3])
            reason = tx.get("confirmation_reason", "")
            lines.append(f"  {i}. ${tx['amount']:.2f} — {item_desc} ({reason})")
        lines.append("")
        lines.append('Responde: "todos airbnb", "1,3 airbnb 2 personal", o por número')

    return "\n".join(lines)
