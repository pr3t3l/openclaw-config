"""Bank CSV reconciliation for Finance Tracker v2.

Cherry-picked bank detection + matching from v1 reconcile.py.
"""

import csv
import io
import re
from datetime import date, timedelta
from pathlib import Path

from . import config as C
from .merchant_rules import normalize_merchant


# ── Bank format detection ─────────────────────────────

def detect_bank_format(csv_path: str) -> str:
    """Auto-detect bank from CSV headers. Returns: chase, discover, citi, wells, amex, unknown."""
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        first_line = f.readline().lower().strip()

    if "memo" in first_line and "type" in first_line:
        return "chase"
    if "trans. date" in first_line:
        return "discover"
    if "extended details" in first_line:
        return "citi"
    if first_line.startswith('"') and '"*"' in first_line:
        return "wells"
    if "reference" in first_line and "amount" in first_line:
        return "amex"
    return "unknown"


# ── CSV row parsers ───────────────────────────────────

def _parse_rows(csv_path: str, bank: str) -> list[dict]:
    """Parse CSV rows into normalized transaction dicts."""
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            parsed = _parse_row(row, bank)
            if parsed and parsed.get("amount"):
                rows.append(parsed)
    return rows


def _parse_row(row: dict, bank: str) -> dict | None:
    """Parse a single CSV row based on bank format."""
    try:
        if bank == "chase":
            return {
                "date": row.get("Transaction Date", row.get("Posting Date", "")),
                "merchant": row.get("Description", ""),
                "amount": abs(float(row.get("Amount", 0))),
                "is_debit": float(row.get("Amount", 0)) < 0,
                "type_raw": row.get("Type", ""),
            }
        if bank == "discover":
            return {
                "date": row.get("Trans. Date", ""),
                "merchant": row.get("Description", ""),
                "amount": abs(float(row.get("Amount", 0))),
                "is_debit": float(row.get("Amount", 0)) > 0,
                "type_raw": row.get("Category", ""),
            }
        if bank == "wells":
            amount = float(row.get("Amount", 0))
            return {
                "date": row.get("Date", ""),
                "merchant": row.get("Description", ""),
                "amount": abs(amount),
                "is_debit": amount < 0,
                "type_raw": "",
            }
        if bank == "citi":
            debit = float(row.get("Debit", 0) or 0)
            credit = float(row.get("Credit", 0) or 0)
            return {
                "date": row.get("Date", ""),
                "merchant": row.get("Description", ""),
                "amount": debit or credit,
                "is_debit": debit > 0,
                "type_raw": "",
            }
        # Generic fallback
        amount_val = 0
        for key in ("Amount", "amount", "Debit", "Credit"):
            if row.get(key):
                try:
                    amount_val = abs(float(row[key]))
                    break
                except ValueError:
                    pass
        return {
            "date": row.get("Date", row.get("date", "")),
            "merchant": row.get("Description", row.get("description", row.get("Merchant", ""))),
            "amount": amount_val,
            "is_debit": True,
            "type_raw": "",
        }
    except (ValueError, KeyError):
        return None


# ── Match scoring ─────────────────────────────────────

def _match_score(csv_row: dict, logged_tx: dict) -> int:
    """Score a match between CSV row and logged transaction. 0-3 scale."""
    score = 0
    # Amount must match (required)
    csv_amt = round(csv_row.get("amount", 0), 2)
    tx_amt = round(float(logged_tx.get("amount", 0)), 2)
    if csv_amt != tx_amt:
        return 0
    score = 1

    # Date within ±2 days
    try:
        csv_date = _parse_date(csv_row.get("date", ""))
        tx_date = _parse_date(logged_tx.get("date", ""))
        if csv_date and tx_date and abs((csv_date - tx_date).days) <= 2:
            score += 1
    except Exception:
        pass

    # Merchant fuzzy match
    csv_merchant = normalize_merchant(csv_row.get("merchant", ""))
    tx_merchant = normalize_merchant(logged_tx.get("merchant", ""))
    if csv_merchant and tx_merchant and (csv_merchant in tx_merchant or tx_merchant in csv_merchant):
        score += 1

    return score


def _parse_date(d: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            return date.fromisoformat(d) if "-" in d and len(d) == 10 else __import__("datetime").datetime.strptime(d, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


# ── Reconciliation ────────────────────────────────────

def reconcile_csv(csv_path: str) -> dict:
    """Match CSV transactions against logged transactions."""
    bank = detect_bank_format(csv_path)
    csv_rows = _parse_rows(csv_path, bank)

    # Get logged transactions
    try:
        from . import sheets
        logged = sheets.read_transactions()
    except Exception:
        logged = []

    matched = []
    unmatched_bank = []
    unmatched_tracker = list(range(len(logged)))
    used_logged = set()

    for csv_row in csv_rows:
        best_score = 0
        best_idx = -1
        for i, tx in enumerate(logged):
            if i in used_logged:
                continue
            score = _match_score(csv_row, tx)
            if score > best_score:
                best_score = score
                best_idx = i

        if best_score >= 2 and best_idx >= 0:
            matched.append({
                "csv": csv_row,
                "logged": logged[best_idx],
                "score": best_score,
            })
            used_logged.add(best_idx)
            if best_idx in unmatched_tracker:
                unmatched_tracker.remove(best_idx)
        else:
            unmatched_bank.append(csv_row)

    return {
        "bank": bank,
        "csv_rows": len(csv_rows),
        "matched": len(matched),
        "unmatched_bank": len(unmatched_bank),
        "unmatched_tracker": len(unmatched_tracker),
        "unmatched_bank_rows": unmatched_bank[:20],
        "unmatched_tracker_rows": [logged[i] for i in unmatched_tracker[:20]] if logged else [],
    }
