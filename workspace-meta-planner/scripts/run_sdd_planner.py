#!/usr/bin/env python3
"""
run_sdd_planner.py — CLI entry point for the SDD Planner.

Usage:
  python3 run_sdd_planner.py start "Build a todo CLI app"
  python3 run_sdd_planner.py start --from-docs /path/to/monolith.md
  python3 run_sdd_planner.py resume [run_id]
  python3 run_sdd_planner.py status [run_id]
  python3 run_sdd_planner.py gate-reply RUN-xxx G0 "MODULE_SPEC, keep it minimal"
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
from planner.orchestrator.gates import GateEngine
from planner.phase_handlers import register_all_handlers

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

    # Phase 0: detect mode (without doc_type — human chooses at G0)
    setup = run_phase_0(PROJECT_ROOT, has_attachments=has_attachments, doc_type=args.doc_type)
    print(f"Mode: {setup.mode}")
    print(f"Context docs loaded: {len(setup.context_loaded)}")

    # Create run with empty documents_pending if no doc_type yet
    docs_pending = setup.documents_pending if args.doc_type else []
    project_id = args.project_id or f"sdd-{idea[:20].replace(' ', '-').lower()}"
    try:
        run_state = state_manager.create_run(
            PROJECT_ROOT, project_id, docs_pending,
        )
    except state_manager.ProjectAdmissionError as e:
        print(f"Error: {e}")
        print(f"Use 'resume {e.existing_run_id}' to continue the existing run.")
        sys.exit(1)

    # Save input
    run_dir = Path(PROJECT_ROOT) / "planner_runs" / run_state["run_id"]
    (run_dir / "input.txt").write_text(idea or f"from-docs: {args.from_docs}")

    # Set Gate G0 pending — human must confirm doc type
    run_state["pending_gate"] = "G0"
    run_state = state_manager.save(PROJECT_ROOT, run_state)

    print(f"\nRun created: {run_state['run_id']}")
    print(f"Run dir: {run_dir}")
    print(f"Status: {run_state['run_status']}")
    print(f"\nGate G0 pending. Reply with MODULE_SPEC or WORKFLOW_SPEC")


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


def cmd_gate_reply(args: argparse.Namespace) -> None:
    """Resolve a pending gate and continue execution until the next gate or completion."""
    run_id = args.run_id
    gate_id = args.gate_id
    response = " ".join(args.response) if args.response else ""

    if not response:
        print("Error: gate response cannot be empty")
        sys.exit(1)

    # Load state via checkpoint manager
    checkpoint = CheckpointManager(PROJECT_ROOT)
    try:
        state = checkpoint.resume_from(run_id)
    except Exception as e:
        print(f"Error loading run {run_id}: {e}")
        sys.exit(1)

    # Verify the pending gate matches
    stored_gate = state.get("pending_gate")
    if stored_gate and stored_gate != gate_id:
        print(f"Error: run {run_id} is waiting on gate {stored_gate}, not {gate_id}")
        state_manager.release_lock(PROJECT_ROOT, state)
        sys.exit(1)

    # G0 special handling: extract doc_type from response and re-run phase 0
    if gate_id == "G0":
        response_upper = response.upper()
        if "MODULE_SPEC" in response_upper:
            doc_type = "MODULE_SPEC"
        elif "WORKFLOW_SPEC" in response_upper:
            doc_type = "WORKFLOW_SPEC"
        else:
            print(f"Error: G0 response must contain MODULE_SPEC or WORKFLOW_SPEC")
            print(f"  Got: {response}")
            state_manager.release_lock(PROJECT_ROOT, state)
            sys.exit(1)

        # Re-run phase 0 with the chosen doc_type
        setup = run_phase_0(PROJECT_ROOT, has_attachments=False, doc_type=doc_type)
        state["documents_pending"] = setup.documents_pending
        print(f"Doc type: {doc_type}")
        print(f"Documents to produce: {setup.documents_pending}")

        # Check for auto-approve mode
        if "AUTO" in response_upper:
            state["auto_approve"] = True
            print(f"Auto-approve: ENABLED (only G0 and G7 will require manual input)")

    # Determine approval from response
    reject_keywords = {"reject", "rejected", "no", "deny", "denied", "redo"}
    first_word = response.strip().split()[0].lower().rstrip(",") if response.strip() else ""
    approved = gate_id == "G0" or first_word not in reject_keywords

    # Resolve the gate
    gate_engine = GateEngine()
    result = gate_engine.resolve_gate(gate_id, approved=True if gate_id == "G0" else approved, notes=response)
    print(f"Gate {gate_id}: {'APPROVED' if result.passed else 'REJECTED'}")
    if result.message:
        print(f"  {result.message}")

    # Clear pending gate
    state["pending_gate"] = None

    if not result.passed:
        # Gate rejected — save state and exit, human needs to adjust
        state["last_checkpoint"] = f"Gate {gate_id} rejected: {response}"
        state = state_manager.release_lock(PROJECT_ROOT, state)
        print(f"\nGate {gate_id} rejected. Run paused at phase {state['current_phase']}.")
        print(f"Fail action: {result.fail_action}")
        return

    # Gate approved — advance to next phase and run until next gate or completion
    dispatcher = Dispatcher(PROJECT_ROOT, gate_engine=gate_engine, checkpoint_manager=checkpoint)
    register_all_handlers(dispatcher, PROJECT_ROOT)
    next_phase = dispatcher._next_phase(state, state["current_phase"])

    if next_phase is None:
        state["run_status"] = "completed"
        state["last_checkpoint"] = "Run complete"
        state = state_manager.release_lock(PROJECT_ROOT, state)
        print("\nAll phases complete. Run finished.")
        print(f"Cost: ${state['cost']['total_usd']:.2f}")
        return

    state["current_phase"] = next_phase
    state = state_manager.save(PROJECT_ROOT, state)

    # Dispatch phases until next gate or completion
    while True:
        result = dispatcher.dispatch_phase(state)
        state = result.state
        print(f"  Phase {state['current_phase']}: {result.message}")

        if result.action == "gate_pending":
            # Save checkpoint and exit — next gate reached
            state = checkpoint.save_checkpoint(state, state["pending_gate"],
                                                message_to_human=result.message)
            print(f"\nPaused at gate {state['pending_gate']}.")
            print(f"Run: {run_id}")
            print(f"Cost: ${state['cost']['total_usd']:.2f}")
            return

        if result.action == "complete":
            print(f"\nAll phases complete. Run finished.")
            print(f"Cost: ${state['cost']['total_usd']:.2f}")
            return

        if result.action == "cost_alert":
            print(f"\n{result.message}")
            state = state_manager.release_lock(PROJECT_ROOT, state)
            return

        if result.action == "error":
            print(f"\nError: {result.message}")
            state = state_manager.release_lock(PROJECT_ROOT, state)
            sys.exit(1)

        # action == "continue" — keep going


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
    p_start.add_argument("--doc-type", default=None,
                        choices=["MODULE_SPEC", "WORKFLOW_SPEC"])
    p_start.add_argument("--project-id", help="Override project ID")

    # resume
    p_resume = sub.add_parser("resume", help="Resume an existing run")
    p_resume.add_argument("run_id", nargs="?", help="Run ID (default: latest active)")

    # status
    p_status = sub.add_parser("status", help="Show run status")
    p_status.add_argument("run_id", nargs="?", help="Run ID (default: list all)")

    # gate-reply
    p_gate = sub.add_parser("gate-reply", help="Resolve a pending gate and continue")
    p_gate.add_argument("run_id", help="Run ID (e.g. RUN-20260407-001)")
    p_gate.add_argument("gate_id", help="Gate ID (e.g. G0, G3, G5, G7)")
    p_gate.add_argument("response", nargs="*", help="Human response to the gate")

    # test-call
    p_test = sub.add_parser("test-call", help="Test LiteLLM connectivity")
    p_test.add_argument("--model", help="Model to test (default: gemini-3.1-pro)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {"start": cmd_start, "resume": cmd_resume, "status": cmd_status,
     "gate-reply": cmd_gate_reply, "test-call": cmd_test_call}[args.command](args)


if __name__ == "__main__":
    main()
