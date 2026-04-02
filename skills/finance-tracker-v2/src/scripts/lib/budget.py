"""Budget tracking for Finance Tracker v2.

Cherry-picked status display logic from v1 budget.py.
"""

from datetime import date

from . import config as C


def _get_spending(month: str) -> dict[str, float]:
    """Get actual spending by category. Gracefully handles missing sheets."""
    try:
        from . import sheets
        sc = sheets.load_sheets_config()
        if sc:
            return sheets.get_month_spending_by_category(month)
    except Exception:
        pass
    return {}


def get_budget_status(month: str | None = None) -> dict:
    """Get per-category budget status. Returns structured dict."""
    if not month:
        month = date.today().strftime("%Y-%m")

    budgets = C.get_category_budgets()
    spending = _get_spending(month)
    categories = []
    total_budget = 0
    total_spent = 0

    for cat_name, cat_data in budgets.items():
        monthly = cat_data.get("monthly", 0) or 0
        spent = spending.get(cat_name, 0)
        remaining = monthly - spent
        pct = (spent / monthly * 100) if monthly > 0 else 0
        btype = cat_data.get("type", "variable")

        status = "ok"
        if monthly > 0:
            if pct >= 100:
                status = "over"
            elif pct >= 95:
                status = "critical"
            elif pct >= 80:
                status = "warning"

        categories.append({
            "category": cat_name,
            "type": btype,
            "budget": monthly,
            "spent": spent,
            "remaining": remaining,
            "pct": round(pct, 1),
            "status": status,
        })
        total_budget += monthly
        total_spent += spent

    return {
        "month": month,
        "categories": categories,
        "total_budget": round(total_budget, 2),
        "total_spent": round(total_spent, 2),
        "total_remaining": round(total_budget - total_spent, 2),
    }


def check_budget_alerts(category: str, amount: float) -> list[dict]:
    """Check if adding `amount` to `category` triggers budget alerts."""
    budgets = C.get_category_budgets()
    cat_data = budgets.get(category)
    if not cat_data or not cat_data.get("monthly"):
        return []

    monthly = cat_data["monthly"]
    month = date.today().strftime("%Y-%m")
    spending = _get_spending(month)
    spent = spending.get(category, 0)
    new_total = spent + amount
    pct = new_total / monthly * 100

    alerts = []
    threshold = cat_data.get("threshold", 0.8) * 100

    if pct >= 100:
        alerts.append({
            "level": "over",
            "message": f"{category}: ${new_total:.2f}/${monthly:.2f} ({pct:.0f}%) — OVER BUDGET",
        })
    elif pct >= 95:
        alerts.append({
            "level": "critical",
            "message": f"{category}: ${new_total:.2f}/${monthly:.2f} ({pct:.0f}%) — almost at limit",
        })
    elif pct >= threshold:
        alerts.append({
            "level": "warning",
            "message": f"{category}: ${new_total:.2f}/${monthly:.2f} ({pct:.0f}%) — approaching limit",
        })

    return alerts


def format_budget_status(status: dict) -> str:
    """Format budget status as human-readable text."""
    lang = C.get_language()
    lines = []
    for cat in status["categories"]:
        if cat["budget"] <= 0 and cat["spent"] <= 0:
            continue
        icon = {"ok": "+", "warning": "!", "critical": "!!", "over": "X"}.get(cat["status"], " ")
        btype = "(F)" if cat["type"] == "fixed" else "(V)"
        lines.append(
            f"  [{icon}] {cat['category']} {btype}: "
            f"${cat['spent']:,.2f}/${cat['budget']:,.2f} ({cat['pct']:.0f}%)"
        )

    header = "Estado del Presupuesto" if lang == "es" else "Budget Status"
    month = status["month"]
    summary = "\n".join(lines) if lines else "  (no budgets with activity)"
    total_line = (f"Total: ${status['total_spent']:,.2f}/${status['total_budget']:,.2f} "
                  f"(remaining: ${status['total_remaining']:,.2f})")
    return f"{header} ({month}):\n{summary}\n\n{total_line}"
