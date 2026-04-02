"""Receipt/transaction parsing for Finance Tracker v2.

Flow: regex extraction → merchant rules → AI fallback.
Cherry-picked regex patterns from v1 parser.py.
"""

import re
from datetime import date

from . import config as C
from . import merchant_rules as MR
from . import rules as R
from . import ai_parser as AI

# ── Income detection keywords ─────────────────────────

INCOME_PATTERNS = [
    "me pagaron", "paycheck", "ingreso:", "income:", "cobré", "cobre",
    "deposito:", "depósito:", "me depositaron", "nómina", "nomina",
    "sueldo", "got paid", "direct deposit", "refund",
]


def _is_income(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in INCOME_PATTERNS)


# ── Regex extraction ──────────────────────────────────

_AMOUNT_RE = re.compile(r"\$?([\d,]+\.\d{2})")
_AMOUNT_WHOLE_RE = re.compile(r"\$(\d+)")
_FILLER_WORDS = {
    "gasté", "gaste", "en", "para", "at", "from", "on", "the",
    "spent", "bought", "paid", "for", "de", "del", "la", "el",
    "un", "una", "a", "i", "my", "mi",
}


def _extract_amount(text: str) -> float | None:
    """Extract the largest dollar amount from text."""
    # Try decimal first
    matches = _AMOUNT_RE.findall(text)
    if matches:
        amounts = [float(m.replace(",", "")) for m in matches]
        return max(amounts)
    # Try whole numbers with $
    matches = _AMOUNT_WHOLE_RE.findall(text)
    if matches:
        amounts = [float(m) for m in matches]
        return max(amounts)
    # Try bare numbers
    bare = re.findall(r"(\d+(?:\.\d{1,2})?)", text)
    if bare:
        amounts = [float(b) for b in bare if float(b) > 0]
        if amounts:
            return max(amounts)
    return None


def _extract_card(text: str) -> str | None:
    """Match a card/account name from the configured cards."""
    cards = C.get_cards()
    text_lower = text.lower()
    for card in cards:
        if card.lower() in text_lower:
            return card
    return None


def _extract_merchant(text: str, amount: float | None, card: str | None) -> str:
    """Extract merchant name by removing amounts, cards, and filler words."""
    cleaned = text
    # Remove dollar amounts
    cleaned = re.sub(r"\$[\d,]+\.?\d{0,2}", "", cleaned)
    # Remove bare numbers that match the amount
    if amount:
        cleaned = re.sub(rf"\b{int(amount)}\b", "", cleaned)
        cleaned = re.sub(rf"\b{amount:.2f}\b", "", cleaned)
    # Remove card name
    if card:
        cleaned = re.sub(re.escape(card), "", cleaned, flags=re.IGNORECASE)
    # Remove filler words
    words = cleaned.split()
    words = [w for w in words if w.lower().strip(".,!?") not in _FILLER_WORDS]
    merchant = " ".join(words).strip(" .,!?-")
    return merchant or "Unknown"


# ── Income parsing ────────────────────────────────────

def parse_income(text: str) -> dict:
    """Parse income text into a transaction dict."""
    amount = _extract_amount(text)
    return {
        "type": "income",
        "amount": amount or 0,
        "merchant": "Income",
        "date": date.today().isoformat(),
        "category": "Income",
        "card": "Bank",
        "input_method": "text",
        "confidence": 1.0,
        "needs_confirmation": True,
        "tax_deductible": False,
        "tax_category": "none",
        "notes": text,
    }


# ── Main parse_text ───────────────────────────────────

def parse_text(text: str) -> dict:
    """Parse free-form text into a transaction. Regex → rules → AI fallback."""
    lang = C.get_language()

    # Income detection (before anything else)
    if _is_income(text):
        return parse_income(text)

    # Extract fields via regex
    amount = _extract_amount(text)
    card = _extract_card(text)
    merchant = _extract_merchant(text, amount, card)

    # Try merchant rules
    if merchant and amount:
        rule = MR.lookup_merchant(merchant)
        if rule:
            if rule.get("requires_line_items"):
                # Multi-category merchant — need AI for line items
                ai_result = AI.parse_receipt_lines(text, lang)
                if ai_result and not ai_result.get("llm_request"):
                    return ai_result

            elif rule.get("confidence", 0) >= 0.7 and rule.get("category"):
                # High-confidence single-category match
                tax = R.match_tax_deduction(merchant, rule["category"])
                tx = {
                    "amount": amount,
                    "merchant": merchant,
                    "date": date.today().isoformat(),
                    "category": rule["category"],
                    "subcategory": rule.get("subcategory", ""),
                    "card": card or rule.get("card") or C.get_cards()[0],
                    "input_method": "text",
                    "confidence": rule["confidence"],
                    "needs_confirmation": rule["confidence"] < 0.9,
                    "tax_deductible": tax["deductible"],
                    "tax_category": tax["tax_category"],
                    "type": "expense",
                    "rule_matched": True,
                }
                return tx

    # AI fallback
    ai_result = AI.parse_transaction(text, lang)
    if ai_result and not ai_result.get("llm_request"):
        # Fill in what regex found if AI missed it
        if amount and not ai_result.get("amount"):
            ai_result["amount"] = amount
        if card and not ai_result.get("card"):
            ai_result["card"] = card
        ai_result["input_method"] = "text"
        return ai_result

    # Last resort: build from regex alone
    return {
        "amount": amount or 0,
        "merchant": merchant,
        "date": date.today().isoformat(),
        "category": "Other",
        "card": card or C.get_cards()[0],
        "input_method": "text",
        "confidence": 0.3,
        "needs_confirmation": True,
        "tax_deductible": False,
        "tax_category": "none",
        "type": "expense",
    }


def parse_photo(photo_path: str) -> dict | None:
    """Parse a receipt photo. Always uses AI."""
    lang = C.get_language()
    return AI.parse_receipt_lines(f"[photo:{photo_path}]", lang)
