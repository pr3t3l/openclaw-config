"""Module 6: Reconciliation Engine — match CSV uploads against logged receipts."""

import csv
import io
import re
from datetime import datetime, timedelta

from . import config as C
from . import sheets
from .rules import normalize_merchant, match_rules


def reconcile_csv(csv_content: str, bank: str = "auto") -> dict:
    """Reconcile a bank CSV against existing transactions."""
    if bank == "auto":
        bank = _detect_bank(csv_content)

    csv_rows = _parse_csv(csv_content, bank)
    month = _detect_month(csv_rows)
    existing = sheets.get_transactions_for_month(month) if month else []

    matched = []
    probable = []
    unmatched_bank = []
    unmatched_receipt = []
    used_receipt_indices = set()

    for ci, crow in enumerate(csv_rows):
        best_match = None
        best_score = 0

        for ri, rtx in enumerate(existing):
            if ri in used_receipt_indices:
                continue
            score = _match_score(crow, rtx)
            if score > best_score:
                best_score = score
                best_match = (ri, rtx)

        if best_match and best_score >= 2:
            # Full match: amount + (date or merchant)
            ri, rtx = best_match
            used_receipt_indices.add(ri)
            matched.append({
                "csv_row": ci,
                "receipt_row": ri,
                "amount": crow["amount"],
                "merchant_bank": crow["merchant"],
                "merchant_receipt": rtx.get("merchant", ""),
                "date": crow["date"],
                "status": "matched",
                "resolved_by": "auto",
                "receipt_id": rtx.get("receipt_id", ""),
                "notes": f"tax:{rtx.get('tax_category', 'none')}" if rtx.get("tax_deductible") else "",
            })
        elif best_match and best_score >= 1:
            # Amount matches but no date/merchant match
            ri, rtx = best_match
            probable.append({
                "csv_row": ci,
                "receipt_row": ri,
                "amount": crow["amount"],
                "merchant_bank": crow["merchant"],
                "merchant_receipt": rtx.get("merchant", ""),
                "date": crow["date"],
                "status": "probable_match",
                "resolved_by": "pending",
            })
        else:
            # No match — new transaction from bank
            unmatched_bank.append({
                "csv_row": ci,
                "amount": crow["amount"],
                "merchant_bank": crow["merchant"],
                "date": crow["date"],
                "status": "unmatched_bank",
            })

    # Find unmatched receipts
    for ri, rtx in enumerate(existing):
        if ri not in used_receipt_indices and rtx.get("source") != "csv":
            unmatched_receipt.append({
                "receipt_row": ri,
                "amount": float(rtx.get("amount", 0)),
                "merchant_receipt": rtx.get("merchant", ""),
                "date": rtx.get("date", ""),
                "status": "unmatched_receipt",
            })

    # Auto-log unmatched bank transactions
    auto_logged = 0
    for ub in unmatched_bank:
        rule = match_rules(ub["merchant_bank"], ub["amount"])
        tx = {
            "date": ub["date"],
            "amount": ub["amount"],
            "merchant": ub["merchant_bank"],
            "category": rule["category"] if rule else "Other",
            "subcategory": rule.get("subcategory", "") if rule else "",
            "card": bank if bank != "auto" else "Unknown",
            "input_method": "csv",
            "confidence": 0.8,
            "matched": False,
            "source": "csv",
            "notes": "Auto-logged from bank CSV",
            "timestamp": datetime.now().isoformat(),
            "month": ub["date"][:7] if ub["date"] else "",
            "receipt_id": "",
            "receipt_number": "",
            "store_address": "",
            "tax_deductible": False,
            "tax_category": "none",
        }
        sheets.append_transaction(tx)
        auto_logged += 1

    # Log all to reconciliation tab
    for entry in matched + probable:
        sheets.append_reconciliation_row(entry)

    # Mark matched transactions
    for m in matched:
        # Update the existing receipt transaction as matched
        pass  # Would need row-level update in sheets

    summary = (
        f"RECONCILIACIÓN COMPLETA — {bank} ({month or 'unknown'})\n"
        f"{len(csv_rows)} transacciones en CSV\n"
        f"{len(matched)} matched con recibos\n"
        f"{auto_logged} nuevas (sin recibo) → auto-logged\n"
        f"{len(probable)} probable match → necesita tu confirmación\n"
        f"{len(unmatched_receipt)} recibos sin match → revisar"
    )

    return {
        "summary": summary,
        "matched": len(matched),
        "probable": probable,
        "unmatched_bank": auto_logged,
        "unmatched_receipt": unmatched_receipt,
    }


