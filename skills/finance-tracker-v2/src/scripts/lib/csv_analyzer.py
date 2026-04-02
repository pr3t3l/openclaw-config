"""Bank CSV auto-detection for setup — detect recurring bills and income from bank data.

Powers the "send a CSV instead of listing bills manually" feature.
"""

import csv
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from .reconcile import detect_bank_format, _parse_rows


def analyze_csv(csv_path: str) -> dict:
    """Analyze 3-6 months of bank data to detect patterns.

    Returns: {recurring_bills, detected_income, subscriptions, summary}
    """
    bank = detect_bank_format(csv_path)
    rows = _parse_rows(csv_path, bank)

    if not rows:
        return {"error": "No transactions found in CSV", "bank": bank}

    # Group by merchant
    merchant_txs = defaultdict(list)
    for r in rows:
        merchant = r.get("merchant", "").strip()
        if merchant:
            merchant_txs[merchant].append(r)

    recurring = []
    subscriptions = []
    income_detected = []

    for merchant, txs in merchant_txs.items():
        if len(txs) < 2:
            continue

        amounts = [t["amount"] for t in txs]
        dates = [t.get("date", "") for t in txs]
        is_debit = txs[0].get("is_debit", True)

        # Check for consistent amount (within 10% tolerance)
        avg_amount = sum(amounts) / len(amounts)
        consistent = all(abs(a - avg_amount) / max(avg_amount, 1) < 0.1 for a in amounts)

        if not consistent:
            continue

        # Detect frequency
        freq = _detect_frequency(dates)

        if not is_debit:
            # Income pattern
            income_detected.append({
                "merchant": merchant,
                "amount": round(avg_amount, 2),
                "frequency": freq,
                "occurrences": len(txs),
            })
        elif avg_amount < 30 and freq == "monthly":
            # Subscription (small monthly charge)
            subscriptions.append({
                "merchant": merchant,
                "amount": round(avg_amount, 2),
                "frequency": freq,
                "occurrences": len(txs),
            })
        elif freq in ("monthly", "quarterly", "semi_annual", "annual"):
            # Recurring bill
            due_day = _estimate_due_day(dates)
            recurring.append({
                "merchant": merchant,
                "amount": round(avg_amount, 2),
                "frequency": freq,
                "due_day": due_day,
                "occurrences": len(txs),
            })

    # Sort by amount descending
    recurring.sort(key=lambda x: -x["amount"])
    subscriptions.sort(key=lambda x: -x["amount"])
    income_detected.sort(key=lambda x: -x["amount"])

    total_monthly_bills = sum(
        b["amount"] * {"monthly": 1, "quarterly": 1/3, "semi_annual": 1/6, "annual": 1/12}.get(b["frequency"], 1)
        for b in recurring
    )

    return {
        "bank": bank,
        "total_transactions": len(rows),
        "recurring_bills": recurring,
        "subscriptions": subscriptions,
        "detected_income": income_detected,
        "total_monthly_bills": round(total_monthly_bills, 2),
        "total_monthly_subscriptions": round(sum(s["amount"] for s in subscriptions), 2),
    }


def _detect_frequency(dates: list[str]) -> str:
    """Detect frequency from a list of date strings."""
    parsed = []
    for d in dates:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                from datetime import datetime
                parsed.append(datetime.strptime(d, fmt).date())
                break
            except (ValueError, TypeError):
                continue

    if len(parsed) < 2:
        return "unknown"

    parsed.sort()
    gaps = [(parsed[i+1] - parsed[i]).days for i in range(len(parsed)-1)]
    avg_gap = sum(gaps) / len(gaps)

    if avg_gap < 10:
        return "weekly"
    if 12 <= avg_gap <= 18:
        return "biweekly"
    if 25 <= avg_gap <= 35:
        return "monthly"
    if 80 <= avg_gap <= 100:
        return "quarterly"
    if 170 <= avg_gap <= 195:
        return "semi_annual"
    if 350 <= avg_gap <= 380:
        return "annual"
    return "irregular"


def _estimate_due_day(dates: list[str]) -> int:
    """Estimate which day of month a recurring charge typically hits."""
    days = []
    for d in dates:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                from datetime import datetime
                days.append(datetime.strptime(d, fmt).day)
                break
            except (ValueError, TypeError):
                continue
    if not days:
        return 1
    # Most common day
    counter = Counter(days)
    return counter.most_common(1)[0][0]
