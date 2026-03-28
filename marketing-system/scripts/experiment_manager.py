#!/usr/bin/env python3
"""Experiment Manager — deterministic script (NO LLM).

Manages experiment lifecycle: register proposals, validate closure conditions, update status.

Usage:
  python3 experiment_manager.py <product_id> <week> [--process-proposals <diagnosis.json>]
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")


def process_proposals(product_id: str, week: str, diagnosis: dict) -> dict:
    """Register new experiment proposals from diagnosis agent."""
    product_dir = PRODUCTS_DIR / product_id
    log_path = product_dir / "experiments_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"product_id": product_id, "experiments": []}

    proposed_experiments = diagnosis.get("proposed_experiments", [])
    proposed_closures = diagnosis.get("proposed_closures", [])

    new_experiments = []
    existing_ids = {e["experiment_id"] for e in log["experiments"]}
    next_id = max((int(e["experiment_id"].split("-")[1]) for e in log["experiments"]), default=0) + 1

    # Register new proposals
    for prop in proposed_experiments:
        exp_id = f"EXP-{next_id:03d}"
        next_id += 1
        exp = {
            "experiment_id": exp_id,
            "proposed_by": "diagnosis_agent",
            "proposed_at": week,
            "approved_by": None,
            "approved_at": None,
            "hypothesis": prop.get("hypothesis", ""),
            "variable": prop.get("variable", ""),
            "variant_a": prop.get("variant_a", ""),
            "variant_b": prop.get("variant_b", ""),
            "success_metric": prop.get("success_metric", ""),
            "success_threshold": prop.get("success_threshold", ""),
            "sample_size_target": prop.get("sample_size_target", 3000),
            "min_duration_weeks": prop.get("min_duration_weeks", 2),
            "status": "proposed",
            "result": None,
            "decision": None,
            "related_pattern_id": prop.get("related_pattern_id"),
            "notes": "",
        }
        log["experiments"].append(exp)
        new_experiments.append(exp_id)

    # Process closure proposals
    closures_processed = []
    for closure in proposed_closures:
        exp_id = closure.get("experiment_id")
        for exp in log["experiments"]:
            if exp["experiment_id"] == exp_id and exp["status"] == "running":
                # Validate closure conditions
                can_close, reason = _validate_closure(exp, closure, week)
                if can_close:
                    exp["status"] = "completed"
                    exp["result"] = closure.get("result")
                    exp["decision"] = closure.get("decision", "pending_review")
                    exp["closed_by"] = "experiment_manager"
                    exp["closed_at"] = week
                    closures_processed.append(exp_id)
                else:
                    exp["notes"] = f"Closure proposed at {week} but not met: {reason}"

    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))

    result = {
        "new_experiments_registered": new_experiments,
        "closures_processed": closures_processed,
        "total_active": sum(1 for e in log["experiments"] if e["status"] == "running"),
        "total_proposed": sum(1 for e in log["experiments"] if e["status"] == "proposed"),
    }
    print(f"✅ experiments_log.json updated: {len(new_experiments)} new, {len(closures_processed)} closed")
    return result


def approve_experiment(product_id: str, experiment_id: str) -> bool:
    """Approve a proposed experiment → status 'running'."""
    product_dir = PRODUCTS_DIR / product_id
    log_path = product_dir / "experiments_log.json"
    log = json.loads(log_path.read_text())

    for exp in log["experiments"]:
        if exp["experiment_id"] == experiment_id and exp["status"] == "proposed":
            exp["status"] = "running"
            exp["approved_by"] = "human"
            exp["approved_at"] = datetime.now().isoformat()
            log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
            print(f"✅ {experiment_id} approved → running")
            return True

    print(f"❌ {experiment_id} not found or not in 'proposed' status")
    return False


def _validate_closure(exp: dict, closure: dict, week: str) -> tuple[bool, str]:
    """Validate if experiment can be closed."""
    # Check minimum duration
    proposed_week = exp.get("proposed_at", "")
    if proposed_week and week:
        try:
            pw = int(proposed_week.split("W")[1])
            cw = int(week.split("W")[1])
            duration = cw - pw
            if duration < exp.get("min_duration_weeks", 2):
                return False, f"min_duration not met ({duration} < {exp['min_duration_weeks']})"
        except (ValueError, IndexError):
            pass

    # Check sample size if provided
    result = closure.get("result", {})
    actual_sample = result.get("sample_actual", 0)
    target = exp.get("sample_size_target", 0)
    if target and actual_sample and actual_sample < target * 0.8:
        return False, f"sample_size not met ({actual_sample} < {target * 0.8})"

    return True, "conditions met"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 experiment_manager.py <product_id> <week>")
        sys.exit(1)
    # Standalone: just check status
    product_id = sys.argv[1]
    log_path = PRODUCTS_DIR / product_id / "experiments_log.json"
    if log_path.exists():
        log = json.loads(log_path.read_text())
        active = [e for e in log["experiments"] if e["status"] == "running"]
        proposed = [e for e in log["experiments"] if e["status"] == "proposed"]
        print(f"Experiments: {len(active)} running, {len(proposed)} proposed, {len(log['experiments'])} total")
    else:
        print("No experiments log found")
