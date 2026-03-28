#!/usr/bin/env python3
"""Metrics Calculator — deterministic script (NO LLM).

Reads metrics_input.json, calculates derived metrics, deltas, trends, threshold flags.
Outputs calculated_metrics.json.

Usage:
  python3 metrics_calculator.py <product_id> <week>
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")


def calculate(product_id: str, week: str) -> dict:
    product_dir = PRODUCTS_DIR / product_id
    run_dir = product_dir / "weekly_runs" / week / "growth"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Load inputs
    input_path = run_dir / "metrics_input.json"
    if not input_path.exists():
        raise FileNotFoundError(f"Missing: {input_path}")
    raw = json.loads(input_path.read_text())

    model_path = product_dir / "metrics_model.json"
    model = json.loads(model_path.read_text()) if model_path.exists() else {}

    # Load previous weeks for deltas/trends
    prev_metrics = _load_previous_calculated(product_dir, week, count=4)

    # Extract raw numbers
    meta = raw.get("meta_ads", {})
    email = raw.get("email", {})
    organic = raw.get("organic", {})
    spend = meta.get("spend", 0)
    impressions = meta.get("impressions", 0)
    clicks = meta.get("clicks", 0)
    conversions = meta.get("conversions", 0)
    revenue = raw.get("revenue", 0)
    email_sent = email.get("sent", 0)
    email_opened = email.get("opened", 0)
    email_clicked = email.get("clicked", 0)

    # Calculate derived metrics
    ctr = (clicks / impressions * 100) if impressions else 0
    cpc = (spend / clicks) if clicks else 0
    cpm = (spend / impressions * 1000) if impressions else 0
    cpa = (spend / conversions) if conversions else 0
    roas = (revenue / spend) if spend else 0
    conversion_rate = (conversions / clicks * 100) if clicks else 0
    email_open_rate = (email_opened / email_sent * 100) if email_sent else 0
    email_click_rate = (email_clicked / email_sent * 100) if email_sent else 0
    profit = revenue - spend

    metrics = {
        "ctr": _metric(ctr, "pct"),
        "cpc": _metric(cpc, "usd"),
        "cpm": _metric(cpm, "usd"),
        "cpa": _metric(cpa, "usd"),
        "roas": _metric(roas, "ratio"),
        "conversion_rate": _metric(conversion_rate, "pct"),
        "email_open_rate": _metric(email_open_rate, "pct"),
        "email_click_rate": _metric(email_click_rate, "pct"),
        "revenue": _metric(revenue, "usd"),
        "profit": _metric(profit, "usd"),
        "spend": _metric(spend, "usd"),
    }

    # Calculate deltas vs previous week
    if prev_metrics:
        prev = prev_metrics[0]  # most recent
        prev_m = prev.get("metrics", {})
        for key in metrics:
            pval = prev_m.get(key, {}).get("value")
            if pval is not None:
                metrics[key]["delta_prev_week"] = round(metrics[key]["value"] - pval, 4)

    # Calculate deltas vs baseline (avg of last 4 weeks)
    if len(prev_metrics) >= 2:
        for key in metrics:
            vals = [p.get("metrics", {}).get(key, {}).get("value") for p in prev_metrics]
            vals = [v for v in vals if v is not None]
            if vals:
                baseline = sum(vals) / len(vals)
                metrics[key]["delta_baseline"] = round(metrics[key]["value"] - baseline, 4)

    # Threshold flags from metrics_model
    l2 = model.get("levels", {}).get("L2_marketing", {}).get("metrics", {})
    if cpa and "cpa" in l2:
        ceiling = l2["cpa"].get("ceiling")
        if ceiling and cpa > ceiling:
            metrics["cpa"]["threshold_flag"] = "above_target"
    if roas and "roas" in l2:
        floor = l2["roas"].get("floor")
        if floor and roas < floor:
            metrics["roas"]["threshold_flag"] = "below_target"

    # Trends (3-week consecutive direction)
    trends = {}
    if len(prev_metrics) >= 2:
        for key in ["cpa", "ctr", "roas", "conversion_rate"]:
            trend = _calc_trend(key, metrics, prev_metrics)
            if trend:
                trends[f"{key}_3w"] = trend

    # Alerts
    alerts = []
    if metrics["cpa"].get("threshold_flag") == "above_target":
        consecutive = _consecutive_above(prev_metrics, "cpa",
                                          l2.get("cpa", {}).get("ceiling", 999))
        if consecutive >= 2:
            alerts.append({
                "metric": "cpa",
                "condition": f"above_target_{consecutive}_consecutive_weeks",
                "severity": "warning" if consecutive < 4 else "critical",
            })
        else:
            alerts.append({"metric": "cpa", "condition": "above_target", "severity": "watch"})

    if metrics["roas"].get("threshold_flag") == "below_target":
        alerts.append({"metric": "roas", "condition": "below_target", "severity": "watch"})

    # Build output
    manifest_path = product_dir / "product_manifest.json"
    strategy_version = "unknown"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text())
        strategy_version = m.get("active_strategy_version", "unknown")

    output = {
        "product_id": product_id,
        "run_id": week,
        "strategy_version": strategy_version,
        "calculated_at": datetime.now().isoformat(),
        "raw_input": {
            "spend": spend, "impressions": impressions, "clicks": clicks,
            "conversions": conversions, "revenue": revenue,
        },
        "metrics": metrics,
        "trends": trends,
        "alerts": alerts,
    }

    out_path = run_dir / "calculated_metrics.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"✅ calculated_metrics.json written")
    return output


def _metric(value, unit):
    return {"value": round(value, 4), "unit": unit,
            "delta_prev_week": None, "delta_baseline": None, "threshold_flag": None}


def _load_previous_calculated(product_dir: Path, current_week: str, count: int = 4) -> list:
    """Load calculated_metrics from previous weeks, newest first."""
    runs_dir = product_dir / "weekly_runs"
    if not runs_dir.exists():
        return []
    weeks = sorted([d.name for d in runs_dir.iterdir() if d.is_dir() and d.name < current_week], reverse=True)
    results = []
    for w in weeks[:count]:
        path = runs_dir / w / "growth" / "calculated_metrics.json"
        if path.exists():
            results.append(json.loads(path.read_text()))
    return results


def _calc_trend(key: str, current: dict, prev_list: list) -> str | None:
    """Determine 3-week trend: rising, falling, stable."""
    vals = []
    for p in prev_list[:2]:
        v = p.get("metrics", {}).get(key, {}).get("value")
        if v is not None:
            vals.append(v)
    cur = current.get(key, {}).get("value")
    if cur is None or len(vals) < 2:
        return None
    vals = list(reversed(vals)) + [cur]  # oldest → newest
    diffs = [vals[i+1] - vals[i] for i in range(len(vals)-1)]
    if all(d > 0 for d in diffs):
        return "rising"
    if all(d < 0 for d in diffs):
        return "falling"
    return "stable"


def _consecutive_above(prev_list: list, key: str, threshold: float) -> int:
    """Count consecutive weeks where metric was above threshold."""
    count = 0
    for p in prev_list:
        v = p.get("metrics", {}).get(key, {}).get("value")
        if v is not None and v > threshold:
            count += 1
        else:
            break
    return count


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 metrics_calculator.py <product_id> <week>")
        sys.exit(1)
    calculate(sys.argv[1], sys.argv[2])
