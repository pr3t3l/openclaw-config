#!/usr/bin/env python3
"""
cost_estimator.py — Deterministic cost estimator (NOT an LLM agent).

Reads architecture decision and models.json, calculates per-component
and total costs, writes 07_cost_estimate.json.

Usage:
  python3 cost_estimator.py <slug>
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/home/robotin/.openclaw/workspace-meta-planner")

# Pricing per million tokens (approximate, from LiteLLM config)
PRICING = {
    "claude-sonnet46": {"input": 3.0, "output": 15.0},
    "claude-sonnet46-thinking": {"input": 3.0, "output": 15.0},
    "claude-opus46": {"input": 5.0, "output": 25.0},
    "claude-opus46-thinking": {"input": 5.0, "output": 25.0},
    "gpt52-none": {"input": 3.0, "output": 12.0},
    "gpt52-medium": {"input": 3.0, "output": 12.0},
    "gpt52-thinking": {"input": 3.0, "output": 12.0},
    "gpt52-xhigh": {"input": 3.0, "output": 12.0},
    "gpt53-codex": {"input": 3.0, "output": 12.0},
    "gpt5-mini": {"input": 0.15, "output": 0.60},
    "gpt41": {"input": 2.0, "output": 8.0},
    "gemini31pro-none": {"input": 1.25, "output": 10.0},
    "gemini31pro-medium": {"input": 1.25, "output": 10.0},
    "gemini31pro-thinking": {"input": 1.25, "output": 10.0},
    "gemini31lite-none": {"input": 0.0, "output": 0.0},
    "gemini31lite-low": {"input": 0.0, "output": 0.0},
    "gemini31lite-medium": {"input": 0.0, "output": 0.0},
    "gemini31lite-high": {"input": 0.0, "output": 0.0},
    "minimax-m27": {"input": 0.30, "output": 1.20},
    "kimi-k25": {"input": 0.60, "output": 3.00},
    "step35-flash": {"input": 0.10, "output": 0.30},
}

ARTIFACT_ORDER = [
    "00_intake_summary", "01_gap_analysis", "02_scope_decision",
    "03_data_flow_map", "04_contracts", "05_architecture_decision",
    "06_implementation_plan", "07_cost_estimate", "08_plan_review",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calc_cost(model, input_tokens, output_tokens):
    """Calculate cost in USD for a given model and token counts."""
    pricing = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def find_cheaper_alternatives(model, models_json):
    """Find cheaper models available in LiteLLM."""
    current_pricing = PRICING.get(model, {"input": 999, "output": 999})
    current_cost = current_pricing["input"] + current_pricing["output"]

    alternatives = []
    all_models = set()
    for agent_cfg in models_json.get("agents", {}).values():
        all_models.add(agent_cfg["model"])
    for mod_list in models_json.get("debate_models", {}).values():
        all_models.update(mod_list)

    for alt_model in sorted(PRICING.keys()):
        alt_pricing = PRICING[alt_model]
        alt_cost = alt_pricing["input"] + alt_pricing["output"]
        if alt_cost < current_cost * 0.5 and alt_model != model:
            alternatives.append({
                "model": alt_model,
                "input_price": alt_pricing["input"],
                "output_price": alt_pricing["output"],
            })

    return alternatives[:3]


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <slug>")
        sys.exit(1)

    slug = sys.argv[1]
    run_dir = WORKSPACE / "runs" / slug

    if not run_dir.exists():
        print(f"ERROR: Run not found: {run_dir}")
        sys.exit(1)

    # Load inputs
    arch_path = run_dir / "05_architecture_decision.json"
    if not arch_path.exists():
        print(f"ERROR: Architecture decision not found: {arch_path}")
        sys.exit(1)

    architecture = load_json(arch_path)
    manifest = load_json(run_dir / "manifest.json")
    models_json = load_json(WORKSPACE / "models.json")

    # Load intake for budget and frequency
    intake_path = run_dir / "00_intake_summary.json"
    intake = load_json(intake_path) if intake_path.exists() else {}
    budget_max = intake.get("budget_monthly_max")
    frequency = intake.get("frequency", "unknown")

    # Estimate runs per month from frequency string
    runs_per_month = 4  # default
    freq_lower = frequency.lower()
    if "día" in freq_lower or "day" in freq_lower or "diario" in freq_lower:
        runs_per_month = 30
    elif "semana" in freq_lower or "week" in freq_lower:
        runs_per_month = 4
    elif "mes" in freq_lower or "month" in freq_lower:
        runs_per_month = 1
    elif "caso" in freq_lower or "case" in freq_lower:
        runs_per_month = 4  # assume ~4 cases/month

    project_name = architecture.get("project_name", manifest.get("plan_id", slug))

    # Calculate per-component costs
    per_component_costs = []
    components = architecture.get("components", {})

    # Agents
    for agent in components.get("agents", []):
        model = agent.get("model", "claude-sonnet46")
        input_tokens = agent.get("estimated_input_tokens", 2000)
        output_tokens = agent.get("estimated_output_tokens", 1000)
        cost = calc_cost(model, input_tokens, output_tokens)

        per_component_costs.append({
            "component": agent.get("name", "unknown_agent"),
            "type": "agent",
            "model": model,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "cost_per_call": round(cost, 6),
        })

    # Scripts (cost = 0)
    for script in components.get("scripts", []):
        per_component_costs.append({
            "component": script.get("name", "unknown_script"),
            "type": "script",
            "model": None,
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
            "cost_per_call": 0.0,
        })

    # Calculate totals
    per_run_total = round(sum(c["cost_per_call"] for c in per_component_costs), 6)
    total_monthly = round(per_run_total * runs_per_month, 4)

    # Orchestrator overhead estimate (L-09, L-25)
    orchestrator_overhead = round(per_run_total * 0.1, 6)  # ~10% overhead

    # Budget check
    budget_feasible = True
    if budget_max is not None and budget_max > 0:
        budget_feasible = total_monthly <= budget_max

    # Build notes
    notes_parts = []
    notes_parts.append(f"Estimated {runs_per_month} runs/month based on frequency: '{frequency}'.")

    # Planner costs (actual, from manifest)
    planner_cost = manifest.get("total_cost_usd", 0)
    if planner_cost > 0:
        notes_parts.append(f"Planning phase cost (actual): ${planner_cost:.4f}.")

    if not budget_feasible:
        notes_parts.append(
            f"WARNING: Monthly estimate (${total_monthly:.2f}) exceeds budget "
            f"(${budget_max:.2f}/month). Consider cheaper models or fewer runs."
        )

    # Cheaper alternatives for top cost drivers
    sorted_costs = sorted(
        [c for c in per_component_costs if c["cost_per_call"] > 0],
        key=lambda x: x["cost_per_call"],
        reverse=True,
    )
    if sorted_costs:
        top = sorted_costs[0]
        alts = find_cheaper_alternatives(top["model"], models_json)
        if alts:
            alt_names = ", ".join(a["model"] for a in alts[:2])
            notes_parts.append(
                f"Highest cost driver: {top['component']} ({top['model']}, "
                f"${top['cost_per_call']:.4f}/call). Cheaper alternatives: {alt_names}."
            )

    notes = " ".join(notes_parts)

    # Build output
    cost_estimate = {
        "project_name": project_name,
        "per_component_costs": per_component_costs,
        "per_run_total": per_run_total,
        "monthly_estimate": {
            "runs_per_month": runs_per_month,
            "total_monthly_cost": total_monthly,
        },
        "budget_feasible": budget_feasible,
        "orchestrator_overhead": orchestrator_overhead,
        "notes": notes,
    }

    # Write artifact
    content_str = json.dumps(cost_estimate, indent=2, ensure_ascii=False)
    artifact_path = run_dir / "07_cost_estimate.json"
    artifact_path.write_text(content_str, encoding="utf-8")
    print(f"Wrote: {artifact_path}")

    # Validate
    import subprocess as sp
    val = sp.run(
        [sys.executable, str(WORKSPACE / "scripts" / "validate_schema.py"), slug, "07_cost_estimate"],
        capture_output=True, text=True, timeout=30,
    )
    print(val.stdout.strip())
    if val.returncode != 0:
        print(f"WARNING: Schema validation failed: {val.stderr.strip()}")

    # Update manifest
    file_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["artifacts"]["07_cost_estimate"] = {
        "status": "fresh",
        "hash": file_hash,
        "cost_usd": 0.0,  # Script, not LLM
        "timestamp": now,
    }
    # Invalidate downstream
    idx = ARTIFACT_ORDER.index("07_cost_estimate")
    for downstream in ARTIFACT_ORDER[idx + 1:]:
        if manifest["artifacts"][downstream]["status"] == "fresh":
            manifest["artifacts"][downstream]["status"] = "stale"
    manifest["total_cost_usd"] = round(
        sum((v.get("cost_usd") or 0) for v in manifest["artifacts"].values()), 4
    )
    manifest["last_modified"] = now
    with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Manifest updated: 07_cost_estimate → fresh (cost: $0.0000)")
    print(f"\nPer-run total: ${per_run_total:.4f}")
    print(f"Monthly estimate ({runs_per_month} runs): ${total_monthly:.4f}")
    print(f"Budget feasible: {budget_feasible}")


if __name__ == "__main__":
    main()
