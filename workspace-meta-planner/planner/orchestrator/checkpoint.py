"""Checkpoint manager — save state at every gate, exit cleanly, resume from Telegram.

Implements the async state-machine pattern for Telegram:
orchestrator saves state + exits at every human gate (NOT blocking loop).
Telegram callback triggers resume_from(checkpoint).

See spec.md §5 (State Persistence).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from planner import state_manager

logger = logging.getLogger(__name__)


class StaleResumeError(Exception):
    """Raised when attempting to resume with a stale state version."""

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Stale resume: expected state_version {expected}, found {actual}"
        )


class CheckpointManager:
    """Manages save/resume checkpoints for the Planner orchestrator.

    The Planner does NOT block waiting for human input. Instead:
    1. At each human gate, save_checkpoint() persists full state and returns
    2. The orchestrator process exits
    3. When human responds via Telegram, resume_from() loads state and continues
    """

    def __init__(self, project_root: str) -> None:
        self.project_root = project_root

    def save_checkpoint(
        self,
        state: dict,
        gate_id: str,
        message_to_human: str = "",
    ) -> dict:
        """Save state at a gate checkpoint and prepare for exit.

        Args:
            state: Current planner state.
            gate_id: The gate that triggered the checkpoint.
            message_to_human: Message to send to human via Telegram.

        Returns:
            Updated state with checkpoint info.
        """
        doc = state.get("current_document")
        doc_name = doc.get("name") if doc else "N/A"
        state["last_checkpoint"] = (
            f"Gate {gate_id} pending — "
            f"Phase {state['current_phase']}, "
            f"Doc: {doc_name}"
        )
        state["pending_gate"] = gate_id

        # Release lock before exiting (human may take hours to respond)
        if state["locked_by"] is not None:
            state = state_manager.release_lock(self.project_root, state)
        else:
            state = state_manager.save(self.project_root, state)

        logger.info(
            f"Checkpoint saved at gate {gate_id} for run {state['run_id']}. "
            f"State version: {state['state_version']}"
        )
        return state

    def resume_from(
        self,
        run_id: str,
        expected_version: Optional[int] = None,
    ) -> dict:
        """Resume a run from the last checkpoint.

        Args:
            run_id: The run to resume.
            expected_version: If provided, validates state_version matches.
                            Prevents resuming with stale state.

        Returns:
            Loaded and locked state, ready for continued execution.

        Raises:
            FileNotFoundError: If run doesn't exist.
            ValueError: If state is invalid.
            StaleResumeError: If state_version doesn't match expected.
            RunLockedException: If another process holds the lock.
        """
        state = state_manager.load(self.project_root, run_id)

        # Version check — prevent stale resume
        if expected_version is not None and state["state_version"] != expected_version:
            raise StaleResumeError(expected_version, state["state_version"])

        # Run consistency check
        issues = self._consistency_check(state)
        if issues:
            logger.warning(f"Consistency issues on resume: {issues}")
            state["run_status"] = "degraded"

        # Acquire lock
        state = state_manager.acquire_lock(self.project_root, state)

        logger.info(
            f"Resumed run {run_id} at phase {state['current_phase']}, "
            f"state version {state['state_version']}"
        )
        return state

    def _consistency_check(self, state: dict) -> list[str]:
        """Run consistency checks on state before resuming.

        Checks:
        - Run is in a resumable status
        - Current document is consistent with documents lists
        - Phase is valid

        Returns:
            List of issues found (empty = consistent).
        """
        issues = []

        # Check status is resumable
        if state["run_status"] not in ("active", "paused", "degraded"):
            issues.append(
                f"Run status '{state['run_status']}' is not resumable"
            )

        # Check current document consistency
        doc = state.get("current_document")
        if doc:
            doc_name = doc.get("name")
            if doc_name in state.get("documents_completed", []):
                issues.append(
                    f"Current document '{doc_name}' is already in documents_completed"
                )

        # Check phase is valid
        from planner.orchestrator.dispatcher import ALL_PHASES
        if state["current_phase"] not in ALL_PHASES:
            issues.append(f"Invalid phase: {state['current_phase']}")

        return issues

    def get_checkpoint_info(self, run_id: str) -> dict:
        """Get checkpoint info without loading full state or acquiring lock.

        Returns:
            Dict with run_id, status, phase, document, checkpoint, cost.
        """
        state = state_manager.load(self.project_root, run_id)
        doc = state.get("current_document")
        return {
            "run_id": state["run_id"],
            "run_status": state["run_status"],
            "current_phase": state["current_phase"],
            "current_document": doc.get("name") if doc else None,
            "last_checkpoint": state["last_checkpoint"],
            "state_version": state["state_version"],
            "cost_total": state["cost"]["total_usd"],
            "locked_by": state["locked_by"],
        }
