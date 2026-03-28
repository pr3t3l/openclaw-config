"""Artifact validator — validates JSON artifacts against expected schemas."""

import json
from pathlib import Path


# Required fields per artifact type
SCHEMAS = {
    "product_brief.json": {
        "required": ["product_id", "product_name", "price", "language"],
    },
    "product_manifest.json": {
        "required": ["product_id", "active_strategy_version", "strategy_status", "strategy_validity"],
    },
    "strategy_manifest.json": {
        "required": ["product_id", "strategy_version", "status", "outputs"],
    },
    "market_analysis.json": {
        "required": ["product_id", "market_size", "competitors"],
    },
    "buyer_persona.json": {
        "required": ["product_id", "avatar", "pain_points", "purchase_triggers"],
    },
    "brand_strategy.json": {
        "required": ["product_id", "value_proposition", "voice_and_tone"],
    },
    "seo_architecture.json": {
        "required": ["product_id", "keyword_groups"],
    },
    "channel_strategy.json": {
        "required": ["product_id", "channels", "funnel"],
    },
    "run_manifest.json": {
        "required": ["product_id", "run_id", "strategy_version_used", "status"],
    },
    "calculated_metrics.json": {
        "required": ["product_id", "run_id", "metrics"],
    },
    "diagnosis.json": {
        "required": ["product_id", "run_id", "root_cause", "decision_level"],
    },
    "optimization_actions.json": {
        "required": ["product_id", "for_run", "actions"],
    },
}


def validate_artifact(path: Path) -> dict:
    """Validate a JSON artifact. Returns {valid, errors}."""
    errors = []
    filename = path.name

    if not path.exists():
        return {"valid": False, "errors": [f"File not found: {path}"]}

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"Invalid JSON: {e}"]}

    if not isinstance(data, dict):
        return {"valid": False, "errors": ["Expected JSON object, got " + type(data).__name__]}

    schema = SCHEMAS.get(filename)
    if schema:
        for field in schema["required"]:
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif data[field] is None or data[field] == "":
                errors.append(f"Empty required field: {field}")

    return {"valid": len(errors) == 0, "errors": errors}


def validate_strategy_dir(strategy_dir: Path) -> dict:
    """Validate all files in a strategy version directory."""
    results = {}
    expected = [
        "strategy_manifest.json", "market_analysis.json", "buyer_persona.json",
        "brand_strategy.json", "seo_architecture.json", "channel_strategy.json",
    ]
    for f in expected:
        results[f] = validate_artifact(strategy_dir / f)

    all_valid = all(r["valid"] for r in results.values())
    return {"all_valid": all_valid, "files": results}
