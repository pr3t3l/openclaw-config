"""Module 6: Reconciliation Engine — match CSV uploads against logged receipts."""

import csv
import io
import json
import re
import subprocess
from datetime import datetime, timedelta

from . import config as C
from . import sheets
from .rules import normalize_merchant, match_rules, add_rule


def _ai_classify_merchants(merchants: list[str]) -> dict[str, str]:
    """Classify unknown merchants in batch via LiteLLM. Returns {merchant: category}."""
    if not merchants:
        return {}

    categories_str = ", ".join(C.CATEGORIES)
    merchant_list = "\n".join(f"- {m}" for m in merchants)

    payload = {
        "model": C.CLASSIFY_MODEL,
        "messages": [
            {"role": "system", "content": "You classify bank transaction merchants into spending categories. Respond ONLY with valid JSON, no markdown."},
            {"role": "user", "content": (
                f"Classify each merchant into exactly one category.\n"
                f"Categories: {categories_str}\n\n"
                f"Merchants:\n{merchant_list}\n\n"
                f"Respond as JSON: {{\"merchant_name\": \"Category\"}}"
            )},
        ],
        "temperature": 0.0,
    }

    try:
        result = subprocess.run(
            ["curl", "-s", C.LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {C.LITELLM_KEY}",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=30
        )
        resp = json.loads(result.stdout)
        ai_text = resp["choices"][0]["message"]["content"]
        # Strip markdown code fences if present
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", ai_text)
        if json_match:
            ai_text = json_match.group(1)
        classifications = json.loads(ai_text.strip())
        # Validate categories
        valid = {}
        for m, cat in classifications.items():
            if cat in C.CATEGORIES:
                valid[m] = cat
            else:
                valid[m] = "Other"
        return valid
    except Exception:
        return {}


def _ensure_rules_for_merchants(unmatched_rows: list[dict]) -> int:
    """Identify merchants without rules, classify via AI, save as new rules.

    Returns number of new rules created.
    """
    # Collect expense merchants without rules
    unknown_merchants = {}
    for ub in unmatched_rows:
        merchant = ub.get("merchant_bank", ub.get("merchant", ""))
        if not merchant:
            continue
        rule = match_rules(merchant, ub.get("amount", 0))
        if rule:
            continue
        # Check if it would be classified as expense (not payment/transfer/income)
        tx_type, _ = _classify_csv_transaction(ub, None)
        if tx_type != "expense":
            continue
        normalized = normalize_merchant(merchant)
        if normalized not in unknown_merchants:
            unknown_merchants[normalized] = merchant  # keep original for display

    if not unknown_merchants:
        return 0

    # Batch classify via AI
    classifications = _ai_classify_merchants(list(unknown_merchants.keys()))
    if not classifications:
        return 0

    # Save as rules
    created = 0
    for normalized, original in unknown_merchants.items():
        category = classifications.get(normalized)
        if not category or category == "Other":
            # Try matching by original name too
            category = classifications.get(original)
        if category and category != "Other":
            add_rule(normalized, category, confidence=0.80,
                     created_by="ai_auto")
            created += 1
    return created


def reconcile_csv(csv_content: str, bank: str = "auto") -> dict:
    """Reconcile a bank CSV against existing transactions."""
    if bank == "auto":
        bank = _detect_bank(csv_content)

    csv_rows = _parse_csv(csv_content, bank)
    months = _detect_months(csv_rows)
    # Load existing receipts for ALL months in the CSV
    existing = []
    for m in months:
        existing.extend(sheets.get_transactions_for_month(m))

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
            # Match: amount + at least one of (date, merchant)
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
        else:
            # Score 0 or 1 (amount-only match = not reliable, treat as unmatched)
            # Amount-only matches caused false positives like Anthropic vs Interest Charge
            unmatched_bank.append({
                "csv_row": ci,
                "amount": crow["amount"],
                "signed_amount": crow.get("signed_amount", crow["amount"]),
                "merchant_bank": crow["merchant"],
                "raw_category": crow.get("raw_category", ""),
                "raw_type": crow.get("raw_type", ""),
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

    # AI-classify unknown merchants and create rules before categorizing
    ai_rules_created = _ensure_rules_for_merchants(unmatched_bank)

    # Auto-log unmatched bank transactions in batch
    auto_log_transactions = []
    cashflow_rows = []
    for ub in unmatched_bank:
        rule = match_rules(ub["merchant_bank"], ub["amount"])
        tx_type, tx_category = _classify_csv_transaction(ub, rule)
        subcategory = rule.get("subcategory", "") if rule else ""
        cashflow_rows.append({
            "date": ub["date"],
            "account": bank if bank != "auto" else "Unknown",
            "merchant": ub["merchant_bank"],
            "amount_signed": ub.get("signed_amount", ub["amount"]),
            "flow_type": tx_type,
            "category": tx_category,
            "subcategory": subcategory,
            "notes": "Imported from bank CSV",
            "source": "csv",
            "timestamp": datetime.now().isoformat(),
            "month": ub["date"][:7] if ub["date"] else "",
        })
        if tx_type in {"payment", "income", "transfer"}:
            continue
        tx = {
            "date": ub["date"],
            "amount": ub["amount"],
            "merchant": ub["merchant_bank"],
            "category": tx_category,
            "subcategory": subcategory,
            "card": bank if bank != "auto" else "Unknown",
            "input_method": "csv",
            "confidence": 0.8,
            "matched": False,
            "source": "csv",
            "notes": f"Auto-logged from bank CSV [{tx_type}]",
            "timestamp": datetime.now().isoformat(),
            "month": ub["date"][:7] if ub["date"] else "",
            "receipt_id": "",
            "receipt_number": "",
            "store_address": "",
            "tax_deductible": False,
            "tax_category": "none",
            "type": tx_type,
        }
        auto_log_transactions.append(tx)

    sheets.append_transactions(auto_log_transactions)
    sheets.append_cashflow_rows(cashflow_rows)
    auto_logged = len(auto_log_transactions)

    # Log all to reconciliation tab in batch
    sheets.append_reconciliation_rows(matched + probable)

    # Mark matched transactions
    for m in matched:
        # Update the existing receipt transaction as matched
        pass  # Would need row-level update in sheets

    month_str = ", ".join(months) if months else "unknown"
    ai_note = f"\n{ai_rules_created} merchants clasificados por AI → reglas creadas" if ai_rules_created else ""
    summary = (
        f"RECONCILIACIÓN COMPLETA — {bank} ({month_str})\n"
        f"{len(csv_rows)} transacciones en CSV\n"
        f"{len(matched)} matched con recibos\n"
        f"{auto_logged} nuevas (sin recibo) → auto-logged\n"
        f"{len(probable)} probable match → necesita tu confirmación\n"
        f"{len(unmatched_receipt)} recibos sin match → revisar"
        f"{ai_note}"
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
    rows = []
    if bank == "Wells":
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            parsed = _parse_csv_row_wells(row)
            if parsed:
                rows.append(parsed)
        return rows

    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        parsed = _parse_csv_row(row, bank)
        if parsed:
            rows.append(parsed)
    return rows


def _parse_csv_row_wells(row: list[str]) -> dict | None:
    try:
        if len(row) < 5:
            return None
        date_val = row[0].strip().strip('"')
        amt_val = float(row[1].strip().strip('"').replace(',', ''))
        desc_val = row[4].strip().strip('"')
        return {
            "date": _normalize_date(date_val),
            "amount": abs(amt_val),
            "signed_amount": amt_val,
            "merchant": desc_val,
            "raw_category": "",
            "raw_type": "",
        }
    except (ValueError, IndexError):
        return None


def _parse_csv_row(row: dict, bank: str) -> dict | None:
    """Parse a single CSV row based on bank format."""
    try:
        if bank == "Chase":
            amount = float(row.get("Amount", "0").replace(",", ""))
            return {
                "date": _normalize_date(row.get("Transaction Date", "")),
                "amount": abs(amount),
                "signed_amount": amount,
                "merchant": row.get("Description", ""),
                "raw_category": row.get("Category", ""),
                "raw_type": row.get("Type", ""),
            }
        elif bank == "Discover":
            amount = float(row.get("Amount", "0").replace(",", ""))
            return {
                "date": _normalize_date(row.get("Trans. Date", "")),
                "amount": abs(amount),
                "signed_amount": amount,
                "merchant": row.get("Description", ""),
                "raw_category": row.get("Category", ""),
                "raw_type": "",
            }
        elif bank == "Citi":
            amount = float(row.get("Amount", "0").replace(",", ""))
            return {
                "date": _normalize_date(row.get("Date", "")),
                "amount": abs(amount),
                "signed_amount": amount,
                "merchant": row.get("Description", ""),
                "raw_category": row.get("Category", ""),
                "raw_type": "",
            }
        else:
            # Generic: try common column names
            date_val = row.get("Date", row.get("date", row.get("Transaction Date", "")))
            amt_val = float(str(row.get("Amount", row.get("amount", "0"))).replace(",", "").replace("$", ""))
            desc_val = row.get("Description", row.get("description", row.get("Merchant", "")))
            return {
                "date": _normalize_date(date_val),
                "amount": abs(amt_val),
                "signed_amount": amt_val,
                "merchant": desc_val,
                "raw_category": row.get("Category", row.get("category", "")),
                "raw_type": row.get("Type", row.get("type", "")),
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
    if first_line.startswith('"') and '"*"' in first_line:
        return "Wells"
    return "unknown"


def _detect_months(rows: list[dict]) -> list[str]:
    """Detect all months present in CSV rows."""
    months: set[str] = set()
    for r in rows:
        m = r.get("date", "")[:7]
        if m and len(m) == 7:
            months.add(m)
    return sorted(months)


def _classify_csv_transaction(row: dict, rule: dict | None) -> tuple[str, str]:
    merchant = (row.get("merchant_bank") or row.get("merchant") or "").upper()
    raw_category = (row.get("raw_category") or "").upper()
    raw_type = (row.get("raw_type") or "").upper()
    signed_amount = float(row.get("signed_amount", row.get("amount", 0) or 0))

    # === PAYMENTS: check FIRST, regardless of sign ===
    # On credit cards, payments TO the card are POSITIVE (credit to account)
    # On checking accounts, payments OUT are NEGATIVE
    payment_keywords = ["PAYMENT", "THANK YOU", "SU PAGO", "PAGO AUTOMATICO",
                        "PAGO AUTO", "EPAY", "AUTOPAY", "INTERNET PAYMENT"]
    if any(k in merchant for k in payment_keywords) or "PAYMENT" in raw_category or "PAYMENT" in raw_type:
        return "payment", "Payment"

    # === TRANSFERS: check regardless of sign ===
    transfer_keywords = ["TRANSFER TO", "TRANSFER FROM", "ZELLE TO", "ZELLE FROM",
                         "WORLDREMIT", "CASH APP", "PAYPAL *", "ROBINHOOD FUNDS",
                         "WIRE TRANS", "EXT TRNSFR", "ONLINE TRANSFER",
                         "MONEY TRANSFER", "BANK ADJUSTMENT", "ADJUSTMENT",
                         "BALANCE TRANSFER"]
    if any(k in merchant for k in transfer_keywords):
        return "transfer", "Transfer"
    if "BALANCE TRANSFERS" in raw_category:
        return "transfer", "Transfer"

    # === POSITIVE amounts (money in) ===
    if signed_amount > 0:
        # Actual returns/refunds
        if "RETURN" in raw_type or "RETURN" in merchant:
            return "refund", "Refunds"

        # Rewards, cashback, statement credits
        if any(k in merchant for k in ["PAYYOURSELFBACK", "CASHBACK", "REWARD",
                                        "REBATE", "BONUS REDEMPTION"]):
            return "income", "Other"
        if "AWARDS" in raw_category or "REBATE" in raw_category or "CREDIT" in raw_category:
            return "income", "Other"

        # Income: payroll, deposits, Airbnb, etc.
        income_keywords = ["PAYROLL", "DEPOSIT", "VENMO CASHOUT", "PAYPAL TRANSFER",
                          "AIRS EDI", "MOBILE DEPOSIT", "INSTANT PMT", "TAX REFUND",
                          "AIRBNB PAYMENTS", "EPAYMENT REVERSAL"]
        if any(k in merchant for k in income_keywords):
            return "income", "Other"

        # Store returns (positive amount + store name = likely return)
        if rule and rule.get("category") in ("Home", "Shopping", "Groceries"):
            return "refund", "Refunds"

        # Default positive: unknown credit → transfer (NOT refund)
        return "transfer", "Other"

    # === NEGATIVE amounts (money out) ===
    # Interest
    if "INTEREST" in raw_category or "INTEREST" in merchant:
        return "expense", "Debt_Interest"

    # Fees
    if any(k in merchant for k in ["FEE", "OVERDRAFT", "SVC CHARGE", "TRANSACTION FEE",
                                     "LATE FEE", "BAL TRANS FEE"]):
        return "expense", "Bank_Fees"
    if "FEE" in raw_category:
        return "expense", "Bank_Fees"

    # Normal expense — use rule category if available
    return "expense", (rule["category"] if rule else "Other")

