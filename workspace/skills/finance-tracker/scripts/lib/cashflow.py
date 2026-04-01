"""Module 8: Daily Cashflow — 'how much can I safely spend today?'"""

from datetime import datetime, date
from . import config as C
from .payments import payment_summary_14d
from .budget import budget_status_brief


def daily_cashflow() -> str:
    """Generate the daily cashflow message."""
    today = date.today()
    balance_info = C.get_balance_info()
    lang = C.get_language()

    available = balance_info.get("available", 0)
    upcoming_total, upcoming_details = payment_summary_14d()
    daily_savings = _daily_savings_quota()
    days_to_pay = _days_to_payday(balance_info)

    if days_to_pay > 0:
        safe_daily = (available - upcoming_total) / days_to_pay - daily_savings
    else:
        safe_daily = available - upcoming_total - daily_savings

    safe_daily = round(safe_daily, 2)

    # Risk level
    if lang == "es":
        if safe_daily > 100:
            risk_msg = ""
        elif safe_daily >= 30:
            risk_msg = "\n⚠ Cuidado con gastos grandes esta semana."
        elif safe_daily >= 0:
            risk_msg = "\n🔴 APRETADO. Solo gastos esenciales hasta próximo pago."
        else:
            risk_msg = "\n🚨 NO ALCANZA. Recorta o difiere un pago."
    else:
        if safe_daily > 100:
            risk_msg = ""
        elif safe_daily >= 30:
            risk_msg = "\n⚠ Watch out for big purchases this week."
        elif safe_daily >= 0:
            risk_msg = "\n🔴 TIGHT. Essential spending only until next payday."
        else:
            risk_msg = "\n🚨 NOT ENOUGH. Cut spending or defer a payment."

    # Payday info with estimated amount
    expected_pay = balance_info.get("expected_paycheck", 0)
    if lang == "es":
        payday_line = f"Próximo ingreso: {days_to_pay} días"
        if expected_pay:
            payday_line += f" (~${expected_pay:,.0f} estimado)"
    else:
        payday_line = f"Next income: {days_to_pay} days"
        if expected_pay:
            payday_line += f" (~${expected_pay:,.0f} estimated)"

    if lang == "es":
        lines = [
            f"BUENOS DÍAS — {today.strftime('%b %d, %Y')}",
            "",
            f"Saldo disponible: ${available:,.0f}",
            f"Pagos próximos 14d: ${upcoming_total:,.0f} ({', '.join(upcoming_details)})" if upcoming_details else "Pagos próximos 14d: $0",
            f"Ahorro viajes hoy: ${daily_savings:.0f}",
            payday_line,
            "",
            f"→ Puedes gastar máximo ${max(safe_daily, 0):.0f}/día",
            risk_msg,
            "",
            budget_status_brief(),
            "",
            _savings_status(),
        ]
    else:
        lines = [
            f"GOOD MORNING — {today.strftime('%b %d, %Y')}",
            "",
            f"Available balance: ${available:,.0f}",
            f"Upcoming payments 14d: ${upcoming_total:,.0f} ({', '.join(upcoming_details)})" if upcoming_details else "Upcoming payments 14d: $0",
            f"Savings quota today: ${daily_savings:.0f}",
            payday_line,
            "",
            f"→ Safe to spend: ${max(safe_daily, 0):.0f}/day",
            risk_msg,
            "",
            budget_status_brief(),
            "",
            _savings_status(),
        ]

    return "\n".join(lines)


def update_balance(amount: float):
    """Update the available cash balance."""
    config = C._load_tracker_config()
    config["balance"]["available"] = amount
    config["balance"]["last_updated"] = datetime.now().isoformat()
    C.save_tracker_config(config)
    lang = C.get_language()
    if lang == "es":
        return f"Saldo actualizado: ${amount:,.2f}"
    return f"Balance updated: ${amount:,.2f}"


def update_savings(goal: str, amount: float):
    """Log savings toward a goal."""
    config = C._load_tracker_config()
    savings = config.get("savings", [])
    lang = C.get_language()
    for s in savings:
        if s["goal"].lower() == goal.lower():
            s["saved"] += amount
            C.save_tracker_config(config)
            remaining = s["target"] - s["saved"]
            days_left = (date.fromisoformat(s["deadline"]) - date.today()).days
            daily = remaining / max(days_left, 1)
            if lang == "es":
                return (
                    f"Ahorro registrado: ${amount:.0f} para {s['goal']}. "
                    f"Total: ${s['saved']:.0f}/${s['target']}. "
                    f"Faltan ${remaining:.0f} en {days_left} días (${daily:.0f}/día)."
                )
            return (
                f"Savings logged: ${amount:.0f} for {s['goal']}. "
                f"Total: ${s['saved']:.0f}/${s['target']}. "
                f"${remaining:.0f} remaining in {days_left} days (${daily:.0f}/day)."
            )
    if lang == "es":
        return f"Meta '{goal}' no encontrada."
    return f"Goal '{goal}' not found."


def update_savings_target(goal: str, target: float):
    """Update a savings goal target."""
    config = C._load_tracker_config()
    savings = config.get("savings", [])
    lang = C.get_language()
    for s in savings:
        if s["goal"].lower() == goal.lower():
            s["target"] = target
            C.save_tracker_config(config)
            if lang == "es":
                return f"Meta {s['goal']} actualizada: ${target:,.0f}"
            return f"Goal {s['goal']} updated: ${target:,.0f}"
    if lang == "es":
        return f"Meta '{goal}' no encontrada."
    return f"Goal '{goal}' not found."


def update_payday(schedule: str, amount: float = 0, dates: list[int] = None):
    """Update pay schedule and expected paycheck amount."""
    config = C._load_tracker_config()
    config["balance"]["pay_schedule"] = schedule
    if amount:
        config["balance"]["expected_paycheck"] = amount
    if dates:
        config["balance"]["pay_dates"] = dates
    C.save_tracker_config(config)

    pay_dates = config["balance"].get("pay_dates", [])
    msg = f"Payday: {schedule}"
    if amount:
        msg += f", ~${amount:,.0f}/pay"
    if pay_dates:
        msg += f", days {pay_dates}"
    return msg


def _daily_savings_quota() -> float:
    """Calculate total daily savings needed across all goals."""
    savings = C.get_savings()
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


def _days_to_payday(balance_info: dict) -> int:
    """Calculate days until next payday."""
    today = date.today()
    pay_dates = balance_info.get("pay_dates", [15, 30])

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
    savings = C.get_savings()
    today = date.today()
    lang = C.get_language()
    header = "Metas de viaje:" if lang == "es" else "Savings goals:"
    lines = [header]
    for s in savings:
        remaining = s["target"] - s.get("saved", 0)
        days_left = max((date.fromisoformat(s["deadline"]) - today).days, 1)
        daily = remaining / days_left
        lines.append(
            f"  {s['goal']} ({s['deadline']}): "
            f"${s.get('saved', 0):,.0f}/${s['target']:,.0f} — ${daily:.0f}/{'día' if lang == 'es' else 'day'}"
        )
    return "\n".join(lines)
