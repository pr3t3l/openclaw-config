"""Tests for orchestrator/dispatcher.py — TASK-007."""

import pytest

from planner import state_manager
from planner.orchestrator.dispatcher import (
    ALL_PHASES,
    DOCUMENT_PHASES,
    Dispatcher,
    DispatchResult,
    PhaseHandler,
    SKIP_IDEATION_TYPES,
)


class StubHandler(PhaseHandler):
    """Simple handler that just marks phase as done."""

    def __init__(self, phase_id: str, gate_id: str = None):
        self.phase_id = phase_id
        self._gate_id = gate_id
        self.called = False

    def execute(self, state, context):
        self.called = True
        if self._gate_id:
            state["_gate_pending"] = self._gate_id
        return state


class FailingHandler(PhaseHandler):
    def execute(self, state, context):
        raise RuntimeError("Phase exploded")


@pytest.fixture
def project_root(tmp_path):
    return str(tmp_path)


@pytest.fixture
def run_state(project_root):
    return state_manager.create_run(
        project_root, "test-proj", ["CONSTITUTION.md", "DATA_MODEL.md"]
    )


def _make_dispatcher(project_root, handlers=None):
    d = Dispatcher(project_root, phase_handlers=handlers or {})
    return d


class TestDispatchPhase:
    def test_dispatches_to_handler(self, project_root, run_state):
        h = StubHandler("0")
        d = _make_dispatcher(project_root, {"0": h})
        result = d.dispatch_phase(run_state)
        assert h.called
        assert result.action == "continue"
        assert result.next_phase == "1"

    def test_advances_through_phases(self, project_root, run_state):
        handlers = {p: StubHandler(p) for p in DOCUMENT_PHASES}
        d = _make_dispatcher(project_root, handlers)

        state = run_state
        phases_visited = []
        for _ in range(20):  # safety limit
            result = d.dispatch_phase(state)
            phases_visited.append(state["current_phase"])
            state = result.state
            if result.action != "continue":
                break

        # Should have visited multiple phases
        assert len(phases_visited) > 1

    def test_no_handler_skips(self, project_root, run_state):
        d = _make_dispatcher(project_root, {})
        result = d.dispatch_phase(run_state)
        assert result.action == "continue"
        assert result.next_phase == "1"

    def test_gate_pending(self, project_root, run_state):
        h = StubHandler("0", gate_id="G0")
        d = _make_dispatcher(project_root, {"0": h})
        result = d.dispatch_phase(run_state)
        assert result.action == "gate_pending"
        assert result.gate_pending is True
        assert "G0" in result.message

    def test_error_handling(self, project_root, run_state):
        d = _make_dispatcher(project_root, {"0": FailingHandler()})
        result = d.dispatch_phase(run_state)
        assert result.action == "error"
        assert "exploded" in result.message


class TestIdeationSkip:
    def test_skips_ideation_for_foundation(self, project_root, run_state):
        run_state["current_phase"] = "1.5"
        run_state["current_document"] = {
            "name": "CONSTITUTION.md",
            "type": "CONSTITUTION",
            "version": 1,
            "phase_status": "ideation",
            "phase_attempt": 1,
        }
        state_manager.save(project_root, run_state)

        d = _make_dispatcher(project_root, {})
        result = d.dispatch_phase(run_state)
        assert result.action == "continue"
        assert result.next_phase == "2"
        assert "skipped" in result.message.lower()

    def test_does_not_skip_ideation_for_spec(self, project_root, run_state):
        run_state["current_phase"] = "1.5"
        run_state["current_document"] = {
            "name": "spec.md",
            "type": "WORKFLOW_SPEC",
            "version": 1,
            "phase_status": "ideation",
            "phase_attempt": 1,
        }
        state_manager.save(project_root, run_state)

        h = StubHandler("1.5")
        d = _make_dispatcher(project_root, {"1.5": h})
        result = d.dispatch_phase(run_state)
        assert h.called

    def test_all_foundation_types_skip(self):
        for doc_type in SKIP_IDEATION_TYPES:
            assert doc_type in {
                "PROJECT_FOUNDATION", "CONSTITUTION", "DATA_MODEL",
                "INTEGRATIONS", "LESSONS_LEARNED"
            }

    def test_manual_skip_ideation(self, project_root, run_state):
        run_state["current_phase"] = "1.5"
        run_state["current_document"] = {
            "name": "spec.md",
            "type": "WORKFLOW_SPEC",
            "version": 1,
            "phase_status": "ideation",
            "phase_attempt": 1,
        }
        state_manager.save(project_root, run_state)

        d = _make_dispatcher(project_root, {})
        d.skip_ideation = True  # Human requested skip
        result = d.dispatch_phase(run_state)
        assert result.next_phase == "2"


class TestDocumentLoop:
    def test_loops_back_for_pending_docs(self, project_root, run_state):
        # Simulate end of document phases (phase 6)
        run_state["current_phase"] = "6"
        run_state["documents_pending"] = ["DATA_MODEL.md"]
        state_manager.save(project_root, run_state)

        h = StubHandler("6")
        d = _make_dispatcher(project_root, {"6": h})
        result = d.dispatch_phase(run_state)
        assert result.next_phase == "1"  # Back to intake

    def test_moves_to_crossdoc_when_no_pending(self, project_root, run_state):
        run_state["current_phase"] = "6"
        run_state["documents_pending"] = []
        state_manager.save(project_root, run_state)

        h = StubHandler("6")
        d = _make_dispatcher(project_root, {"6": h})
        result = d.dispatch_phase(run_state)
        assert result.next_phase == "6.5"


class TestCompletion:
    def test_completes_after_phase_7(self, project_root, run_state):
        run_state["current_phase"] = "7"
        run_state["documents_pending"] = []
        state_manager.save(project_root, run_state)

        h = StubHandler("7")
        d = _make_dispatcher(project_root, {"7": h})
        result = d.dispatch_phase(run_state)
        assert result.action == "complete"
        assert result.state["run_status"] == "completed"


class TestCostAlert:
    def test_hard_stop_at_limit(self, project_root, run_state):
        run_state["cost"]["total_usd"] = 50.0
        state_manager.save(project_root, run_state)

        d = _make_dispatcher(project_root, {"0": StubHandler("0")})
        result = d.dispatch_phase(run_state)
        assert result.action == "cost_alert"
        assert "HARD LIMIT" in result.message

    def test_continues_below_limit(self, project_root, run_state):
        run_state["cost"]["total_usd"] = 29.0
        state_manager.save(project_root, run_state)

        d = _make_dispatcher(project_root, {"0": StubHandler("0")})
        result = d.dispatch_phase(run_state)
        assert result.action == "continue"
