#!/usr/bin/env python3
"""
human_gate.py — Interactive human gate with summary display.

Usage: python3 human_gate.py <slug> <gate_number>
  gate_number: 1, 2, or 3

Exit codes (PATCH-3):
  0 = approved
  1 = rejected
  2 = adjust (re-run phase with changes)
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path("/home/robotin/.openclaw/workspace-meta-planner")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def show_gate_1_summary(run_dir):
    """Show Fase A summary for human review."""
    intake = load_json(run_dir / "00_intake_summary.json")
    gaps = load_json(run_dir / "01_gap_analysis.json")
    scope = load_json(run_dir / "02_scope_decision.json")

    print("=" * 60)
    print("  GATE #1 — Review Fase A (Clarify)")
    print("=" * 60)
    print(f"\n  Project: {intake.get('project_name', 'N/A')}")
    print(f"  Category: {intake.get('project_category', 'N/A')}")
    print(f"  Budget: ${intake.get('budget_monthly_max', 'N/A')}/month")
    print(f"  Analysis level: {intake.get('debate_level_recommendation', 'N/A')}")

    print(f"\n  --- GAPS ({gaps.get('blocker_count', 0)} blockers, {gaps.get('advisory_count', 0)} advisory) ---")
    print(f"  Readiness score: {gaps.get('readiness_score', 'N/A')}/100")
    for gap in gaps.get("gaps", [])[:5]:
        severity = gap.get("severity", "?").upper()
        print(f"  [{severity}] {gap.get('id', '?')}: {gap.get('description', '')[:100]}...")

    print(f"\n  --- SCOPE RECOMMENDATION ---")
    rec = scope.get("recommendation", {})
    print(f"  Start with: {rec.get('start_with', '?')}")
    print(f"  Reasoning: {rec.get('reasoning', '?')[:150]}...")


def show_gate_2_summary(run_dir):
    """Show Fase B summary."""
    flow = load_json(run_dir / "03_data_flow_map.json")
    arch = load_json(run_dir / "05_architecture_decision.json")

    print("=" * 60)
    print("  GATE #2 — Review Fase B (Design)")
    print("=" * 60)

    artifacts = flow.get("artifacts", [])
    print(f"\n  Data flow: {len(artifacts)} artifacts")
    for a in artifacts[:8]:
        consumed = ", ".join(a.get("consumed_by", []))
        print(f"    {a.get('name', '?')} ({a.get('format', '?')}): {a.get('produced_by', '?')} -> {consumed}")

    components = arch.get("components", {})
    agents = components.get("agents", [])
    scripts = components.get("scripts", [])
    print(f"\n  Architecture: {len(agents)} agents + {len(scripts)} scripts")
    for a in agents[:6]:
        print(f"    Agent: {a.get('name', '?')} ({a.get('model', '?')}) — ${a.get('estimated_cost', 0)}/call")


def show_gate_3_summary(run_dir):
    """Show Fase C summary."""
    review = load_json(run_dir / "08_plan_review.json")
    cost = load_json(run_dir / "07_cost_estimate.json")

    print("=" * 60)
    print("  GATE #3 — Final Review (Buildability)")
    print("=" * 60)
    print(f"\n  Verdict: {review.get('verdict', 'UNKNOWN')}")
    print(f"\n  Cost per run: ${cost.get('per_run_total', 0)}")
    print(f"  Monthly estimate: ${cost.get('monthly_estimate', {}).get('total_monthly_cost', 0)}")

    if review.get("revision_items"):
        print(f"\n  Revision items ({len(review['revision_items'])}):")
        for item in review["revision_items"]:
            print(f"    - {str(item)[:120]}...")


def prompt_approval(slug, gate_num, run_dir):
    """Ask human for approval. Returns exit code (PATCH-3)."""
    print(f"\n{'=' * 60}")
    response = input(f"  Gate #{gate_num} — Approve? (yes / no / adjust): ").strip().lower()

    manifest_path = run_dir / "manifest.json"
    manifest = load_json(manifest_path)
    now = datetime.now(timezone.utc).isoformat()

    if response in ("yes", "y"):
        manifest["gates"][f"gate_{gate_num}"] = {
            "status": "approved",
            "approved_by": "Alfredo",
            "timestamp": now,
            "comment": "Approved via human_gate.py",
        }
        if gate_num == 1:
            # Set scope_selected from scope decision
            scope_path = run_dir / "02_scope_decision.json"
            if scope_path.exists():
                scope = load_json(scope_path)
                manifest["scope_selected"] = scope.get("recommendation", {}).get("start_with", "mvp")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"  Gate #{gate_num} APPROVED.")
        sys.exit(0)
    elif response in ("adjust", "a"):
        changes = input("  Describe your changes: ").strip()
        adj_path = run_dir / f"gate_{gate_num}_adjustments.json"
        adj = {
            "gate": gate_num,
            "adjustments": changes,
            "timestamp": now,
        }
        with open(adj_path, "w") as f:
            json.dump(adj, f, indent=2)
        phase = "A" if gate_num == 1 else "B" if gate_num == 2 else "C"
        print(f"  Adjustments saved. Re-running Fase {phase}...")
        sys.exit(2)
    else:
        manifest["gates"][f"gate_{gate_num}"] = {
            "status": "rejected",
            "approved_by": "Alfredo",
            "timestamp": now,
            "comment": "Rejected via human_gate.py",
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"  Gate #{gate_num} REJECTED. Pipeline stopped.")
        sys.exit(1)


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <slug> <gate_number>")
        sys.exit(1)

    slug = sys.argv[1]
    gate_num = int(sys.argv[2])
    run_dir = WORKSPACE / "runs" / slug

    if not run_dir.exists():
        print(f"ERROR: Run not found: {run_dir}")
        sys.exit(1)

    show_funcs = {1: show_gate_1_summary, 2: show_gate_2_summary, 3: show_gate_3_summary}
    if gate_num not in show_funcs:
        print(f"ERROR: Invalid gate number: {gate_num}")
        sys.exit(1)

    show_funcs[gate_num](run_dir)
    prompt_approval(slug, gate_num, run_dir)


if __name__ == "__main__":
    main()
