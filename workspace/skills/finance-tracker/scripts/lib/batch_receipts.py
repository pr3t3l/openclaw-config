"""Batch receipt processor for Walmart digital receipts."""

import json
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import config as C
from .sheets import get_sheet, append_transactions
from .rules import match_rules

PROCESSED_FILE = C.CONFIG_DIR / "processed_receipts.json"

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
)

# Items matching these patterns may be Airbnb-related
AIRBNB_KEYWORDS = re.compile(
    r"towel|linen|sheet|pillow|blanket|comforter|duvet|"
    r"clorox|lysol|swiffer|cleaning|cleaner|disinfect|"
    r"mop|broom|vacuum|trash bag|garbage bag|"
    r"laundry|detergent|fabric soften|dryer sheet|"
    r"air freshener|febreze|candle|soap dispens|"
    r"curtain|shower|bath mat|toilet brush|plunger",
    re.IGNORECASE,
)


def _load_processed() -> list:
    if PROCESSED_FILE.exists():
        return C.load_json(PROCESSED_FILE)
    return []


def _save_processed(processed: list):
    C.save_json(PROCESSED_FILE, processed)


def _is_already_processed(link: str) -> bool:
    processed = _load_processed()
    return any(p.get("link") == link if isinstance(p, dict) else p == link for p in processed)


def _mark_processed(link: str, receipt_id: str):
    processed = _load_processed()
    processed.append({"link": link, "receipt_id": receipt_id, "date": datetime.now().isoformat()})
    _save_processed(processed)


