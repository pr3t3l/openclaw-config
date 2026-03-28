"""Module 8: Daily Cashflow — 'how much can I safely spend today?'"""

from datetime import datetime, date
from . import config as C
from .payments import payment_summary_14d
from .budget import budget_status_brief


def daily_cashflow() -> str:
    """Generate the daily cashflow message."""
    today = date.today()
    budgets = C.load_budgets()

    available = budgets.get("available_balance", 0)
    upcoming_total, upcoming_details = payment_summary_14d()
    daily_savings = _daily_savings_quota()
    days_to_pay = _days_to_payday(budgets)

    if days_to_pay > 0:
        safe_daily = (available - upcoming_total) / days_to_pay - daily_savings
    else:
        safe_daily = available - upcoming_total - daily_savings

    safe_daily = round(safe_daily, 2)

    # Risk level
    if safe_daily > 100:
        risk_msg = ""
    elif safe_daily >= 30:
        risk_msg = "\n⚠ Cuidado con gastos grandes esta semana."
    elif safe_daily >= 0:
        risk_msg = "\n🔴 APRETADO. Solo gastos esenciales hasta próximo pago."
    else:
        risk_msg = "\n🚨 NO ALCANZA. Recorta o difiere un pago."

    lines = [
        f"BUENOS DÍAS — {today.strftime('%b %d, %Y')}",
        "",
        f"Saldo disponible: ${available:,.0f}",
        f"Pagos próximos 14d: ${upcoming_total:,.0f} ({', '.join(upcoming_details)})" if upcoming_details else "Pagos próximos 14d: $0",
        f"Ahorro viajes hoy: ${daily_savings:.0f}",
        f"Próximo pago: {days_to_pay} días",
        "",
        f"→ Puedes gastar máximo ${max(safe_daily, 0):.0f}/día",
        risk_msg,
        "",
        budget_status_brief(),
        "",
        _savings_status(),
    ]

    return "\n".join(lines)


def update_balance(amount: float):
    """Update the available cash balance."""
    budgets = C.load_budgets()
    budgets["available_balance"] = amount
    budgets["last_balance_update"] = datetime.now().isoformat()
    C.save_json(C.CONFIG_DIR / "budgets.json", budgets)
    return f"Saldo actualizado: ${amount:,.2f}"


def update_savings(goal: str, amount: float):
    """Log savings toward a goal."""
    savings = C.load_savings()
    for s in savings:
        if s["goal"].lower() == goal.lower():
            s["saved"] += amount
            C.save_json(C.CONFIG_DIR / "savings.json", savings)
            remaining = s["target"] - s["saved"]
            days_left = (date.fromisoformat(s["deadline"]) - date.today()).days
            daily = remaining / max(days_left, 1)
            return (
                f"Ahorro registrado: ${amount:.0f} para {s['goal']}. "
                f"Total: ${s['saved']:.0f}/${s['target']}. "
                f"Faltan ${remaining:.0f} en {days_left} días (${daily:.0f}/día)."
            )
    return f"Meta '{goal}' no encontrada."


def update_savings_target(goal: str, target: float):
    """Update a savings goal target."""
    savings = C.load_savings()
    for s in savings:
        if s["goal"].lower() == goal.lower():
            s["target"] = target
            C.save_json(C.CONFIG_DIR / "savings.json", savings)
            return f"Meta {s['goal']} actualizada: ${target:,.0f}"
    return f"Meta '{goal}' no encontrada."


def _daily_savings_quota() -> float:
    """Calculate total daily savings needed across all goals."""
    savings = C.load_savings()
    today = date.today()
    total = 0
    for s in savings:
        remaining = s["target"] - s.get("saved", 0)
        if remaining <= 0:
            continue
        days_left = (date.fromisoformat(s["deadline"]) - today).days
        if days_left > 0:
            total += remaining / days_left
    return round(total, 2)


def _days_to_payday(budgets: dict) -> int:
    """Calculate days until next payday."""
    today = date.today()
    pay_dates = budgets.get("pay_dates", [15, 30])

    for d in sorted(pay_dates):
        pay_day = today.replace(day=min(d, 28))
        if pay_day > today:
            return (pay_day - today).days

    # Next month's first pay date
    from dateutil.relativedelta import relativedelta
    next_month = today + relativedelta(months=1)
    next_pay = next_month.replace(day=min(pay_dates[0], 28))
    return (next_pay - today).days


def _savings_status() -> str:
    """Format savings goals status."""
    savings = C.load_savings()
    today = date.today()
    lines = ["Metas de viaje:"]
    for s in savings:
        remaining = s["target"] - s.get("saved", 0)
        days_left = max((date.fromisoformat(s["deadline"]) - today).days, 1)
        daily = remaining / days_left
        lines.append(
            f"  {s['goal']} ({s['deadline']}): "
            f"${s.get('saved', 0):,.0f}/${s['target']:,.0f} — ${daily:.0f}/día"
        )
    return "\n".join(lines)
