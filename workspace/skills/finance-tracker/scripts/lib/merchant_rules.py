"""Two-tier merchant rule system for Finance Tracker v2.

Tier 1: Merchant-level rules for single-category merchants (Uber → Transportation).
Tier 2: Multi-category merchants flagged for line-item parsing (Walmart, Target).

Cherry-picked normalize + match from v1 rules.py.
"""

import re
from datetime import date
from pathlib import Path

from . import config as C

# Merchants that sell across categories — always parse line items
MULTI_CATEGORY_MERCHANTS = {
    "walmart", "target", "costco", "home depot", "lowes", "lowe's",
    "publix", "kroger", "amazon", "sam's club", "sams club",
    "dollar general", "dollar tree", "walgreens", "cvs",
    "aldi", "heb", "h-e-b", "meijer", "winco",
}

# Bank prefixes to strip during normalization
_BANK_PREFIXES = re.compile(
    r"^(?:tst\*|sq \*|dd \*|sp \*|par\*|cpi\*|ctlp\*|pp\*|paypal \*|zelle |venmo )",
    re.IGNORECASE,
)


def normalize_merchant(name: str) -> str:
    """Normalize merchant name for matching. 'UBER *TRIP' → 'uber', 'WAL-MART #1234' → 'walmart'."""
    if not name:
        return ""
    m = name.lower().strip()
    m = _BANK_PREFIXES.sub("", m)
    m = re.sub(r"\s*#\d+.*$", "", m)         # strip #store numbers
    m = re.sub(r"\s+\w{2}\s+\d{5}.*$", "", m)  # strip "FL 32801"
    m = re.sub(r"\s+\d{5,}$", "", m)          # trailing zips
    m = re.sub(r"\s*\*.*$", "", m)            # strip * suffixes
    m = m.replace("-", " ").replace("'", "").strip()
    # Consolidate known aliases
    aliases = {
        "wal mart": "walmart", "walmart supercenter": "walmart",
        "uber eats": "uber", "uber technologies": "uber",
        "home depo": "home depot",
    }
    for alias, canonical in aliases.items():
        if alias in m:
            return canonical
    return m.strip()


def is_multi_category(merchant: str) -> bool:
    """Check if a normalized merchant needs line-item parsing."""
    norm = normalize_merchant(merchant)
    return any(mc in norm for mc in MULTI_CATEGORY_MERCHANTS)


def _load_merchant_rules() -> list[dict]:
    path = C.get_config_dir() / "merchant_rules.json"
    if path.exists():
        return C.load_json(path)
    return []


def _save_merchant_rules(rules: list[dict]) -> None:
    C.save_json(C.get_config_dir() / "merchant_rules.json", rules)


def lookup_merchant(name: str) -> dict | None:
    """Look up a merchant in rules. Returns best match or None.

    Returns: {category, subcategory, requires_line_items, confidence, card} or None
    """
    norm = normalize_merchant(name)
    if not norm:
        return None

    # Check multi-category first
    if is_multi_category(norm):
        return {
            "category": None,
            "requires_line_items": True,
            "confidence": None,
            "merchant_normalized": norm,
        }

    rules = _load_merchant_rules()
    matches = []
    for rule in rules:
        pattern = rule.get("merchant_pattern", "").lower()
        if not pattern:
            continue
        # Substring match both directions
        if pattern in norm or norm in pattern:
            matches.append(rule)

    if not matches:
        return None

    # Sort by specificity (longest pattern first), then confidence
    matches.sort(key=lambda r: (-len(r.get("merchant_pattern", "")),
                                 -r.get("confidence", 0)))
    best = matches[0]
    return {
        "category": best.get("category"),
        "subcategory": best.get("subcategory", ""),
        "requires_line_items": best.get("requires_line_items", False),
        "confidence": best.get("confidence", 0.8),
        "card": best.get("default_account", ""),
        "merchant_normalized": norm,
    }


def save_merchant_rule(merchant: str, category: str, confidence: float = 0.85,
                       subcategory: str = "", default_account: str = "",
                       created_by: str = "auto") -> None:
    """Save or update a merchant rule from a confirmed transaction."""
    norm = normalize_merchant(merchant)
    if not norm or is_multi_category(norm):
        return

    rules = _load_merchant_rules()

    # Update existing or append
    for rule in rules:
        if rule.get("merchant_pattern", "").lower() == norm:
            rule["category"] = category
            rule["confidence"] = min(confidence + 0.02, 0.98)  # boost on reuse
            rule["times_used"] = rule.get("times_used", 0) + 1
            rule["last_used"] = date.today().isoformat()
            if subcategory:
                rule["subcategory"] = subcategory
            _save_merchant_rules(rules)
            return

    rules.append({
        "merchant_pattern": norm,
        "category": category,
        "subcategory": subcategory,
        "default_account": default_account,
        "requires_line_items": False,
        "confidence": confidence,
        "times_used": 1,
        "last_used": date.today().isoformat(),
        "created_by": created_by,
    })
    _save_merchant_rules(rules)


def list_rules() -> list[dict]:
    """Return all merchant rules."""
    return _load_merchant_rules()
