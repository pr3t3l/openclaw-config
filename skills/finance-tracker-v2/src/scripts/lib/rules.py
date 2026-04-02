"""Base rules + user overlay system for tax deduction matching.

rules.base.json: compiled from rulepacks during setup (read-only).
rules.user.json: user additions/overrides.
"""

from . import config as C


def _load_base_rules() -> list[dict]:
    path = C.get_config_dir() / "rules.base.json"
    if path.exists():
        return C.load_json(path)
    return []


def _load_user_rules() -> list[dict]:
    path = C.get_config_dir() / "rules.user.json"
    if path.exists():
        return C.load_json(path)
    return []


def save_user_rules(rules: list[dict]) -> None:
    C.save_json(C.get_config_dir() / "rules.user.json", rules)


def get_all_deduction_rules() -> list[dict]:
    """Merge base + user rules. User rules override base on same category."""
    base = _load_base_rules()
    user = _load_user_rules()
    # User overrides base by category
    user_cats = {r.get("category") for r in user}
    merged = [r for r in base if r.get("category") not in user_cats]
    merged.extend(user)
    return merged


def match_tax_deduction(item_name: str, category: str = "",
                        business_rules: list[dict] | None = None) -> dict:
    """Check if an item/category is tax deductible based on rulepack keywords.

    Returns: {"deductible": bool|None, "tax_category": str, "confidence": float}
    """
    rules = business_rules or get_all_deduction_rules()
    if not rules:
        return {"deductible": False, "tax_category": "none", "confidence": 1.0}

    item_lower = item_name.lower() if item_name else ""
    cat_lower = category.lower() if category else ""

    best_match = None
    best_keyword_count = 0

    for rule in rules:
        keywords = rule.get("keywords", [])
        if not keywords:
            continue

        # Count keyword matches in the item name
        matches = sum(1 for kw in keywords if kw.lower() in item_lower)
        if matches > best_keyword_count:
            best_keyword_count = matches
            best_match = rule

        # Also check if the category itself matches
        rule_cat = rule.get("category", "").lower()
        if rule_cat and (rule_cat in cat_lower or cat_lower in rule_cat):
            if not best_match or matches >= best_keyword_count:
                best_match = rule
                best_keyword_count = max(matches, 1)

    if best_match and best_keyword_count > 0:
        return {
            "deductible": True,
            "tax_category": best_match.get("category", "business_expense"),
            "confidence": min(0.6 + best_keyword_count * 0.1, 0.95),
            "irs_reference": best_match.get("irs_reference", ""),
        }

    return {"deductible": False, "tax_category": "none", "confidence": 0.9}
