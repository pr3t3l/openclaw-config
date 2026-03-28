"""Module 4: Payment Reminder — alerts before due dates + promo APR warnings."""

from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from . import config as C


def check_payments() -> list[str]:
    """Check all payments and return alerts for today."""
    payments = C.load_payments()
    today = date.today()
    alerts = []

    for p in payments:
        days_until = _days_until_due(p["due_day"], today)
        name = p["name"]
        amount = p["amount"]
        autopay = "Autopay activo." if p.get("autopay") else "⚠ Sin autopay."

        if days_until == 0:
            alerts.append(f"HOY VENCE: {name} ${amount}. {autopay}")
        elif days_until == 1:
            alerts.append(f"MAÑANA vence {name} (${amount}). Verifica fondos. {autopay}")
        elif days_until == 3:
            alerts.append(f"Recordatorio: {name} (${amount}) vence el día {p['due_day']} (en 3 días). {autopay}")

        # Promo APR expiry warnings
        promo = p.get("promo_expiry")
        if promo:
            promo_date = date.fromisoformat(promo)
            days_to_promo = (promo_date - today).days
            if days_to_promo in [60, 30, 7]:
                alerts.append(
                    f"⚠ PROMO: {name} — tasa promocional de {p['apr']}% "
                    f"expira en {days_to_promo} días ({promo}). "
                    f"Prepara un plan de pago."
                )
            elif days_to_promo == 0:
                alerts.append(
                    f"🔴 HOY EXPIRA la tasa promo de {name} ({p['apr']}%). "
                    f"La tasa normal entra en efecto."
                )

    return alerts


def payment_summary_14d() -> tuple[float, list[str]]:
    """Sum of payments due in next 14 days + list of details."""
    payments = C.load_payments()
    today = date.today()
    total = 0
    details = []

    for p in payments:
        days = _days_until_due(p["due_day"], today)
        if 0 <= days <= 14:
            total += p["amount"]
            details.append(f"{p['name']} ${p['amount']} d{p['due_day']}")

    return total, details


def _days_until_due(due_day: int, today: date) -> int:
    """Calculate days until next due date."""
    this_month_due = today.replace(day=min(due_day, 28))
    if this_month_due >= today:
        return (this_month_due - today).days
    # Next month
    next_month = today + relativedelta(months=1)
    next_due = next_month.replace(day=min(due_day, 28))
    return (next_due - today).days
