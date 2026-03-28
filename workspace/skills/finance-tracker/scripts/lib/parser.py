"""Module 1: Expense Parser — parse text, photos, and CSVs into structured transactions."""

import json
import re
import subprocess
from datetime import datetime

from . import config as C
from .rules import match_rules, normalize_merchant

SYSTEM_PROMPT = """You are Alfredo's personal expense tracking assistant. Extract expense data from receipt images or text descriptions.

RULES:
- Output ONLY valid JSON, nothing else
- category MUST be one of: Groceries, Restaurants, Gas, Shopping, Entertainment, Subscriptions_AI, Subscriptions_Other, Childcare, Home, Personal, Travel, Work_Tools, Health, Pets, Other
- amounts must be positive numbers
- dates in ISO format YYYY-MM-DD
- If image is unclear, set confidence < 0.5 and add a note
- If user doesn't specify card, guess based on merchant and set confidence to 0.7
- If user says "para trabajo" or "work", categorize as Work_Tools
- If user says "para airbnb" or "airbnb", set tax_deductible to true
- For CSV: parse each row, output JSON array
- For receipts: extract line items into "items" array when readable

RECEIPT ITEM SPLITTING:
When parsing a receipt photo with multiple items:
1. Group items by category
2. Output one transaction per category group
3. All share the same receipt_id (format: merchant-YYYYMMDD-totalcents)
4. Extract receipt_number if visible on the receipt
5. Extract store_address if visible on the receipt

TAX DEDUCTION FLAGGING:
For each item group, set needs_confirmation = true and confirmation_reason if the items are:
- Cleaning products (Clorox, Lysol, bleach, mop, sponges, etc.) → confirmation_reason: "cleaning_supplies"
- Linens (towels, sheets, pillowcases, blankets) → confirmation_reason: "linens"
- Home repair items (tools, hardware, paint, light bulbs) → confirmation_reason: "repair_supplies"
- Home maintenance (air filters, pest control) → confirmation_reason: "maintenance"
- Bathroom/kitchen supplies in bulk → confirmation_reason: "bathroom_supplies" or "kitchen_supplies"

Set needs_confirmation = false and tax_deductible = false for:
- Food and groceries (NEVER ask)
- Clothing and personal items (NEVER ask)
- Medicine (NEVER ask)

When needs_confirmation = true, set tax_category = "pending"
When needs_confirmation = false, set tax_category = "none"

Output schema for receipt photos with multiple categories:
{
  "receipt_id": "<merchant-YYYYMMDD-totalcents>",
  "receipt_number": "<string or null>",
  "store_address": "<string or null>",
  "transactions": [
    {
      "amount": <number>,
      "merchant": "<string>",
      "date": "<YYYY-MM-DD>",
      "category": "<one of 14 categories>",
      "card": "<Chase|Discover|Citi|WellsFargo|Cash>",
      "confidence": <0.0-1.0>,
      "items": [{"name": "<string>", "amount": <number>}],
      "tax_deductible": <true|false|null>,
      "tax_category": "<none|pending>",
      "needs_confirmation": <boolean>,
      "confirmation_reason": "<string or null>"
    }
  ]
}

Output schema for single-category (text input):
{
  "amount": <number>,
  "merchant": "<string>",
  "date": "<YYYY-MM-DD>",
  "category": "<one of 14 categories>",
  "subcategory": "<optional string>",
  "card": "<Chase|Discover|Citi|WellsFargo|Cash>",
  "input_method": "<photo|text|csv>",
  "confidence": <0.0-1.0>,
  "notes": "<string>",
  "items": [{"name": "<string>", "amount": <number>}],
  "tax_deductible": <boolean>,
  "tax_category": "<string>"
}"""

TAX_CATEGORIES = [
    "none", "airbnb_supplies", "airbnb_repair", "airbnb_cleaning",
    "airbnb_utilities", "airbnb_insurance", "airbnb_mortgage_interest",
    "business_expense", "pending",
]


