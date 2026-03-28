#!/usr/bin/env python3
"""Runtime Orchestrator — central coordinator for all marketing workflows.

Usage:
  python3 runtime_orchestrator.py <product_id> strategy    — run Strategy Workflow
  python3 runtime_orchestrator.py <product_id> marketing   — run Marketing Weekly
  python3 runtime_orchestrator.py <product_id> growth <week> — run Growth Intelligence
  python3 runtime_orchestrator.py <product_id> status      — show product status
"""

import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")

sys.path.insert(0, str(SCRIPTS_DIR))

from preflight_check import run_preflight
from state_lock_manager import acquire_lock, release_lock, is_locked, get_lock_info
from gate_handler import get_pending_gates, _load_runtime_state
from telegram_sender import send_message


def cmd_status(product_id: str):
    """Show current product status."""
    product_dir = PRODUCTS_DIR / product_id

    if not product_dir.exists():
        print(f"Product not found: {product_id}")
        return

    # Product brief
    brief_path = product_dir / "product_brief.json"
    brief = json.loads(brief_path.read_text()) if brief_path.exists() else {}

    # Manifest
    manifest_path = product_dir / "product_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None

    # Lock
    lock_info = get_lock_info(product_id)

    # Runtime state
    state = _load_runtime_state(product_id)
    pending_gates = state.get("pending_gates", {})

    # Strategy versions
    strategies_dir = product_dir / "strategies"
    versions = sorted([d.name for d in strategies_dir.iterdir() if d.is_dir()]) if strategies_dir.exists() else []

    # Weekly runs
    runs_dir = product_dir / "weekly_runs"
    runs = sorted([d.name for d in runs_dir.iterdir() if d.is_dir()]) if runs_dir.exists() else []

    lines = [
        f"{'='*50}",
        f"PRODUCT STATUS — {product_id}",
        f"{'='*50}",
        f"Name: {brief.get('product_name', '?')}",
        f"Price: ${brief.get('price', '?')} {brief.get('currency', '')}",
        f"Language: {brief.get('language', '?')}",
        "",
    ]

    if manifest:
        lines += [
            "Strategy:",
            f"  Active version: {manifest.get('active_strategy_version', 'none')}",
            f"  Status: {manifest.get('strategy_status', 'missing')}",
            f"  Validity: {manifest.get('strategy_validity', 'unknown')}",
            f"  Approved at: {manifest.get('approved_at', 'never')}",
            "",
        ]
    else:
        lines += ["Strategy: NOT GENERATED YET", ""]

    if versions:
        lines.append(f"Strategy versions: {', '.join(versions)}")
    if runs:
        lines.append(f"Weekly runs: {', '.join(runs[-5:])}")  # Last 5

    if lock_info:
        lines += [
            "",
            f"LOCKED by: {lock_info.get('workflow', '?')}",
            f"  Since: {lock_info.get('acquired_at', '?')}",
        ]

    if pending_gates:
        lines += ["", "Pending gates:"]
        for name, gate in pending_gates.items():
            lines.append(f"  - {name} ({gate.get('gate_type', '?')}) — {gate.get('status', '?')}")

    print("\n".join(lines))

    # Send to Telegram too
    tg_lines = [
        f"📊 Status: {product_id}",
        f"Strategy: {manifest.get('strategy_status', 'missing') if manifest else 'missing'}",
    ]
    if manifest and manifest.get("strategy_validity"):
        tg_lines.append(f"Validity: {manifest['strategy_validity']}")
    if pending_gates:
        tg_lines.append(f"Pending gates: {', '.join(pending_gates.keys())}")
    if not manifest:
        tg_lines += [
            "",
            "No existe estrategia. Ejecutar:",
            f"/strategy run {product_id}",
        ]
    send_message("\n".join(tg_lines))


def cmd_strategy(product_id: str):
    """Run Strategy Workflow."""
    # Preflight (no strategy required — we're creating it)
    preflight = run_preflight(product_id, require_strategy=False)
    if not preflight["passed"]:
        print(f"Preflight FAILED: {preflight['errors']}")
        send_message(f"🛑 Strategy preflight failed for {product_id}:\n" + "\n".join(preflight["errors"]))
        return False

    # Lock
    if not acquire_lock(product_id, "strategy"):
        lock = get_lock_info(product_id)
        msg = f"🔒 {product_id} locked by {lock.get('workflow', '?')} since {lock.get('acquired_at', '?')}"
        print(msg)
        send_message(msg)
        return False

    try:
        send_message(f"🚀 Starting Strategy Workflow for {product_id}...")

        # Import and run strategy_runner
        try:
            from strategy_runner import run_strategy
            result = run_strategy(product_id)
            return result
        except ImportError:
            msg = (
                f"Strategy runner not yet implemented.\n"
                f"Product {product_id} needs strategy before marketing can run.\n"
                f"Next step: Implement Paso 4B (Strategy Workflow)"
            )
            print(msg)
            send_message(f"ℹ️ {msg}")
            return False
    finally:
        release_lock(product_id)


def cmd_marketing(product_id: str):
    """Run Marketing Weekly Workflow."""
    # Preflight WITH strategy required
    preflight = run_preflight(product_id, require_strategy=True)
    if not preflight["passed"]:
        # Build actionable message
        errors = preflight["errors"]
        msg_parts = [f"🛑 Marketing bloqueado — {product_id}", ""]
        for e in errors:
            msg_parts.append(f"- {e}")

        if any("no strategy" in e.lower() or "no product_manifest" in e.lower() for e in errors):
            msg_parts += ["", "Acción:", f"/strategy run {product_id}"]
        elif any("hard_invalid" in e for e in errors):
            msg_parts += ["", "Acción:", f"/strategy run {product_id} (re-generate)"]

        msg = "\n".join(msg_parts)
        print(msg)
        send_message(msg)
        return False

    # Lock
    if not acquire_lock(product_id, "marketing"):
        lock = get_lock_info(product_id)
        msg = f"🔒 {product_id} locked by {lock.get('workflow', '?')}"
        print(msg)
        send_message(msg)
        return False

    try:
        send_message(f"🚀 Starting Marketing Weekly for {product_id}...")
        try:
            from marketing_runner import run_marketing
            return run_marketing(product_id)
        except ImportError:
            msg = "Marketing runner not yet implemented. Next step: Paso 4C"
            print(msg)
            send_message(f"ℹ️ {msg}")
            return False
    finally:
        release_lock(product_id)


def cmd_growth(product_id: str, week: str):
    """Run Growth Intelligence."""
    preflight = run_preflight(product_id, require_strategy=True)
    if not preflight["passed"]:
        print(f"Preflight FAILED: {preflight['errors']}")
        return False

    if not acquire_lock(product_id, "growth"):
        print(f"Product locked")
        return False

    try:
        send_message(f"📊 Starting Growth Intelligence for {product_id} {week}...")
        try:
            from growth_runner import run_growth
            return run_growth(product_id, week)
        except ImportError:
            msg = "Growth runner not yet implemented. Next step: Paso 4D"
            print(msg)
            send_message(f"ℹ️ {msg}")
            return False
    finally:
        release_lock(product_id)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    product_id = sys.argv[1]
    command = sys.argv[2]

    if command == "status":
        cmd_status(product_id)
    elif command == "strategy":
        cmd_strategy(product_id)
    elif command == "marketing":
        cmd_marketing(product_id)
    elif command == "growth":
        if len(sys.argv) < 4:
            print("Usage: runtime_orchestrator.py <product_id> growth <week>")
            sys.exit(1)
        cmd_growth(product_id, sys.argv[3])
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
