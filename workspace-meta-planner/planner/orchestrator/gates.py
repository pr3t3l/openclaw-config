"""Gate engine — evaluates gate conditions and triggers fail actions.

Each gate (G0-G7) has evaluation logic, fail actions, and result logging.
See spec.md §3 (Gate Criteria table).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of evaluating a gate."""
    gate_id: str
    passed: bool
    fail_reasons: list[str] = field(default_factory=list)
    requires_human: bool = False
    fail_action: str = ""
    message: str = ""


# Gate definitions with their pass conditions and fail actions
GATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "G0": {
        "after_phase": "0",
        "description": "Mode detected, doc type confirmed, PII scan clean, doc list confirmed",
        "requires_human": True,
        "fail_action": "clarify_or_redact",
    },
    "G1": {
        "after_phase": "1",
        "description": "Human confirms idea captured properly",
        "requires_human": True,
        "fail_action": "propose_assumed_default",
    },
    "G1.5": {
        "after_phase": "1.5",
        "description": "Human accepted/rejected ideation or skipped",
        "requires_human": True,
        "fail_action": "skip_ideation",
    },
    "G2": {
        "after_phase": "2",
        "description": "Document has all sections filled, no stubs",
        "requires_human": False,
        "fail_action": "redraft_sections",
    },
    "G2.5": {
        "after_phase": "2.5",
        "description": "Safe AF patterns auto-fixed; semantic flags highlighted",
        "requires_human": False,
        "fail_action": "review_semantic_flags",
    },
    "G3": {
        "after_phase": "3",
        "description": "Audit triage: 0 critical issues remaining; conflicts resolved",
        "requires_human": True,
        "fail_action": "resolve_criticals",
    },
    "G4": {
        "after_phase": "4",
        "description": "0 lesson violations",
        "requires_human": False,
        "fail_action": "fix_violations",
    },
    "G5": {
        "after_phase": "5",
        "description": "Human approves document",
        "requires_human": True,
        "fail_action": "another_round",
    },
    "G6.5": {
        "after_phase": "6.5",
        "description": "0 cross-document contradictions",
        "requires_human": True,
        "fail_action": "resolve_contradictions",
    },
    "G7": {
        "after_phase": "7",
        "description": "Plan+tasks pass audit, human approves",
        "requires_human": True,
        "fail_action": "revise_plan",
    },
}