def parse_text(text: str) -> dict:
    """Parse a free-text expense message. Tries rules first, then AI."""
    text_lower = text.lower()
    is_airbnb = "airbnb" in text_lower or "para airbnb" in text_lower
    wants_split = "split" in text_lower

    # Auto-detect split: 3+ dollar amounts in the text means itemized receipt
    dollar_amounts = re.findall(r"\$[\d,]+\.?\d{0,2}", text)
    if len(dollar_amounts) >= 3:
        wants_split = True

    # If split mode, delegate to AI for full item extraction + category grouping
    if wants_split:
        return _ai_parse(text, input_method="text")

    # Try to extract amount and merchant from common patterns
    amount, merchant, card = _extract_text_fields(text)

    if merchant and amount:
        rule = match_rules(merchant, amount)
        if rule and rule["confidence"] >= 0.7:
            tx = {
                "amount": amount,
                "merchant": merchant,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "category": rule["category"],
                "subcategory": rule.get("subcategory", ""),
                "card": card or rule.get("default_account", "Chase"),
                "input_method": "text",
                "confidence": rule["confidence"],
                "notes": "",
                "items": [],
                "rule_matched": True,
                "needs_confirmation": rule["confidence"] < 0.9,
                "tax_deductible": True if is_airbnb else False,
                "tax_category": _infer_tax_category(rule["category"]) if is_airbnb else "none",
            }
            # ask_airbnb merchants always need confirmation (unless user said "airbnb")
            if rule.get("ask_airbnb") and not is_airbnb:
                tx["needs_confirmation"] = True
                tx["tax_deductible"] = None
                tx["tax_category"] = "pending"
                tx["confirmation_reason"] = "ask_airbnb"
            return tx

    # Fall through to AI
    result = _ai_parse(text, input_method="text")
    # If user said "airbnb", force tax fields
    if is_airbnb and isinstance(result, dict):
        result["tax_deductible"] = True
        result["tax_category"] = _infer_tax_category(result.get("category", "Other"))
    return result


def _infer_tax_category(category: str) -> str:
    """Infer the tax_category from the spending category."""
    mapping = {
        "Home": "airbnb_supplies",
        "Work_Tools": "business_expense",
    }
    return mapping.get(category, "airbnb_supplies")


def parse_photo(image_path: str) -> dict:
    """Parse a receipt photo using AI vision."""
    return _ai_parse(image_path, input_method="photo", is_image=True)


def parse_csv_text(csv_content: str, bank: str = "auto") -> list[dict]:
    """Parse CSV content from a bank statement."""
    if bank == "auto":
        bank = _detect_bank_format(csv_content)

    prompt = f"Parse this {bank} bank CSV into transactions. Each row is a separate transaction.\n\nCSV:\n{csv_content}"
    result = _ai_parse(prompt, input_method="csv")

    if isinstance(result, list):
        return result
    return [result]


