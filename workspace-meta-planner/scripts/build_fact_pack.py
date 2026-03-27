#!/usr/bin/env python3
"""
build_fact_pack.py — Extract key facts from artifacts for report review.

Prevents context bloat: instead of passing 9 full JSON artifacts to the
reviewer (~10-20K tokens), this extracts ~1-2K tokens of verifiable facts.

Usage: python3 build_fact_pack.py <slug>
Output: runs/<slug>/fact_pack.json
"""
import json
import sys
from pathlib import Path

WORKSPACE = Path("/home/robotin/.openclaw/workspace-meta-planner")


def load_json_safe(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def extract_facts(run_dir):
    facts = {"project": {}, "gaps": {}, "scope": {}, "architecture": {}, "costs": {}, "verdict": {}}

    intake = load_json_safe(run_dir / "00_intake_summary.json")
    if intake:
        facts["project"] = {
            "name": intake.get("project_name"),
            "category": intake.get("project_category"),
            "budget": intake.get("budget_monthly_max"),
            "debate_level": intake.get("debate_level_recommendation"),
            "status": intake.get("status"),
        }

    gaps = load_json_safe(run_dir / "01_gap_analysis.json")
    if gaps:
        facts["gaps"] = {
            "total": len(gaps.get("gaps", [])),
            "blockers": gaps.get("blocker_count", 0),
            "advisory": gaps.get("advisory_count", 0),
            "readiness_score": gaps.get("readiness_score"),
            "top_blockers": [
                {"id": g["id"], "description": g["description"][:80]}
                for g in gaps.get("gaps", []) if g.get("severity") == "blocker"
            ][:5],
        }

    scope = load_json_safe(run_dir / "02_scope_decision.json")
    if scope:
        rec = scope.get("recommendation", {})
        facts["scope"] = {
            "recommended": rec.get("start_with"),
            "reasoning_summary": rec.get("reasoning", "")[:150],
        }

    arch = load_json_safe(run_dir / "05_architecture_decision.json")
    if arch:
        components = arch.get("components", {})
        facts["architecture"] = {
            "agents": len(components.get("agents", [])),
            "scripts": len(components.get("scripts", [])),
            "agent_names": [a.get("name") for a in components.get("agents", [])],
            "total_estimated_cost": round(
                sum(a.get("estimated_cost", 0) for a in components.get("agents", [])), 4
            ),
        }

    cost = load_json_safe(run_dir / "07_cost_estimate.json")
    if cost:
        facts["costs"] = {
            "per_run": cost.get("per_run_total"),
            "monthly": cost.get("monthly_estimate", {}).get("total_monthly_cost"),
            "budget_feasible": cost.get("budget_feasible"),
        }

    review = load_json_safe(run_dir / "08_plan_review.json")
    if review:
        facts["verdict"] = {
            "status": review.get("verdict"),
            "revision_items": len(review.get("revision_items") or []),
            "risks": len(review.get("risk_register", [])),
        }

    # Manifest costs
    manifest = load_json_safe(run_dir / "manifest.json")
    if manifest:
        facts["planning_cost"] = manifest.get("total_cost_usd", 0)

    return facts


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <slug>")
        sys.exit(1)

    slug = sys.argv[1]
    run_dir = WORKSPACE / "runs" / slug
    facts = extract_facts(run_dir)

    out_path = run_dir / "fact_pack.json"
    with open(out_path, "w") as f:
        json.dump(facts, f, indent=2)
    print(f"Fact pack written: {out_path}")


if __name__ == "__main__":
    main()