def _match_score(csv_row: dict, receipt: dict) -> int:
    """Score a potential match. Amount must be exact (required)."""
    score = 0

    # Amount: EXACT match required
    csv_amt = round(csv_row["amount"], 2)
    rcpt_amt = round(float(receipt.get("amount", 0)), 2)
    if csv_amt != rcpt_amt:
        return 0
    score += 1  # Amount match is baseline

    # Date: same day or ±2 days
    try:
        csv_date = datetime.strptime(csv_row["date"], "%Y-%m-%d")
        rcpt_date = datetime.strptime(receipt.get("date", ""), "%Y-%m-%d")
        if abs((csv_date - rcpt_date).days) <= 2:
            score += 1
    except (ValueError, TypeError):
        pass

    # Merchant: fuzzy match
    csv_m = normalize_merchant(csv_row.get("merchant", ""))
    rcpt_m = normalize_merchant(receipt.get("merchant", ""))
    if csv_m and rcpt_m and (csv_m in rcpt_m or rcpt_m in csv_m):
        score += 1

    return score


def _parse_csv(content: str, bank: str) -> list[dict]:
    """Parse CSV content into standardized rows."""
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for row in reader:
        parsed = _parse_csv_row(row, bank)
        if parsed:
            rows.append(parsed)
    return rows


def _parse_csv_row(row: dict, bank: str) -> dict | None:
    """Parse a single CSV row based on bank format."""
    try:
        if bank == "Chase":
            return {
                "date": _normalize_date(row.get("Transaction Date", "")),
                "amount": abs(float(row.get("Amount", "0").replace(",", ""))),
                "merchant": row.get("Description", ""),
            }
        elif bank == "Discover":
            return {
                "date": _normalize_date(row.get("Trans. Date", "")),
                "amount": abs(float(row.get("Amount", "0").replace(",", ""))),
                "merchant": row.get("Description", ""),
            }
        elif bank == "Citi":
            return {
                "date": _normalize_date(row.get("Date", "")),
                "amount": abs(float(row.get("Amount", "0").replace(",", ""))),
                "merchant": row.get("Description", ""),
            }
        else:
            # Generic: try common column names
            date_val = row.get("Date", row.get("date", row.get("Transaction Date", "")))
            amt_val = row.get("Amount", row.get("amount", "0"))
            desc_val = row.get("Description", row.get("description", row.get("Merchant", "")))
            return {
                "date": _normalize_date(date_val),
                "amount": abs(float(str(amt_val).replace(",", "").replace("$", ""))),
                "merchant": desc_val,
            }
    except (ValueError, KeyError):
        return None


def _normalize_date(date_str: str) -> str:
    """Convert various date formats to YYYY-MM-DD."""
    for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def _detect_bank(content: str) -> str:
    first_line = content.strip().split("\n")[0].lower()
    if "memo" in first_line and "type" in first_line:
        return "Chase"
    if "trans. date" in first_line:
        return "Discover"
    if "extended details" in first_line:
        return "Citi"
    return "unknown"


def _detect_month(rows: list[dict]) -> str | None:
    """Detect the primary month from CSV rows."""
    months: dict[str, int] = {}
    for r in rows:
        m = r.get("date", "")[:7]
        if m:
            months[m] = months.get(m, 0) + 1
    if months:
        return max(months, key=months.get)
    return None