def _fetch_receipt_page(url: str) -> str:
    result = subprocess.run(
        ["curl", "-sL", "-A", USER_AGENT, url],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout


def _parse_receipt_data(html: str) -> dict | None:
    """Extract order data from Walmart's __NEXT_DATA__ JSON."""
    match = re.search(r'id="__NEXT_DATA__"[^>]*>([^<]+)', html)
    if not match:
        return None

    try:
        next_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    order = (
        next_data.get("props", {})
        .get("pageProps", {})
        .get("initialData", {})
        .get("data", {})
        .get("order")
    )
    if not order:
        return None

    # Extract date
    order_date_str = order.get("orderDate", "")
    try:
        order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
        date_iso = order_date.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        date_iso = datetime.now().strftime("%Y-%m-%d")

    # Extract items
    items = []
    for group in order.get("groups_2101", []):
        for item in group.get("items", []):
            name = item.get("productInfo", {}).get("name", "Unknown Item")
            qty = item.get("quantity", 1)
            price = item.get("priceInfo", {}).get("linePrice", {}).get("value", 0)
            items.append({"name": name, "quantity": qty, "amount": price})

    # Extract totals
    price_details = order.get("priceDetails", {})
    subtotal = price_details.get("subTotal", {}).get("value", 0)
    tax = price_details.get("taxTotal", {}).get("value", 0)
    total = price_details.get("grandTotal", {}).get("value", 0)

    # Extract payment method
    payment_methods = order.get("paymentMethods", [])
    card_info = ""
    if payment_methods:
        pm = payment_methods[0]
        card_info = pm.get("description", "")

    # Store info
    order_id = order.get("id", "")
    receipt_id = f"walmart-{date_iso.replace('-', '')}-{int(total * 100)}"

    return {
        "order_id": order_id,
        "receipt_id": receipt_id,
        "date": date_iso,
        "items": items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "card_info": card_info,
        "item_count": order.get("itemCount", len(items)),
        "store": "Walmart",
    }


def _find_matching_transaction(
    receipt_total: float, date: str, existing: list[dict]
) -> int | None:
    """Find row index of matching CSV-imported Walmart transaction.

    Returns 1-indexed row number (accounting for header), or None.
    """
    try:
        receipt_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return None

    best_idx = None
    best_date_diff = 999

    for i, row in enumerate(existing):
        merchant = str(row.get("merchant", "")).lower()
        if "walmart" not in merchant and "wal-mart" not in merchant and "wm supercenter" not in merchant:
            continue

        try:
            row_amount = abs(float(row.get("amount", 0)))
        except (ValueError, TypeError):
            continue

        if abs(row_amount - receipt_total) > 0.02:
            continue

        row_date_str = str(row.get("date", ""))
        try:
            row_date = datetime.strptime(row_date_str, "%Y-%m-%d")
        except ValueError:
            continue

        date_diff = abs((row_date - receipt_date).days)
        if date_diff > 2:
            continue

        if date_diff < best_date_diff:
            best_date_diff = date_diff
            best_idx = i

    return best_idx


def _classify_item(item_name: str) -> tuple[str, bool]:
    """Classify a Walmart item into a category.

    Returns (category, is_potential_airbnb).
    """
    name_lower = item_name.lower()
    is_airbnb_candidate = bool(AIRBNB_KEYWORDS.search(name_lower))

    # Try rules engine first
    rule_match = match_rules(item_name)
    if rule_match:
        return rule_match["category"], is_airbnb_candidate

    # Heuristic classification for common Walmart items
    food_keywords = (
        "chicken|beef|pork|salmon|fish|shrimp|turkey|bacon|sausage|"
        "milk|cheese|yogurt|butter|cream|egg|"
        "bread|tortilla|rice|pasta|bean|cereal|oat|"
        "apple|banana|orange|grape|berry|strawberr|blueberr|avocado|"
        "tomato|onion|potato|lettuce|pepper|carrot|broccoli|corn|"
        "juice|water|soda|coffee|tea|"
        "chip|cookie|cracker|candy|chocolate|ice cream|"
        "sauce|oil|vinegar|salt|pepper|spice|sugar|flour|"
        "frozen|canned|soup|fruit|vegetable|salad|"
        "great value|marketside|fresh|organic"
    )
    if re.search(food_keywords, name_lower):
        return "Groceries", False

    clothing_keywords = r"shirt|pants|jeans|dress|sock|underwear|shoe|boot|jacket|coat|sweater|hoodie"
    if re.search(clothing_keywords, name_lower):
        return "Shopping", False

    health_keywords = r"vitamin|medicine|tylenol|advil|band.?aid|first aid|toothpaste|shampoo|deodorant|lotion"
    if re.search(health_keywords, name_lower):
        return "Health", False

    pet_keywords = r"dog food|cat food|pet|puppy|kitten|litter|chew toy|leash|collar"
    if re.search(pet_keywords, name_lower):
        return "Pets", False

    baby_keywords = r"diaper|wipe|formula|baby|infant|toddler|pacifier|bottle|sippy"
    if re.search(baby_keywords, name_lower):
        return "Childcare", False

    home_keywords = r"towel|pillow|sheet|blanket|curtain|bulb|battery|extension|storage|organiz|hanger|trash bag|garbage bag"
    if re.search(home_keywords, name_lower):
        return "Home", is_airbnb_candidate

    cleaning_keywords = r"clorox|lysol|swiffer|clean|disinfect|mop|broom|detergent|fabric soft|dryer sheet|febreze|air fresh|soap"
    if re.search(cleaning_keywords, name_lower):
        return "Home", is_airbnb_candidate

    return "Groceries", False


def _ai_classify_items(items: list[dict]) -> dict[str, str]:
    """Use AI to classify items that couldn't be classified by rules/heuristics."""
    if not items:
        return {}

    item_list = "\n".join(f"- {it['name']}" for it in items)
    prompt = (
        f"Classify each Walmart item into exactly ONE category.\n"
        f"Categories: {', '.join(C.CATEGORIES)}\n\n"
        f"Items:\n{item_list}\n\n"
        f"Reply ONLY with JSON: {{\"item_name\": \"Category\", ...}}"
    )

    payload = {
        "model": C.CLASSIFY_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    try:
        result = subprocess.run(
            ["curl", "-s", C.LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {C.LITELLM_KEY}",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=60,
        )
        resp = json.loads(result.stdout)
        content = resp["choices"][0]["message"]["content"]
        # Extract JSON from response
        json_match = re.search(r"\{[^{}]+\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass
    return {}


def process_receipt_batch(links: list[str], account: str = "Chase") -> dict:
    """Process multiple Walmart receipt links in batch."""
    results = {
        "processed": 0,
        "matched": 0,
        "new": 0,
        "skipped_dup": 0,
        "skipped_error": 0,
        "total_items": 0,
        "pending_airbnb": [],
        "errors": [],
        "receipts": [],
        "summary": "",
        "airbnb_prompt": "",
    }

    # Get all existing transactions for matching
    ws = get_sheet(C.TAB_TRANSACTIONS)
    all_records = ws.get_all_records()

    for i, link in enumerate(links):
        link = link.strip()
        if not link:
            continue

        short_id = link.split("/")[-1] if "/" in link else link

        # Dedup check
        if _is_already_processed(link):
            results["skipped_dup"] += 1
            print(f"  [{i+1}/{len(links)}] SKIP (already processed): {short_id}")
            continue

        # Rate limit
        if i > 0:
            time.sleep(2)

        print(f"  [{i+1}/{len(links)}] Fetching: {short_id} ...", end=" ", flush=True)

        # Fetch
        try:
            html = _fetch_receipt_page(link)
        except Exception as e:
            results["skipped_error"] += 1
            results["errors"].append(f"{short_id}: fetch failed — {e}")
            print("FETCH ERROR")
            continue

        # Parse
        receipt = _parse_receipt_data(html)
        if not receipt or not receipt["items"]:
            results["skipped_error"] += 1
            results["errors"].append(f"{short_id}: parse failed — no items found")
            print("PARSE ERROR")
            continue

        print(f"${receipt['total']:.2f} ({len(receipt['items'])} items) ...", end=" ", flush=True)

        # Classify items
        item_transactions = []
        for item in receipt["items"]:
            category, is_airbnb = _classify_item(item["name"])
            tx = {
                "date": receipt["date"],
                "amount": item["amount"],
                "merchant": f"Walmart — {item['name'][:50]}",
                "category": category,
                "subcategory": "",
                "card": account,
                "input_method": "receipt",
                "confidence": 0.85,
                "matched": True,
                "source": "receipt",
                "notes": f"qty:{item['quantity']}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "month": receipt["date"][:7],
                "receipt_id": receipt["receipt_id"],
                "receipt_number": receipt["order_id"],
                "store_address": "",
                "tax_deductible": False,
                "tax_category": "none",
                "type": "expense",
            }
            item_transactions.append(tx)

            if is_airbnb:
                results["pending_airbnb"].append({
                    "receipt_date": receipt["date"],
                    "item_name": item["name"],
                    "amount": item["amount"],
                    "category": category,
                    "receipt_id": receipt["receipt_id"],
                    "link": link,
                })

        # Find matching generic Walmart row
        match_idx = _find_matching_transaction(receipt["total"], receipt["date"], all_records)

        if match_idx is not None:
            # Delete the generic row (row index in sheet = match_idx + 2 for header)
            row_num = match_idx + 2
            try:
                ws.delete_rows(row_num)
                # Refresh records since row numbers shifted
                all_records.pop(match_idx)
                results["matched"] += 1
                print(f"MATCHED row {row_num} → replaced", end="")
            except Exception as e:
                results["errors"].append(f"{short_id}: delete row failed — {e}")
                print(f"DELETE ERROR", end="")
        else:
            results["new"] += 1
            print(f"NEW (no CSV match)", end="")

        # Distribute tax proportionally across items
        if receipt["tax"] > 0 and receipt["subtotal"] > 0:
            for tx in item_transactions:
                tax_share = round(receipt["tax"] * tx["amount"] / receipt["subtotal"], 2)
                tx["amount"] = round(tx["amount"] + tax_share, 2)

        # Append detailed item rows
        append_transactions(item_transactions)
        results["total_items"] += len(item_transactions)
        results["processed"] += 1
        results["receipts"].append({
            "link": link,
            "receipt_id": receipt["receipt_id"],
            "date": receipt["date"],
            "total": receipt["total"],
            "items": len(receipt["items"]),
        })

        # Mark as processed
        _mark_processed(link, receipt["receipt_id"])

        # Update all_records with new items for future matching
        all_records.extend([{
            "date": tx["date"],
            "amount": tx["amount"],
            "merchant": tx["merchant"],
            "category": tx["category"],
            "receipt_id": tx["receipt_id"],
        } for tx in item_transactions])

        print(f" ✓ {len(item_transactions)} items logged")

    # Build summary
    lines = [
        f"\nBATCH RECEIPT PROCESSING — {len(links)} links",
        f"",
        f"Processed: {results['processed']}",
        f"  {results['matched']} matched existing CSV rows → replaced with detailed items",
        f"  {results['new']} new (no CSV match) → inserted as new",
        f"Skipped: {results['skipped_dup'] + results['skipped_error']}",
    ]
    if results["skipped_dup"]:
        lines.append(f"  {results['skipped_dup']} already processed")
    if results["skipped_error"]:
        lines.append(f"  {results['skipped_error']} fetch/parse failed")
    lines.append(f"Items: {results['total_items']} logged")
    if results["pending_airbnb"]:
        lines.append(f"Pending: {len(results['pending_airbnb'])} items need Airbnb confirmation")
    if results["errors"]:
        lines.append(f"\nErrors:")
        for err in results["errors"]:
            lines.append(f"  - {err}")

    results["summary"] = "\n".join(lines)

    # Build Airbnb prompt
    if results["pending_airbnb"]:
        airbnb_lines = [
            f"\n¿Personal o Airbnb? ({len(results['pending_airbnb'])} items):",
        ]
        for j, item in enumerate(results["pending_airbnb"], 1):
            airbnb_lines.append(
                f"  {j}. {item['receipt_date']} — {item['item_name']} "
                f"(${item['amount']:.2f}) [{item['category']}]"
            )
        airbnb_lines.append(
            '\nResponde: "todos airbnb", "1,2 airbnb 3,4,5 personal", etc.'
        )
        results["airbnb_prompt"] = "\n".join(airbnb_lines)

    return results
