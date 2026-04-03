"""Safe-to-spend calculator for Finance Tracker v2.

Formula: balance - upcoming_bills - debt_payments - savings - sinking_funds
Cherry-picked from v1 cashflow.py.
"""

from datetime import date, timedelta

from . import config as C


def _days_to_payday(balance_info: dict) -> int:
    """Calculate days until next payday."""
    today = date.today()
    pay_dates = balance_info.get("pay_dates", [15, 30])
    if not pay_dates:
        return 14  # default assumption

    for d in sorted(pay_dates):
        try:
            pay_day = today.replace(day=min(d, 28))
        except ValueError:
            pay_day = today.replace(day=28)
        if pay_day > today:
            return (pay_day - today).days

    # Next month
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    first_pay = min(pay_dates[0], 28)
    try:
        next_pay = next_month.replace(day=first_pay)
    except ValueError:
        next_pay = next_month.replace(day=28)
    return (next_pay - today).days


def _upcoming_bills(days: int = 14) -> tuple[float, list[dict]]:
    """Sum bills due in the next N days. Handles non-monthly frequencies."""
    today = date.today()
    payments = C.get_payments()
    total = 0.0
    upcoming = []

    for p in payments:
        due_day = p.get("due_day", 1)
        freq = p.get("frequency", "monthly")
        amount = p.get("amount", 0)

        # Check if due within window
        try:
            due_date = today.replace(day=min(due_day, 28))
        except ValueError:
            due_date = today.replace(day=28)
        if due_date < today:
            if today.month == 12:
                due_date = due_date.replace(year=today.year + 1, month=1)
            else:
                due_date = due_date.replace(month=today.month + 1)

        days_until = (due_date - today).days
        if 0 <= days_until <= days:
            # For non-monthly bills, only count if actually due this cycle
            if freq == "monthly" or _is_due_this_cycle(freq, today):
                total += amount
                upcoming.append({
                    "name": p["name"], "amount": amount,
                    "due_day": due_day, "days_until": days_until,
                    "frequency": freq,
                })

    return total, upcoming


def _is_due_this_cycle(freq: str, today: date) -> bool:
    """Rough check if a non-monthly bill is due this month."""
    month = today.month
    if freq == "quarterly":
        return month in (1, 4, 7, 10)
    if freq == "semi_annual":
        return month in (1, 7)
    if freq == "annual":
        return month == 1
    return True


def _sinking_fund_daily() -> float:
    """Calculate daily sinking fund provisions for non-monthly bills."""
    payments = C.get_payments()
    daily = 0.0
    for p in payments:
        freq = p.get("frequency", "monthly")
        amount = p.get("amount", 0)
        if freq == "quarterly":
            daily += amount / 90
        elif freq == "semi_annual":
            daily += amount / 180
        elif freq == "annual":
            daily += amount / 365
    return round(daily, 2)


def _daily_savings_quota() -> float:
    """Calculate total daily savings needed across all goals."""
    goals = C.get_savings()
    today = date.today()
    daily = 0.0
    for g in goals:
        remaining = g.get("target", 0) - g.get("saved", 0)
        if remaining <= 0:
            continue
        deadline = g.get("deadline")
        if deadline:
            try:
                dl = date.fromisoformat(deadline)
                days_left = (dl - today).days
                if days_left > 0:
                    daily += remaining / days_left
            except ValueError:
                pass
    return round(daily, 2)


def _debt_min_payments() -> float:
    """Sum minimum debt payments."""
    config = C._load_tracker_config()
    debts = config.get("debts", [])
    return sum(d.get("minimum_payment", 0) for d in debts)


def safe_to_spend() -> dict:
    """Calculate the daily safe-to-spend number."""
    balance_info = C.get_balance_info()
    available = balance_info.get("available", 0)
    days_to_pay = _days_to_payday(balance_info)

    upcoming_total, upcoming_list = _upcoming_bills(14)
    debt_min = _debt_min_payments()
    savings_daily = _daily_savings_quota()
    sinking_daily = _sinking_fund_daily()

    if days_to_pay > 0:
        safe_daily = (available - upcoming_total - debt_min) / days_to_pay - savings_daily - sinking_daily
    else:
        safe_daily = available - upcoming_total - debt_min - savings_daily - sinking_daily

    safe_daily = round(safe_daily, 2)

    # Risk level
    if safe_daily > 100:
        risk = "comfortable"
    elif safe_daily >= 30:
        risk = "caution"
    elif safe_daily >= 0:
        risk = "tight"
    else:
        risk = "negative"

    return {
        "safe_to_spend_daily": safe_daily,
        "balance": available,
        "days_to_payday": days_to_pay,
        "upcoming_bills_14d": round(upcoming_total, 2),
        "upcoming_bills": upcoming_list,
        "debt_min_payments": round(debt_min, 2),
        "daily_savings": savings_daily,
        "daily_sinking_fund": sinking_daily,
        "risk": risk,
    }


def update_balance(account: str, amount: float) -> dict:
    """Update account balance."""
    config = C._load_tracker_config()
    config["balance"]["available"] = amount
    config["balance"]["last_updated"] = date.today().isoformat()
    C.save_tracker_config(config)
    return {"updated": True, "account": account, "balance": amount}


def format_cashflow(data: dict) -> str:
    """Format safe-to-spend as human-readable text."""
    lang = C.get_language()
    risk_msgs = {
        "comfortable": "",
        "caution": "Watch out for big purchases" if lang == "en" else "Cuidado con compras grandes",
        "tight": "TIGHT — essentials only" if lang == "en" else "APRETADO — solo esenciales",
        "negative": "NOT ENOUGH — cut spending or defer" if lang == "en" else "NO ALCANZA — recorta o aplaza",
    }

    lines = []
    if lang == "es":
        lines.append(f"Seguro para gastar hoy: ${data['safe_to_spend_daily']:.2f}")
    else:
        lines.append(f"Safe to spend today: ${data['safe_to_spend_daily']:.2f}")

    risk_msg = risk_msgs.get(data["risk"], "")
    if risk_msg:
        lines.append(f"  {risk_msg}")

    lines.append(f"\nBalance: ${data['balance']:,.2f}")
    lines.append(f"Days to payday: {data['days_to_payday']}")
    lines.append(f"Upcoming bills (14d): ${data['upcoming_bills_14d']:,.2f}")

    if data["upcoming_bills"]:
        for b in data["upcoming_bills"]:
            lines.append(f"  {b['name']}: ${b['amount']:,.2f} (in {b['days_until']}d)")

    if data["daily_sinking_fund"] > 0:
        lines.append(f"Sinking fund provision: ${data['daily_sinking_fund']:.2f}/day")

    return "\n".join(lines)
