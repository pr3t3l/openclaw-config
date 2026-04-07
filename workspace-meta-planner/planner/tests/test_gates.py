"""Tests for orchestrator/gates.py — TASK-008."""

import pytest

from planner.orchestrator.gates import (
    GATE_DEFINITIONS,
    GateEngine,
    GateResult,
)


@pytest.fixture
def engine():
    return GateEngine()


@pytest.fixture
def base_state():
    return {
        "current_document": {
            "name": "SPEC.md",
            "version": 1,
            "phase_status": "complete",
            "phase_attempt": 1,
        },
        "cost": {"total_usd": 0.0, "by_model": {}, "by_phase": {}, "by_document": {}},
    }


class TestGateDefinitions:
    def test_all_gates_defined(self):
        expected = ["G0", "G1", "G1.5", "G2", "G2.5", "G3", "G4", "G5", "G6.5", "G7"]
        for gate_id in expected:
            assert gate_id in GATE_DEFINITIONS

    def test_each_gate_has_required_fields(self):
        for gate_id, gate_def in GATE_DEFINITIONS.items():
            assert "after_phase" in gate_def
            assert "description" in gate_def
            assert "requires_human" in gate_def
            assert "fail_action" in gate_def


class TestEvaluateGate:
    def test_unknown_gate_fails(self, engine, base_state):
        result = engine.evaluate_gate("G99", base_state)
        assert result.passed is False
        assert "Unknown" in result.message

    def test_human_gates_return_pending(self, engine, base_state):
        human_gates = ["G1", "G1.5", "G3", "G5", "G6.5", "G7"]
        for gate_id in human_gates:
            result = engine.evaluate_gate(gate_id, base_state)
            assert result.requires_human is True
            assert result.passed is False  # Pending human input

    def test_custom_evaluator_used(self, engine, base_state):
        def custom_eval(state):
            return GateResult(gate_id="G2", passed=True, message="Custom pass")

        engine.register_evaluator("G2", custom_eval)
        result = engine.evaluate_gate("G2", base_state)
        assert result.passed is True
        assert result.message == "Custom pass"


class TestGateG0:
    def test_g0_pii_blocks(self, engine, base_state):
        base_state["pii_scan_results"] = {
            "high_confidence_hits": [{"pattern": "sk-xxx", "line": 5}]
        }
        result = engine.evaluate_gate("G0", base_state)
        assert result.passed is False
        assert "PII" in result.fail_reasons[0]

    def test_g0_no_pii_still_needs_human(self, engine, base_state):
        result = engine.evaluate_gate("G0", base_state)
        assert result.requires_human is True
        assert result.passed is False  # Still needs human confirmation


class TestGateG2:
    def test_g2_passes_with_valid_doc(self, engine, base_state):
        base_state["current_document"]["validation_result"] = {"passed": True, "violations": []}
        result = engine.evaluate_gate("G2", base_state)
        assert result.passed is True

    def test_g2_fails_with_violations(self, engine, base_state):
        base_state["current_document"]["validation_result"] = {
            "passed": False,
            "violations": [{"line": 10, "pattern": "TBD"}],
        }
        result = engine.evaluate_gate("G2", base_state)
        assert result.passed is False
        assert result.fail_action == "redraft_sections"

    def test_g2_fails_without_validation(self, engine, base_state):
        result = engine.evaluate_gate("G2", base_state)
        assert result.passed is False
        assert "not validated" in result.message.lower()


class TestGateG4:
    def test_g4_passes_no_violations(self, engine, base_state):
        base_state["lessons_check_result"] = {"violations": []}
        result = engine.evaluate_gate("G4", base_state)
        assert result.passed is True

    def test_g4_fails_with_violations(self, engine, base_state):
        base_state["lessons_check_result"] = {
            "violations": [{"id": "LL-PLAN-001", "description": "Missing data flow"}]
        }
        result = engine.evaluate_gate("G4", base_state)
        assert result.passed is False
        assert result.fail_action == "fix_violations"

    def test_g4_passes_no_result(self, engine, base_state):
        # No lessons check result yet — auto-passes (no violations found)
        result = engine.evaluate_gate("G4", base_state)
        assert result.passed is True


class TestResolveGate:
    def test_approve_gate(self, engine):
        result = engine.resolve_gate("G1", approved=True, notes="Looks good")
        assert result.passed is True
        assert "approved" in result.message

    def test_reject_gate(self, engine):
        result = engine.resolve_gate("G1", approved=False, notes="Missing details")
        assert result.passed is False
        assert "Missing details" in result.message
        assert result.fail_action == "propose_assumed_default"

    def test_reject_unknown_gate(self, engine):
        result = engine.resolve_gate("G99", approved=False, notes="bad")
        assert result.passed is False


class TestGateForPhase:
    def test_phase_0_gate(self, engine):
        assert engine.gate_for_phase("0") == "G0"

    def test_phase_3_gate(self, engine):
        assert engine.gate_for_phase("3") == "G3"

    def test_phase_7_gate(self, engine):
        assert engine.gate_for_phase("7") == "G7"

    def test_no_gate_for_unknown_phase(self, engine):
        assert engine.gate_for_phase("99") is None
