#!/usr/bin/env python3
"""
run_sdd_planner.py — CLI entry point for the SDD Planner.

Usage:
  python3 run_sdd_planner.py start "Build a todo CLI app"
  python3 run_sdd_planner.py start --from-docs /path/to/monolith.md
  python3 run_sdd_planner.py resume [run_id]
  python3 run_sdd_planner.py status [run_id]
  python3 run_sdd_planner.py test-call        # Test LiteLLM connectivity

Integrates with the existing workspace-meta-planner infrastructure.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add planner to path
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from planner import state_manager
from planner.model_gateway import ModelGateway
from planner.cost_tracker import get_summary
from planner.phases.phase_0_setup import run_phase_0
from planner.orchestrator.dispatcher import Dispatcher
from planner.orchestrator.checkpoint import CheckpointManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sdd-planner")

# Project root for SDD Planner runs
PROJECT_ROOT = str(WORKSPACE)


def cmd_start(args: argparse.Namespace) -> None:
    """Start a new SDD Planner run."""
    idea = " ".join(args.idea) if args.idea else ""
    if not idea and not args.from_docs:
        print("Error: provide an idea or --from-docs path")
        sys.exit(1)

    has_attachments = bool(args.from_docs)

    # Phase 0: detect mode
    setup = run_phase_0(PROJECT_ROOT, has_attachments=has_attachments, doc_type=args.doc_type)
    print(f"Mode: {setup.mode}")
    print(f"Context docs loaded: {len(setup.context_loaded)}")
    print(f"Documents to produce: {setup.documents_pending}")

    # Create run
    project_id = args.project_id or f"sdd-{idea[:20].replace(' ', '-').lower()}"
    try:
        run_state = state_manager.create_run(
            PROJECT_ROOT, project_id, setup.documents_pending,
        )
    except state_manager.ProjectAdmissionError as e:
        print(f"Error: {e}")
        print(f"Use 'resume {e.existing_run_id}' to continue the existing run.")
        sys.exit(1)

    # Save input
    run_dir = Path(PROJECT_ROOT) / "planner_runs" / run_state["run_id"]
    (run_dir / "input.txt").write_text(idea or f"from-docs: {args.from_docs}")

    print(f"\nRun created: {run_state['run_id']}")
    print(f"Run dir: {run_dir}")
    print(f"Status: {run_state['run_status']}")
    print(f"\nNext: connect Telegram or use 'resume {run_state['run_id']}' to continue.")


def cmd_resume(args: argparse.Namespace) -> None:
    """Resume an existing run."""
    run_id = args.run_id
    if not run_id:
        runs = state_manager.list_runs(PROJECT_ROOT)
        active = [r for r in runs if r["run_status"] in ("active", "paused", "degraded")]
        if not active:
            print("No active runs found.")
            sys.exit(1)
        run_id = active[-1]["run_id"]
        print(f"Resuming latest: {run_id}")

    checkpoint = CheckpointManager(PROJECT_ROOT)
    try:
        run_state = checkpoint.resume_from(run_id)
        print(f"Resumed: {run_id}")
        print(f"Phase: {run_state['current_phase']}")
        print(f"Checkpoint: {run_state['last_checkpoint']}")
        print(f"Cost: ${run_state['cost']['total_usd']:.2f}")
    except Exception as e:
        print(f"Error resuming: {e}")
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    """Show status of runs."""
    if args.run_id:
        try:
            checkpoint = CheckpointManager(PROJECT_ROOT)
            info = checkpoint.get_checkpoint_info(args.run_id)
            print(json.dumps(info, indent=2))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        runs = state_manager.list_runs(PROJECT_ROOT)
        if not runs:
            print("No runs found.")
            return
        for r in runs:
            emoji = {"active": "🟢", "paused": "⏸️", "degraded": "🟡",
                     "completed": "✅", "failed": "🔴"}.get(r["run_status"], "❓")
            print(f"  {emoji} {r['run_id']} — {r['run_status']} "
                  f"(Phase {r['current_phase']}, ${r['cost_total']:.2f})")


def cmd_test_call(args: argparse.Namespace) -> None:
    """Test LiteLLM connectivity with a real API call."""
    print("Testing LiteLLM connectivity...")
    print(f"Model: {args.model or 'gemini-3.1-pro'} (cheapest)")

    state = {
        "cost": {"total_usd": 0.0, "by_model": {}, "by_phase": {}, "by_document": {}},
    }

    gw = ModelGateway(state)
    model = args.model or "gemini-3.1-pro"

    try:
        result = gw.call_model(
            role="primary",
            prompt="Reply with exactly: SDD_PLANNER_OK",
            context="You are a connectivity test. Reply with the exact text requested.",
            phase="test",
            model=model,
            provider="google",
            max_tokens=50,
        )
        print(f"\n✅ Success!")
        print(f"  Model: {result['model']}")
        print(f"  Response: {result['content'][:100]}")
        print(f"  Tokens: {result['tokens_in']} in / {result['tokens_out']} out")
        print(f"  Cost: ${result['cost_usd']:.6f}")
        print(f"  Duration: {result['duration']:.2f}s")
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="SDD Planner CLI")
    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="Start a new planner run")
    p_start.add_argument("idea", nargs="*", help="Project idea description")
    p_start.add_argument("--from-docs", help="Path to monolith document")
    p_start.add_argument("--doc-type", default="WORKFLOW_SPEC",
                        choices=["MODULE_SPEC", "WORKFLOW_SPEC"])
    p_start.add_argument("--project-id", help="Override project ID")

    # resume
    p_resume = sub.add_parser("resume", help="Resume an existing run")
    p_resume.add_argument("run_id", nargs="?", help="Run ID (default: latest active)")

    # status
    p_status = sub.add_parser("status", help="Show run status")
    p_status.add_argument("run_id", nargs="?", help="Run ID (default: list all)")

    # test-call
    p_test = sub.add_parser("test-call", help="Test LiteLLM connectivity")
    p_test.add_argument("--model", help="Model to test (default: gemini-3.1-pro)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {"start": cmd_start, "resume": cmd_resume, "status": cmd_status,
     "test-call": cmd_test_call}[args.command](args)


if __name__ == "__main__":
    main()
