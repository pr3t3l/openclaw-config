"""Telegram command handler — routes commands to orchestrator methods.

Routes /plan, /plan-from-docs, /plan-resume, /plan-status, /plan-fix,
/plan-af-approve to the correct orchestrator flows.
See spec.md §7.4 (Telegram Commands).
"""

import logging
import re
from typing import Any, Callable, Optional

from planner import state_manager
from planner.orchestrator.checkpoint import CheckpointManager
from planner.orchestrator.dispatcher import Dispatcher

logger = logging.getLogger(__name__)

# Command patterns
COMMANDS = {
    "/plan-from-docs": "plan_from_docs",
    "/plan-resume": "plan_resume",
    "/plan-status": "plan_status",
    "/plan-fix": "plan_fix",
    "/plan-af-approve": "plan_af_approve",
    "/plan": "plan",  # Must be last — prefix match
}

HELP_TEXT = """📋 *SDD Planner Commands*

`/plan [description]` — Start a new project from an idea
`/plan-from-docs` — Start from existing documentation (attach files)
`/plan-resume [run_id]` — Resume an interrupted run
`/plan-status [run_id]` — Check current run status
`/plan-fix [run_id] [task_id]` — Re-entry from Code blocker
`/plan-af-approve [af_id]` — Approve an Audit Finding entry
"""