class GateEngine:
    """Evaluates gates and determines pass/fail with actions."""

    def __init__(self, custom_evaluators: Optional[dict] = None) -> None:
        """
        Args:
            custom_evaluators: Optional dict of gate_id → callable(state) → GateResult.
                             Used for gates with programmatic checks (G2, G2.5, G4).
        """
        self._evaluators: dict[str, Any] = custom_evaluators or {}

    def register_evaluator(self, gate_id: str, evaluator: Any) -> None:
        """Register a custom evaluator for a gate."""
        self._evaluators[gate_id] = evaluator

    def evaluate_gate(self, gate_id: str, state: dict) -> GateResult:
        """Evaluate a gate.

        For gates with custom evaluators (structural checks), runs the evaluator.
        For human-required gates, returns a pending result for human input.

        Args:
            gate_id: Gate identifier (G0-G7).
            state: Current planner state.

        Returns:
            GateResult with pass/fail and required actions.
        """
        if gate_id not in GATE_DEFINITIONS:
            return GateResult(
                gate_id=gate_id,
                passed=False,
                fail_reasons=[f"Unknown gate: {gate_id}"],
                message=f"Unknown gate: {gate_id}",
            )

        gate_def = GATE_DEFINITIONS[gate_id]

        # Run custom evaluator if registered
        if gate_id in self._evaluators:
            result = self._evaluators[gate_id](state)
            if isinstance(result, GateResult):
                return result

        # PII gate (G0) — special blocking behavior
        if gate_id == "G0":
            return self._evaluate_g0(state, gate_def)

        # Structural validation gate (G2)
        if gate_id == "G2":
            return self._evaluate_g2(state, gate_def)

        # Lessons check gate (G4)
        if gate_id == "G4":
            return self._evaluate_g4(state, gate_def)

        # Human-required gates — return pending
        if gate_def["requires_human"]:
            return GateResult(
                gate_id=gate_id,
                passed=False,
                requires_human=True,
                fail_action=gate_def["fail_action"],
                message=f"Gate {gate_id}: {gate_def['description']} — awaiting human input",
            )

        # Auto-pass for gates without specific logic
        return GateResult(
            gate_id=gate_id,
            passed=True,
            message=f"Gate {gate_id} auto-passed",
        )

    def resolve_gate(self, gate_id: str, approved: bool, notes: str = "") -> GateResult:
        """Resolve a human-pending gate.

        Args:
            gate_id: Gate identifier.
            approved: Whether the human approved.
            notes: Optional human notes.

        Returns:
            Updated GateResult.
        """
        if approved:
            return GateResult(
                gate_id=gate_id,
                passed=True,
                message=f"Gate {gate_id} approved by human. {notes}".strip(),
            )

        gate_def = GATE_DEFINITIONS.get(gate_id, {})
        return GateResult(
            gate_id=gate_id,
            passed=False,
            fail_reasons=[notes or "Human rejected"],
            fail_action=gate_def.get("fail_action", ""),
            message=f"Gate {gate_id} rejected by human: {notes}",
        )

    def gate_for_phase(self, phase: str) -> Optional[str]:
        """Get the gate ID for a given phase, if any."""
        for gate_id, gate_def in GATE_DEFINITIONS.items():
            if gate_def["after_phase"] == phase:
                return gate_id
        return None

    def _evaluate_g0(self, state: dict, gate_def: dict) -> GateResult:
        """G0: Mode detected, PII scan clean, doc list confirmed."""
        fails = []

        # Check PII scan results
        pii_results = state.get("pii_scan_results")
        if pii_results and pii_results.get("high_confidence_hits"):
            fails.append(
                f"PII scan found {len(pii_results['high_confidence_hits'])} high-confidence secrets. "
                "Must be resolved before proceeding."
            )

        if fails:
            return GateResult(
                gate_id="G0",
                passed=False,
                fail_reasons=fails,
                requires_human=True,
                fail_action="clarify_or_redact",
                message="Gate G0 failed: PII issues detected",
            )

        return GateResult(
            gate_id="G0",
            passed=False,
            requires_human=True,
            fail_action=gate_def["fail_action"],
            message="Gate G0: Confirm mode, doc list, and PII scan results",
        )

    def _evaluate_g2(self, state: dict, gate_def: dict) -> GateResult:
        """G2: Document has all sections filled, no stubs."""
        doc = state.get("current_document", {})
        validation = doc.get("validation_result")

        if validation is None:
            return GateResult(
                gate_id="G2",
                passed=False,
                fail_reasons=["No validation result available"],
                fail_action="redraft_sections",
                message="Gate G2: Document not validated yet",
            )

        if not validation.get("passed", False):
            violations = validation.get("violations", [])
            reasons = [f"Line {v.get('line', '?')}: {v.get('pattern', '?')}" for v in violations[:5]]
            return GateResult(
                gate_id="G2",
                passed=False,
                fail_reasons=reasons,
                fail_action="redraft_sections",
                message=f"Gate G2 failed: {len(violations)} validation issues",
            )

        return GateResult(
            gate_id="G2",
            passed=True,
            message="Gate G2 passed: Document structurally valid",
        )

    def _evaluate_g4(self, state: dict, gate_def: dict) -> GateResult:
        """G4: 0 lesson violations."""
        lessons_check = state.get("lessons_check_result", {})
        violations = lessons_check.get("violations", [])

        if violations:
            reasons = [f"{v.get('id', '?')}: {v.get('description', '?')}" for v in violations[:5]]
            return GateResult(
                gate_id="G4",
                passed=False,
                fail_reasons=reasons,
                fail_action="fix_violations",
                message=f"Gate G4 failed: {len(violations)} lesson violations",
            )

        return GateResult(
            gate_id="G4",
            passed=True,
            message="Gate G4 passed: 0 lesson violations",
        )
