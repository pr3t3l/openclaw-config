"""Debt payoff strategy calculator for Finance Tracker v2.

Avalanche (highest APR first) vs Snowball (smallest balance first).
"""

import copy
from datetime import date, timedelta

from . import config as C


def calculate_avalanche(debts: list[dict], extra_monthly: float = 0) -> dict:
    """Highest APR first. Returns timeline and total interest."""
    return _simulate_payoff(debts, extra_monthly, strategy="avalanche")


def calculate_snowball(debts: list[dict], extra_monthly: float = 0) -> dict:
    """Smallest balance first. Returns timeline and total interest."""
    return _simulate_payoff(debts, extra_monthly, strategy="snowball")


def _simulate_payoff(debts: list[dict], extra_monthly: float, strategy: str) -> dict:
    """Simulate month-by-month debt payoff."""
    if not debts:
        return {"months": 0, "total_interest": 0, "total_paid": 0, "timeline": []}

    # Deep copy to avoid mutating
    active = []
    for d in debts:
        active.append({
            "name": d["name"],
            "balance": d.get("balance", 0),
            "apr": d.get("apr", 0),
            "minimum": d.get("minimum_payment", 0),
        })

    total_interest = 0
    total_paid = 0
    months = 0
    timeline = []
    max_months = 360  # 30 year cap

    while any(d["balance"] > 0 for d in active) and months < max_months:
        months += 1
        month_interest = 0
        month_paid = 0

        # Calculate interest
        for d in active:
            if d["balance"] > 0:
                interest = d["balance"] * (d["apr"] / 100) / 12
                d["balance"] += interest
                month_interest += interest

        # Sort for target selection
        targets = [d for d in active if d["balance"] > 0]
        if strategy == "avalanche":
            targets.sort(key=lambda d: -d["apr"])
        else:  # snowball
            targets.sort(key=lambda d: d["balance"])

        # Pay minimums on all
        remaining_extra = extra_monthly
        for d in active:
            if d["balance"] > 0:
                payment = min(d["minimum"], d["balance"])
                d["balance"] -= payment
                month_paid += payment

        # Apply extra to target
        if targets and remaining_extra > 0:
            target = targets[0]
            if target["balance"] > 0:
                payment = min(remaining_extra, target["balance"])
                target["balance"] -= payment
                month_paid += payment

        total_interest += month_interest
        total_paid += month_paid

        # Record milestones
        if months <= 3 or months % 6 == 0 or all(d["balance"] <= 0 for d in active):
            timeline.append({
                "month": months,
                "remaining_balance": round(sum(max(d["balance"], 0) for d in active), 2),
                "total_interest_so_far": round(total_interest, 2),
            })

    return {
        "strategy": strategy,
        "months": months,
        "total_interest": round(total_interest, 2),
        "total_paid": round(total_paid, 2),
        "timeline": timeline,
    }


def compare_strategies(debts: list[dict] | None = None,
                       extra_monthly: float = 0) -> dict:
    """Side-by-side comparison of avalanche vs snowball."""
    if debts is None:
        config = C._load_tracker_config()
        debts = config.get("debts", [])
    if not debts:
        return {"message": "No debts to analyze.", "debts": []}

    avalanche = calculate_avalanche(debts, extra_monthly)
    snowball = calculate_snowball(debts, extra_monthly)

    interest_saved = snowball["total_interest"] - avalanche["total_interest"]
    months_diff = snowball["months"] - avalanche["months"]

    return {
        "debts": [{"name": d["name"], "balance": d.get("balance", 0),
                    "apr": d.get("apr", 0), "minimum": d.get("minimum_payment", 0)} for d in debts],
        "extra_monthly": extra_monthly,
        "avalanche": avalanche,
        "snowball": snowball,
        "interest_saved_by_avalanche": round(interest_saved, 2),
        "months_faster_avalanche": months_diff,
        "recommendation": "avalanche" if interest_saved > 50 else "either",
    }


def format_debt_strategy(comparison: dict) -> str:
    """Format debt strategy comparison as human-readable text."""
    lang = C.get_language()
    if not comparison.get("debts"):
        return "No debts to analyze." if lang == "en" else "Sin deudas para analizar."

    lines = []
    if lang == "es":
        lines.append("Estrategia de Pago de Deudas")
    else:
        lines.append("Debt Payoff Strategy")
    lines.append("=" * 35)

    lines.append(f"\nDebts:")
    for d in comparison["debts"]:
        lines.append(f"  {d['name']}: ${d['balance']:,.2f} @ {d['apr']}% APR, min ${d['minimum']:.2f}")

    av = comparison["avalanche"]
    sn = comparison["snowball"]

    lines.append(f"\nAvalanche (highest APR first):")
    lines.append(f"  Months: {av['months']} | Interest: ${av['total_interest']:,.2f}")

    lines.append(f"\nSnowball (smallest balance first):")
    lines.append(f"  Months: {sn['months']} | Interest: ${sn['total_interest']:,.2f}")

    saved = comparison["interest_saved_by_avalanche"]
    if saved > 0:
        lines.append(f"\nAvalanche saves: ${saved:,.2f} in interest, {comparison['months_faster_avalanche']} months faster")

    rec = comparison["recommendation"]
    if rec == "avalanche":
        lines.append(f"\nRecommendation: Avalanche — saves the most money.")
    else:
        lines.append(f"\nRecommendation: Either works — similar results. Snowball gives quicker wins.")

    return "\n".join(lines)
