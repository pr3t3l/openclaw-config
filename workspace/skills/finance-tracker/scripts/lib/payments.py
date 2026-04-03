"""Payment calendar and reminders for Finance Tracker v2.

Cherry-picked from v1 payments.py.
"""

from datetime import date, timedelta

from . import config as C


def _days_until_due(due_day: int, today: date | None = None) -> int:
    """Calculate days until a due day this month or next."""
    today = today or date.today()
    try:
        this_month = today.replace(day=min(due_day, 28))
    except ValueError:
        this_month = today.replace(day=28)

    if this_month >= today:
        return (this_month - today).days

    # Next month
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    try:
        next_due = next_month.replace(day=min(due_day, 28))
    except ValueError:
        next_due = next_month.replace(day=28)
    return (next_due - today).days


def get_upcoming_payments(days: int = 7) -> list[dict]:
    """Get payments due within N days."""
    today = date.today()
    payments = C.get_payments()
    upcoming = []

    for p in payments:
        due_day = p.get("due_day", 1)
        days_until = _days_until_due(due_day, today)

        if 0 <= days_until <= days:
            upcoming.append({
                "name": p["name"],
                "amount": p["amount"],
                "due_day": due_day,
                "days_until": days_until,
                "frequency": p.get("frequency", "monthly"),
                "autopay": p.get("autopay", False),
                "apr": p.get("apr", 0),
            })

    upcoming.sort(key=lambda x: x["days_until"])
    return upcoming


def check_due_soon(days: int = 3) -> list[dict]:
    """Get payments due within N days with alert messages."""
    today = date.today()
    lang = C.get_language()
    payments = C.get_payments()
    alerts = []

    for p in payments:
        due_day = p.get("due_day", 1)
        days_until = _days_until_due(due_day, today)
        amount = p["amount"]
        name = p["name"]
        autopay = p.get("autopay", False)

        if days_until == 0:
            ap = " (autopay)" if autopay else " — check funds!"
            if lang == "es":
                msg = f"HOY VENCE: {name} ${amount:,.2f}{ap}"
            else:
                msg = f"DUE TODAY: {name} ${amount:,.2f}{ap}"
            alerts.append({"name": name, "days": 0, "message": msg, "level": "urgent"})
        elif days_until == 1:
            if lang == "es":
                msg = f"MAÑANA vence {name} ${amount:,.2f}"
            else:
                msg = f"DUE TOMORROW: {name} ${amount:,.2f}"
            alerts.append({"name": name, "days": 1, "message": msg, "level": "warning"})
        elif days_until <= days:
            if lang == "es":
                msg = f"Recordatorio: {name} ${amount:,.2f} en {days_until} días"
            else:
                msg = f"Reminder: {name} ${amount:,.2f} in {days_until} days"
            alerts.append({"name": name, "days": days_until, "message": msg, "level": "info"})

        # Promo APR expiry warnings
        promo = p.get("promo_expiry")
        if promo:
            try:
                promo_date = date.fromisoformat(promo)
                promo_days = (promo_date - today).days
                if promo_days in (60, 30, 7, 0):
                    apr = p.get("apr", 0)
                    if lang == "es":
                        msg = f"PROMO APR expira en {promo_days} días: {name} (APR sube a {apr}%)"
                    else:
                        msg = f"PROMO APR expires in {promo_days} days: {name} (APR jumps to {apr}%)"
                    alerts.append({"name": name, "days": promo_days, "message": msg, "level": "promo"})
            except ValueError:
                pass

    return alerts


def sinking_fund_summary() -> dict:
    """Show sinking fund provisions for non-monthly bills."""
    payments = C.get_payments()
    funds = []
    total_monthly = 0

    for p in payments:
        freq = p.get("frequency", "monthly")
        if freq == "monthly":
            continue
        amount = p["amount"]
        monthly_provision = {
            "quarterly": amount / 3,
            "semi_annual": amount / 6,
            "annual": amount / 12,
        }.get(freq, 0)

        if monthly_provision > 0:
            funds.append({
                "name": p["name"],
                "amount": amount,
                "frequency": freq,
                "monthly_provision": round(monthly_provision, 2),
            })
            total_monthly += monthly_provision

    return {
        "sinking_funds": funds,
        "total_monthly_provision": round(total_monthly, 2),
        "total_daily_provision": round(total_monthly / 30, 2),
    }
