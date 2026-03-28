"""Module 7: Rule Engine — auto-categorize known merchants without AI."""

from . import config as C


def normalize_merchant(name: str) -> str:
    """Normalize a merchant name for rule matching."""
    import re
    name = name.lower().strip()
    # Strip common bank-CSV prefixes
    for prefix in ["tst*", "sq *", "dd *", "sp *", "par*", "cpi*", "ctlp*"]:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
    # Strip trailing #digits, city names, state codes
    name = re.sub(r"\s*#\d+.*$", "", name)
    name = re.sub(r"\s+\w{2}\s+\d{5}.*$", "", name)  # "FL 32801"
    name = re.sub(r"\s+\d{5,}$", "", name)
    return name.strip()


def check_amount_condition(condition: str, amount: float) -> bool:
    """Check if an amount matches a rule's amount_condition."""
    if not condition or condition == "any":
        return True
    if condition.startswith(">="):
        return amount >= float(condition[2:])
    if condition.startswith("<="):
        return amount <= float(condition[2:])
    if condition.startswith(">"):
        return amount > float(condition[1:])
    if condition.startswith("<"):
        return amount < float(condition[1:])
    return True


def match_rules(merchant: str, amount: float = 0) -> dict | None:
    """Find the best matching rule for a merchant name.

    Returns the matching rule dict or None.
    Longest pattern wins (more specific). If tied, higher confidence wins.
    """
    rules = C.load_rules()
    normalized = normalize_merchant(merchant)
    matches = []

    for rule in rules:
        pattern = rule["merchant_pattern"].lower()
        if pattern in normalized or normalized in pattern:
            if check_amount_condition(rule.get("amount_condition", "any"), amount):
                matches.append(rule)

    if not matches:
        return None

    # Sort: longest pattern first, then highest confidence
    matches.sort(key=lambda r: (len(r["merchant_pattern"]), r["confidence"]), reverse=True)
    return matches[0]


def add_rule(merchant_pattern: str, category: str, confidence: float = 0.85,
             subcategory: str = "", default_account: str = "Chase",
             amount_condition: str = "any", created_by: str = "manual"):
    """Add a new rule to the rules config."""
    if category not in C.CATEGORIES:
        raise ValueError(f"Invalid category: {category}. Must be one of {C.CATEGORIES}")

    rules = C.load_rules()
    # Check for existing rule with same pattern + amount_condition
    for r in rules:
        if r["merchant_pattern"].lower() == merchant_pattern.lower() and \
           r.get("amount_condition", "any") == amount_condition:
            # Update existing
            r["category"] = category
            r["confidence"] = confidence
            r["subcategory"] = subcategory
            r["default_account"] = default_account
            r["created_by"] = created_by
            C.save_rules(rules)
            return "updated"

    rules.append({
        "merchant_pattern": merchant_pattern.lower(),
        "category": category,
        "subcategory": subcategory,
        "default_account": default_account,
        "confidence": confidence,
        "amount_condition": amount_condition,
        "created_by": created_by,
    })
    C.save_rules(rules)
    return "created"


# Track corrections for auto-rule learning
_correction_log_path = C.CONFIG_DIR / "correction_log.json"


def log_correction(merchant: str, from_category: str, to_category: str):
    """Log a user correction for potential auto-rule creation."""
    import json
    from datetime import datetime

    log = []
    if _correction_log_path.exists():
        log = C.load_json(_correction_log_path)

    log.append({
        "merchant": normalize_merchant(merchant),
        "from": from_category,
        "to": to_category,
        "timestamp": datetime.now().isoformat(),
    })
    C.save_json(_correction_log_path, log)

    # Check if same merchant corrected 2+ times to same category
    normalized = normalize_merchant(merchant)
    same_corrections = [
        e for e in log
        if normalize_merchant(e["merchant"]) == normalized and e["to"] == to_category
    ]
    if len(same_corrections) >= 2:
        result = add_rule(normalized, to_category, confidence=0.85, created_by="system_correction")
        return {
            "auto_rule_created": True,
            "pattern": normalized,
            "category": to_category,
            "action": result,
        }
    return {"auto_rule_created": False}