def _extract_text_fields(text: str) -> tuple:
    """Extract amount, merchant, and card from free text.

    Handles:
      "$45.32 Publix Chase"
      "Gasté $45 en Publix"
      "Publix 45.32"
      "45 gas"
      "Best Buy $200 para trabajo"
    """
    text_lower = text.lower().strip()
    amount = None
    merchant = None
    card = None

    # Extract card if mentioned
    for c in C.CARDS:
        if c.lower() in text_lower:
            card = c
            break

    # Extract amount: find ALL dollar amounts, pick the largest (total > line items)
    amount_matches = re.findall(r"\$?([\d,]+\.\d{2})", text)
    if not amount_matches:
        # Fallback: whole numbers without decimals
        amount_matches = re.findall(r"\$?([\d,]+)", text)
    if amount_matches:
        amounts = [float(m.replace(",", "")) for m in amount_matches]
        amount = max(amounts)

    # Extract merchant: everything that's not amount/card/keywords
    cleaned = text
    # Remove amount patterns
    cleaned = re.sub(r"\$?[\d,]+\.?\d{0,2}", "", cleaned)
    # Remove card names
    for c in C.CARDS:
        cleaned = re.sub(re.escape(c), "", cleaned, flags=re.IGNORECASE)
    # Remove common filler words
    for word in ["gasté", "gaste", "en", "para", "trabajo", "work", "personal", "con"]:
        cleaned = re.sub(rf"\b{word}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().strip("$").strip()
    if cleaned:
        merchant = cleaned

    return amount, merchant, card


def _ai_parse(content: str, input_method: str = "text", is_image: bool = False) -> dict | list:
    """Call LiteLLM AI for parsing."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if is_image:
        import base64
        from pathlib import Path
        img_data = base64.b64encode(Path(content).read_bytes()).decode()
        ext = Path(content).suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_data}"}},
                {"type": "text", "text": f"Parse this receipt. Today is {datetime.now().strftime('%Y-%m-%d')}. Output JSON only."}
            ]
        })
    else:
        messages.append({
            "role": "user",
            "content": f"Parse this expense. Today is {datetime.now().strftime('%Y-%m-%d')}.\n\n{content}"
        })

    payload = {
        "model": C.PARSE_MODEL,
        "messages": messages,
        "temperature": 0.1,
    }

    result = subprocess.run(
        ["curl", "-s", C.LITELLM_URL,
         "-H", "Content-Type: application/json",
         "-H", f"Authorization: Bearer {C.LITELLM_KEY}",
         "-d", json.dumps(payload)],
        capture_output=True, text=True, timeout=60
    )

    resp = json.loads(result.stdout)
    ai_text = resp["choices"][0]["message"]["content"]

    # Extract JSON from response (handle markdown code blocks)
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", ai_text)
    if json_match:
        ai_text = json_match.group(1)

    parsed = json.loads(ai_text.strip())

    # Handle split receipt format (has "transactions" key)
    if isinstance(parsed, dict) and "transactions" in parsed:
        for tx in parsed["transactions"]:
            tx.setdefault("input_method", input_method)
            tx.setdefault("confidence", 0.8)
            tx.setdefault("items", [])
            tx.setdefault("notes", "")
            tx.setdefault("tax_deductible", None if tx.get("tax_category") == "pending" else False)
            tx.setdefault("tax_category", "none")
            tx.setdefault("needs_confirmation", False)
            tx.setdefault("confirmation_reason", None)
            tx["rule_matched"] = False
        return parsed

    # Ensure required fields — single transaction
    if isinstance(parsed, dict):
        parsed.setdefault("input_method", input_method)
        parsed.setdefault("confidence", 0.8)
        parsed.setdefault("items", [])
        parsed.setdefault("notes", "")
        parsed.setdefault("tax_deductible", False)
        parsed.setdefault("tax_category", "none")
        parsed["rule_matched"] = False
        parsed["needs_confirmation"] = True
    elif isinstance(parsed, list):
        for p in parsed:
            p.setdefault("input_method", input_method)
            p.setdefault("confidence", 0.8)
            p.setdefault("items", [])
            p.setdefault("notes", "")
            p.setdefault("tax_deductible", False)
            p.setdefault("tax_category", "none")
            p["rule_matched"] = False
            p["needs_confirmation"] = True

    return parsed


def _detect_bank_format(csv_content: str) -> str:
    """Detect which bank a CSV comes from based on headers."""
    first_line = csv_content.strip().split("\n")[0].lower()
    if "memo" in first_line and "type" in first_line:
        return "Chase"
    if "trans. date" in first_line:
        return "Discover"
    if "extended details" in first_line:
        return "Citi"
    return "unknown"


def check_duplicate(tx: dict, recent: list[dict]) -> dict | None:
    """Check if a transaction might be a duplicate of a recent one."""
    for r in recent:
        if (abs(float(r.get("amount", 0)) - tx["amount"]) < 0.01 and
            normalize_merchant(r.get("merchant", "")) == normalize_merchant(tx.get("merchant", "")) and
            r.get("date", "") == tx.get("date", "")):
            return r
    return None
