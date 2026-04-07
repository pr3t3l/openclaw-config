"""Orchestrator phase dispatcher — engine that transitions between phases.

Dispatches to correct phase handler based on current_phase in state.
Handles document loop, conditional phases, and cost alerts.
See spec.md §3 (Phases & Agents, phase order).
"""

import logging
from typing import Any, Callable, Optional

from planner import cost_tracker, state_manager

logger = logging.getLogger(__name__)

# Phase ordering — defines the sequence of phases for a single document
DOCUMENT_PHASES = ["0", "1", "1.5", "2", "2.5", "3", "4", "5", "6"]

# Post-document phases (run once after all docs processed)
POST_DOCUMENT_PHASES = ["6.5", "7"]

# All valid phases
ALL_PHASES = DOCUMENT_PHASES + POST_DOCUMENT_PHASES

# Foundation doc types that skip ideation (Phase 1.5)
SKIP_IDEATION_TYPES = {
    "PROJECT_FOUNDATION",
    "CONSTITUTION",
    "DATA_MODEL",
    "INTEGRATIONS",
    "LESSONS_LEARNED",
}


class PhaseHandler:
    """Base class for phase handlers. Each phase implements execute()."""

    phase_id: str = ""

    def execute(self, state: dict, context: dict) -> dict:
        """Execute this phase. Returns updated state.

        Args:
            state: Current planner state.
            context: Additional context (project_root, gateway, etc.).

        Returns:
            Updated state dict.
        """
        raise NotImplementedError


class DispatchResult:
    """Result of a dispatch operation."""

    def __init__(
        self,
        state: dict,
        action: str,
        next_phase: Optional[str] = None,
        gate_pending: bool = False,
        message: str = "",
    ) -> None:
        self.state = state
        self.action = action  # "continue", "gate_pending", "complete", "cost_alert", "error"
        self.next_phase = next_phase
        self.gate_pending = gate_pending
        self.message = message


class Dispatcher:
    """Engine that transitions between phases and dispatches to handlers."""

    def __init__(
        self,
        project_root: str,
        phase_handlers: Optional[dict[str, PhaseHandler]] = None,
        gate_engine: Optional[Any] = None,
        checkpoint_manager: Optional[Any] = None,
    ) -> None:
        self.project_root = project_root
        self._handlers: dict[str, PhaseHandler] = phase_handlers or {}
        self._gate_engine = gate_engine
        self._checkpoint = checkpoint_manager
        self.skip_ideation = False  # Set by human to skip Phase 1.5

    def register_handler(self, phase_id: str, handler: PhaseHandler) -> None:
        """Register a phase handler."""
        self._handlers[phase_id] = handler

    def dispatch_phase(self, state: dict) -> DispatchResult:
        """Dispatch the current phase and determine next action.

        This is the main loop entry point. It:
        1. Checks cost alerts
        2. Resolves which phase to run
        3. Executes the phase handler
        4. Determines next phase or gate
        5. Updates state

        Returns:
            DispatchResult indicating what happened and what comes next.
        """
        # Check cost alert before proceeding
        if cost_tracker.should_hard_stop(state):
            return DispatchResult(
                state=state,
                action="cost_alert",
                message=f"HARD LIMIT: ${state['cost']['total_usd']:.2f} exceeds ${cost_tracker.get_hard_limit():.2f}. Human approval required.",
            )

        if cost_tracker.should_alert(state):
            logger.warning(f"Cost alert: ${state['cost']['total_usd']:.2f}")

        current_phase = state["current_phase"]

        # Check if phase should be skipped
        if self._should_skip_phase(state, current_phase):
            next_phase = self._next_phase(state, current_phase)
            if next_phase is None:
                return self._handle_completion(state)
            state["current_phase"] = next_phase
            state = state_manager.save(self.project_root, state)
            logger.info(f"Skipped phase {current_phase}, advancing to {next_phase}")
            return DispatchResult(
                state=state,
                action="continue",
                next_phase=next_phase,
                message=f"Phase {current_phase} skipped, moving to {next_phase}",
            )

        # Get handler for current phase
        handler = self._handlers.get(current_phase)
        if handler is None:
            logger.warning(f"No handler for phase {current_phase}, advancing")
            next_phase = self._next_phase(state, current_phase)
            if next_phase is None:
                return self._handle_completion(state)
            state["current_phase"] = next_phase
            state = state_manager.save(self.project_root, state)
            return DispatchResult(
                state=state,
                action="continue",
                next_phase=next_phase,
                message=f"No handler for phase {current_phase}, skipping to {next_phase}",
            )

        # Execute the phase
        try:
            state = handler.execute(state, {"project_root": self.project_root})
        except Exception as e:
            logger.error(f"Phase {current_phase} failed: {e}")
            return DispatchResult(
                state=state,
                action="error",
                message=f"Phase {current_phase} failed: {e}",
            )

        # Check if a gate is pending (phase handler sets this via transient key)
        gate_id = state.pop("_gate_pending", None)
        if gate_id:
            state["last_checkpoint"] = f"Phase {current_phase} complete, gate {gate_id} pending"
            state = state_manager.save(self.project_root, state)
            return DispatchResult(
                state=state,
                action="gate_pending",
                gate_pending=True,
                message=f"Gate {gate_id} requires human input",
            )

        # Determine next phase
        next_phase = self._next_phase(state, current_phase)
        if next_phase is None:
            return self._handle_completion(state)

        state["current_phase"] = next_phase
        state["last_checkpoint"] = f"Phase {current_phase} complete"
        state = state_manager.save(self.project_root, state)

        return DispatchResult(
            state=state,
            action="continue",
            next_phase=next_phase,
            message=f"Phase {current_phase} complete, next: {next_phase}",
        )

    def _should_skip_phase(self, state: dict, phase: str) -> bool:
        """Check if a phase should be skipped based on conditions."""
        # Phase 1.5 (ideation) skipped for foundation docs
        if phase == "1.5":
            doc = state.get("current_document")
            if doc and doc.get("type") in SKIP_IDEATION_TYPES:
                return True
            # Also skip if human explicitly requested skip
            if self.skip_ideation:
                return True
        return False

    def _next_phase(self, state: dict, current_phase: str) -> Optional[str]:
        """Determine the next phase after current_phase.

        Handles:
        - Normal document phase progression
        - Document loop (more docs → back to Phase 1)
        - Post-document phases (6.5, 7)
        """
        # Document phases
        if current_phase in DOCUMENT_PHASES:
            idx = DOCUMENT_PHASES.index(current_phase)
            if idx < len(DOCUMENT_PHASES) - 1:
                return DOCUMENT_PHASES[idx + 1]
            # End of document phases — check for more documents
            if state.get("documents_pending"):
                return "1"  # Loop back to intake for next doc
            # No more docs — move to post-document phases
            return POST_DOCUMENT_PHASES[0]

        # Post-document phases
        if current_phase in POST_DOCUMENT_PHASES:
            idx = POST_DOCUMENT_PHASES.index(current_phase)
            if idx < len(POST_DOCUMENT_PHASES) - 1:
                return POST_DOCUMENT_PHASES[idx + 1]
            return None  # All done

        return None

    def _handle_completion(self, state: dict) -> DispatchResult:
        """Handle run completion."""
        state["run_status"] = "completed"
        state["last_checkpoint"] = "Run complete"
        state = state_manager.save(self.project_root, state)
        return DispatchResult(
            state=state,
            action="complete",
            message="All phases complete. Run finished.",
        )
