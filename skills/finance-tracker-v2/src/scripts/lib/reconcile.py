"""Bank CSV reconciliation and import for Finance Tracker v2.

Cherry-picked bank detection + matching from v1 reconcile.py.
"""

import csv
import io
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config as C
from .merchant_rules import normalize_merchant, lookup_merchant, save_merchant_rule


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


# ── CSV Import ────────────────────────────────────────

_PAYMENT_KEYWORDS = {"payment", "pago", "epay", "autopay", "auto pay", "thank you"}
_TRANSFER_KEYWORDS = {"transfer", "zelle", "cash app", "paypal", "venmo", "xfer"}
_RETURN_KEYWORDS = {"return", "refund", "credit", "reversal", "adjustment", "devolucion"}


def _classify_csv_tx(row: dict) -> tuple[str, str]:
    """Classify a CSV row: (type, category). Type: expense|income|payment|transfer|return."""
    merchant = (row.get("merchant") or "").lower()
    type_raw = (row.get("type_raw") or "").lower()
    is_debit = row.get("is_debit", True)
    combined = f"{merchant} {type_raw}"

    # Payments first
    if any(kw in combined for kw in _PAYMENT_KEYWORDS):
        return "payment", "Debt Payment"
    # Transfers
    if any(kw in combined for kw in _TRANSFER_KEYWORDS):
        return "transfer", "Transfer"
    # Returns / credits (non-debit)
    if not is_debit:
        if any(kw in combined for kw in _RETURN_KEYWORDS):
            return "return", "Refund"
        return "income", "Income"
    # Normal expense
    return "expense", ""


def import_csv(csv_path: str, dry_run: bool = False) -> dict:
    """Import bank CSV as transactions.

    Handles: purchases, returns/credits, payments, adjustments, reversals.
    """
    bank = detect_bank_format(csv_path)
    csv_rows = _parse_rows(csv_path, bank)
    if not csv_rows:
        return {"error": True, "message": "No transactions found in CSV", "bank": bank}

    transactions = []
    for row in csv_rows:
        tx_type, default_cat = _classify_csv_tx(row)
        merchant_raw = row.get("merchant", "Unknown")
        norm = normalize_merchant(merchant_raw)
        amount = row.get("amount", 0)

        # Determine category from merchant rules
        category = default_cat
        rule = lookup_merchant(merchant_raw)
        if rule and rule.get("category") and tx_type == "expense":
            category = rule["category"]
        elif tx_type == "expense":
            category = "Other"

        # Build transaction
        tx = {
            "date": row.get("date", date.today().isoformat()),
            "amount": amount if tx_type != "return" else -amount,
            "merchant": merchant_raw,
            "category": category,
            "subcategory": "",
            "card": bank.title(),
            "input_method": "csv",
            "confidence": 0.7 if rule else 0.5,
            "matched": False,
            "source": "csv",
            "notes": f"Imported from {bank} CSV",
            "timestamp": datetime.now().isoformat(),
            "month": row.get("date", "")[:7],
            "tax_deductible": False,
            "tax_category": "none",
            "type": tx_type,
        }
        transactions.append(tx)

    summary = {
        "bank": bank,
        "total_rows": len(csv_rows),
        "imported": len(transactions),
        "by_type": {},
        "dry_run": dry_run,
    }
    for tx in transactions:
        t = tx["type"]
        summary["by_type"].setdefault(t, {"count": 0, "total": 0})
        summary["by_type"][t]["count"] += 1
        summary["by_type"][t]["total"] += abs(tx["amount"])

    # Round totals
    for t in summary["by_type"]:
        summary["by_type"][t]["total"] = round(summary["by_type"][t]["total"], 2)

    if not dry_run:
        try:
            from . import sheets
            written = sheets.write_transactions(transactions)
            summary["written_to_sheets"] = written
        except Exception as e:
            summary["written_to_sheets"] = 0
            summary["sheets_error"] = str(e)

    return summary