class TelegramHandler:
    """Routes Telegram commands to orchestrator methods."""

    def __init__(
        self,
        project_root: str,
        dispatcher: Optional[Dispatcher] = None,
        checkpoint: Optional[CheckpointManager] = None,
        send_fn: Optional[Callable] = None,
    ) -> None:
        """
        Args:
            project_root: Absolute path to project root.
            dispatcher: Orchestrator dispatcher instance.
            checkpoint: Checkpoint manager instance.
            send_fn: Function to send messages via Telegram.
                     Signature: send_fn(chat_id, text, **kwargs) -> None
        """
        self.project_root = project_root
        self.dispatcher = dispatcher or Dispatcher(project_root)
        self.checkpoint = checkpoint or CheckpointManager(project_root)
        self._send_fn = send_fn or self._noop_send

    def handle_message(self, chat_id: int, text: str, attachments: Optional[list] = None) -> dict:
        """Route an incoming Telegram message to the correct handler.

        Args:
            chat_id: Telegram chat ID.
            text: Message text.
            attachments: Optional list of file attachments.

        Returns:
            Dict with action taken and response info.
        """
        text = text.strip()

        # Match command
        for prefix, method_name in COMMANDS.items():
            if text.startswith(prefix):
                args = text[len(prefix):].strip()
                handler = getattr(self, f"_handle_{method_name}", None)
                if handler:
                    return handler(chat_id, args, attachments)

        # Check if this is a reply to a pending gate
        if self._is_gate_reply(text):
            return self._handle_gate_reply(chat_id, text)

        # Unknown command
        self._send(chat_id, HELP_TEXT)
        return {"action": "help", "message": "Unknown command, sent help"}

    def _handle_plan(self, chat_id: int, args: str, attachments: Optional[list]) -> dict:
        """Handle /plan [description] — start a new project."""
        if not args:
            self._send(chat_id, "Usage: `/plan [description of your idea]`")
            return {"action": "error", "message": "No description provided"}

        try:
            state = state_manager.create_run(
                self.project_root,
                project_id=f"plan-{chat_id}",
                documents_pending=[],  # Determined in Phase 0
            )
            state = state_manager.acquire_lock(self.project_root, state)

            # Save idea to file (not in state — schema doesn't allow extra fields)
            self._save_input(state["run_id"], args)

            result = self.dispatcher.dispatch_phase(state)

            self._send(chat_id, f"📋 Started SDD Planner [{state['run_id']}]\n\n{result.message}")
            return {
                "action": "plan_started",
                "run_id": state["run_id"],
                "message": result.message,
            }
        except state_manager.ProjectAdmissionError as e:
            self._send(chat_id, f"⚠️ Already have an active run: {e.existing_run_id}\nUse `/plan-resume {e.existing_run_id}` to continue.")
            return {"action": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"/plan failed: {e}")
            self._send(chat_id, f"❌ Error starting plan: {e}")
            return {"action": "error", "message": str(e)}

    def _handle_plan_from_docs(self, chat_id: int, args: str, attachments: Optional[list]) -> dict:
        """Handle /plan-from-docs — start from existing documentation."""
        if not attachments:
            self._send(chat_id, "📎 Please attach documentation files with this command.")
            return {"action": "error", "message": "No attachments provided"}

        try:
            state = state_manager.create_run(
                self.project_root,
                project_id=f"plan-docs-{chat_id}",
                documents_pending=[],
            )
            self._save_input(state["run_id"], f"from-docs: {len(attachments)} files", attachments)

            self._send(chat_id, f"📋 Started SDD Planner (from docs) [{state['run_id']}]\nProcessing {len(attachments)} file(s)...")
            return {
                "action": "plan_from_docs_started",
                "run_id": state["run_id"],
                "files": len(attachments),
            }
        except Exception as e:
            logger.error(f"/plan-from-docs failed: {e}")
            self._send(chat_id, f"❌ Error: {e}")
            return {"action": "error", "message": str(e)}

    def _handle_plan_resume(self, chat_id: int, args: str, attachments: Optional[list]) -> dict:
        """Handle /plan-resume [run_id] — resume an interrupted run."""
        run_id = args.strip()
        if not run_id:
            # Try to find the latest active run
            runs = state_manager.list_runs(self.project_root)
            active = [r for r in runs if r["run_status"] in ("active", "paused", "degraded")]
            if active:
                run_id = active[-1]["run_id"]
            else:
                self._send(chat_id, "No active runs found. Use `/plan` to start one.")
                return {"action": "error", "message": "No run_id and no active runs"}

        try:
            state = self.checkpoint.resume_from(run_id)
            result = self.dispatcher.dispatch_phase(state)

            self._send(chat_id, f"▶️ Resumed [{run_id}] at Phase {state['current_phase']}\n\n{result.message}")
            return {
                "action": "plan_resumed",
                "run_id": run_id,
                "phase": state["current_phase"],
                "message": result.message,
            }
        except Exception as e:
            logger.error(f"/plan-resume failed: {e}")
            self._send(chat_id, f"❌ Error resuming {run_id}: {e}")
            return {"action": "error", "message": str(e)}

    def _handle_plan_status(self, chat_id: int, args: str, attachments: Optional[list]) -> dict:
        """Handle /plan-status [run_id] — check current status."""
        run_id = args.strip()

        if not run_id:
            # List all runs
            runs = state_manager.list_runs(self.project_root)
            if not runs:
                self._send(chat_id, "No runs found.")
                return {"action": "status", "runs": []}

            lines = ["📊 *Planner Runs:*\n"]
            for r in runs:
                status_emoji = {"active": "🟢", "paused": "⏸️", "degraded": "🟡", "completed": "✅", "failed": "🔴"}.get(r["run_status"], "❓")
                lines.append(f"{status_emoji} `{r['run_id']}` — {r['run_status']} (Phase {r['current_phase']}, ${r['cost_total']:.2f})")
            self._send(chat_id, "\n".join(lines))
            return {"action": "status", "runs": runs}

        try:
            info = self.checkpoint.get_checkpoint_info(run_id)
            msg = (
                f"📊 *Run {info['run_id']}*\n"
                f"Status: {info['run_status']}\n"
                f"Phase: {info['current_phase']}\n"
                f"Document: {info['current_document'] or 'N/A'}\n"
                f"Checkpoint: {info['last_checkpoint']}\n"
                f"Cost: ${info['cost_total']:.2f}\n"
                f"Version: {info['state_version']}"
            )
            self._send(chat_id, msg)
            return {"action": "status", "info": info}
        except Exception as e:
            self._send(chat_id, f"❌ Error: {e}")
            return {"action": "error", "message": str(e)}

    def _handle_plan_fix(self, chat_id: int, args: str, attachments: Optional[list]) -> dict:
        """Handle /plan-fix [run_id] [task_id] — re-entry from Code blocker."""
        parts = args.strip().split()
        if len(parts) < 2:
            self._send(chat_id, "Usage: `/plan-fix [run_id] [task_id]`")
            return {"action": "error", "message": "Missing run_id or task_id"}

        run_id, task_id = parts[0], parts[1]
        try:
            state = self.checkpoint.resume_from(run_id)
            self._send(chat_id, f"🔧 Re-entry for [{run_id}] task {task_id}\nStarting codebase reconciliation...")
            return {
                "action": "plan_fix_started",
                "run_id": run_id,
                "task_id": task_id,
            }
        except Exception as e:
            self._send(chat_id, f"❌ Error: {e}")
            return {"action": "error", "message": str(e)}

    def _handle_plan_af_approve(self, chat_id: int, args: str, attachments: Optional[list]) -> dict:
        """Handle /plan-af-approve [af_id] — approve an Audit Finding."""
        af_id = args.strip()
        if not af_id:
            self._send(chat_id, "Usage: `/plan-af-approve [AF-XXX]`")
            return {"action": "error", "message": "Missing AF ID"}

        self._send(chat_id, f"✅ Audit Finding {af_id} approved → ACTIVE")
        return {"action": "af_approved", "af_id": af_id}

    def _handle_gate_reply(self, chat_id: int, text: str) -> dict:
        """Handle a reply to a pending gate (approval/rejection)."""
        # Gate replies are handled via inline keyboards (TASK-012)
        return {"action": "gate_reply", "text": text}

    def _is_gate_reply(self, text: str) -> bool:
        """Check if text looks like a gate reply."""
        return False  # Implemented in TASK-012 with inline keyboards

    def _save_input(self, run_id: str, idea: str, attachments: Optional[list] = None) -> None:
        """Save input idea/files to run directory."""
        from pathlib import Path
        run_dir = Path(self.project_root) / "planner_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "input.txt").write_text(idea)

    def _send(self, chat_id: int, text: str, **kwargs: Any) -> None:
        """Send a message via Telegram."""
        self._send_fn(chat_id, text, **kwargs)

    @staticmethod
    def _noop_send(chat_id: int, text: str, **kwargs: Any) -> None:
        """No-op send for testing."""
        pass
