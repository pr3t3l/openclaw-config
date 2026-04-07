"""Cost tracker for SDD Planner — logs every API call with tokens/cost/duration.

See spec.md §6 (Cost Tracking).
"""

import json
from pathlib import Path
from typing import Optional

_pricing_path = Path(__file__).parent / "config" / "pricing.json"
_pricing_cache: Optional[dict] = None


def _load_pricing() -> dict:
    global _pricing_cache
    if _pricing_cache is None:
        with open(_pricing_path) as f:
            _pricing_cache = json.load(f)
    return _pricing_cache


def get_alert_threshold() -> float:
    return _load_pricing()["alert_threshold_usd"]


def get_hard_limit() -> float:
    return _load_pricing()["hard_limit_usd"]


def compute_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Compute USD cost for an API call.

    Args:
        model: Model identifier (must match a key in pricing.json).
        tokens_in: Input tokens consumed.
        tokens_out: Output tokens produced.

    Returns:
        Estimated cost in USD.

    Raises:
        ValueError: If model is not in pricing config.
    """
    pricing = _load_pricing()
    model_pricing = pricing["models"].get(model)
    if model_pricing is None:
        raise ValueError(
            f"No pricing for model '{model}'. Known models: {list(pricing['models'].keys())}"
        )
    cost_in = (tokens_in / 1_000_000) * model_pricing["input_per_million"]
    cost_out = (tokens_out / 1_000_000) * model_pricing["output_per_million"]
    return round(cost_in + cost_out, 6)


def log_call(
    state: dict,
    model: str,
    tokens_in: int,
    tokens_out: int,
    duration_seconds: float,
    phase: str,
    document: Optional[str] = None,
) -> dict:
    """Log an API call's cost to the state's cost tracking.

    Mutates state["cost"] in place:
    - Accumulates total_usd
    - Accumulates by_model[model]
    - Accumulates by_phase[phase]
    - Accumulates by_document[document] (if provided)

    Args:
        state: The planner state dict.
        model: Model identifier.
        tokens_in: Input tokens.
        tokens_out: Output tokens.
        duration_seconds: Call duration in seconds.
        phase: Phase identifier (e.g., "1", "3", "2.5").
        document: Document name (optional).

    Returns:
        A call record dict with all details.
    """
    cost_usd = compute_cost(model, tokens_in, tokens_out)

    cost = state["cost"]
    cost["total_usd"] = round(cost["total_usd"] + cost_usd, 6)

    model_short = model.split("/")[-1]  # Handle provider/model format
    cost["by_model"][model_short] = round(
        cost["by_model"].get(model_short, 0) + cost_usd, 6
    )
    cost["by_phase"][phase] = round(
        cost["by_phase"].get(phase, 0) + cost_usd, 6
    )
    if document:
        cost["by_document"][document] = round(
            cost["by_document"].get(document, 0) + cost_usd, 6
        )

    return {
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "duration_seconds": duration_seconds,
        "phase": phase,
        "document": document,
    }


def get_summary(state: dict) -> dict:
    """Get a formatted cost summary from the state.

    Returns:
        Dict with total_usd, by_model, by_phase, by_document, alerts.
    """
    cost = state["cost"]
    alerts = []
    if cost["total_usd"] >= get_hard_limit():
        alerts.append(f"HARD LIMIT EXCEEDED: ${cost['total_usd']:.2f} >= ${get_hard_limit():.2f}")
    elif cost["total_usd"] >= get_alert_threshold():
        alerts.append(f"ALERT: Cost ${cost['total_usd']:.2f} exceeds ${get_alert_threshold():.2f} threshold")

    return {
        "total_usd": cost["total_usd"],
        "by_model": cost["by_model"],
        "by_phase": cost["by_phase"],
        "by_document": cost["by_document"],
        "alerts": alerts,
    }


def should_alert(state: dict) -> bool:
    """Check if cost has exceeded the alert threshold ($30)."""
    return state["cost"]["total_usd"] >= get_alert_threshold()


def should_hard_stop(state: dict) -> bool:
    """Check if cost has exceeded the hard limit ($50)."""
    return state["cost"]["total_usd"] >= get_hard_limit()
