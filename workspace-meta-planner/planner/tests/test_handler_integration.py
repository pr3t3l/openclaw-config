"""Integration test: real handlers through dispatcher with schema validation.

Verifies that phase handlers never put extra fields in state dict,
which would cause state_manager.save() to fail (additionalProperties: false).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from planner import state_manager
from planner.orchestrator.dispatcher import Dispatcher
from planner.phase_handlers import register_all_handlers


# Schema-valid field names (from planner_state_schema.json)
SCHEMA_FIELDS = {
    "run_id",
    "project_id",
    "run_status",
    "locked_by",
    "locked_until",
    "state_version",
    "schema_version",
    "current_phase",
    "current_document",
    "last_checkpoint",
    "documents_completed",
    "documents_pending",
    "decision_logs",
    "entity_maps",
    "cost",
    "created_at",
    "updated_at",
    "pending_gate",
}

# The only allowed transient key — dispatcher pops it before save
TRANSIENT_KEYS = {"_gate_pending"}


def _mock_call_model(role="primary", prompt="", context=None, phase="0",
                     document=None, max_tokens=8192, temperature=0.7,
                     provider=None, model=None, **kwargs):
    """Mock ModelGateway.call_model that returns plausible content."""
    return {
        "content": f"Mock content for phase {phase}, section from prompt.",
        "model": model or "mock-model",
        "tokens_in": 100,
        "tokens_out": 50,
        "cost_usd": 0.001,
        "duration": 0.1,
    }


def _assert_state_schema_clean(state: dict, phase_label: str):
    """Assert that state only contains schema-valid fields (plus _gate_pending)."""
    extra = set(state.keys()) - SCHEMA_FIELDS - TRANSIENT_KEYS
    assert extra == set(), (
        f"After {phase_label}: state has extra fields not in schema: {extra}. "
        f"These will cause state_manager.save() to fail with additionalProperties: false."
    )


def _assert_save_succeeds(project_root: str, state: dict, phase_label: str):
    """Assert that state_manager.validate() passes (same check save() does)."""
    clean = dict(state)
    clean.pop("_gate_pending", None)
    errors = state_manager.validate(clean)
    assert errors == [], (
        f"After {phase_label}: state fails schema validation: {errors}"
    )


@pytest.fixture
def project_root(tmp_path):
    """Set up a project root with template stubs so phase handlers don't crash."""
    root = tmp_path / "project"
    root.mkdir()

    # Create docs dir with a minimal LESSONS_LEARNED so Phase 4 has content
    docs = root / "docs"
    docs.mkdir()
    (docs / "LESSONS_LEARNED.md").write_text(
        "# Lessons Learned\n\n## LL-001\nAlways validate inputs.\n"
    )

    return str(root)


@pytest.fixture
def run_state(project_root):
    return state_manager.create_run(
        project_root, "integration-test", ["spec.md"]
    )


@pytest.fixture
def mock_gateway():
    """Patch ModelGateway.call_model to avoid real LiteLLM calls."""
    with patch("planner.phase_handlers.ModelGateway") as MockGW:
        instance = MagicMock()
        instance.call_model.side_effect = _mock_call_model
        MockGW.return_value = instance
        yield instance


class TestHandlerSchemaCompliance:
    """Verify that real phase handlers never pollute state with extra fields."""

    def test_phase0_no_extra_fields(self, project_root, run_state):
        """Phase 0 handler should only set schema-valid fields."""
        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        _assert_state_schema_clean(state, "Phase 0")
        assert result.action == "gate_pending"
        assert state["pending_gate"] == "G0"

    def test_phase1_no_extra_fields(self, project_root, run_state, mock_gateway):
        """Phase 1 handler must save intake_answers to file, not state."""
        # Advance past Phase 0 gate
        run_state["current_phase"] = "1"
        run_state["documents_pending"] = ["CONSTITUTION.md"]
        run_state = state_manager.save(project_root, run_state)

        # Create input.txt so Phase 1 has a project idea
        run_dir = Path(project_root) / "planner_runs" / run_state["run_id"]
        (run_dir / "input.txt").write_text("Build a todo CLI app")

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        _assert_state_schema_clean(state, "Phase 1")
        _assert_save_succeeds(project_root, state, "Phase 1")

        # Verify intake_answers.json was created with real content (not placeholders)
        answers_path = run_dir / "intake_answers.json"
        assert answers_path.exists(), "intake_answers.json not created"
        answers = json.loads(answers_path.read_text())
        assert len(answers) > 0, "intake_answers.json is empty"
        for section, content in answers.items():
            assert "[Pending human input" not in content, (
                f"Section '{section}' has placeholder instead of real content"
            )

    def test_dispatch_loop_no_extra_fields(self, project_root, run_state):
        """Run dispatcher in a loop — every phase must leave state schema-clean."""
        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        state = run_state
        phases_visited = []

        for i in range(30):  # safety limit
            phase_before = state["current_phase"]
            result = d.dispatch_phase(state)
            state = result.state
            phases_visited.append(phase_before)

            _assert_state_schema_clean(state, f"Phase {phase_before} (step {i})")

            if result.action in ("gate_pending", "complete", "error", "cost_alert"):
                break

        # Should have visited at least Phase 0
        assert len(phases_visited) >= 1

    def test_save_roundtrip_after_phase0(self, project_root, run_state):
        """After Phase 0, state must survive save→load roundtrip."""
        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        # The dispatcher already saved. Verify we can load it back.
        loaded = state_manager.load(project_root, state["run_id"])
        assert loaded["pending_gate"] == "G0"
        assert loaded["run_id"] == state["run_id"]

    def test_phase1_calls_model_per_section(self, project_root, run_state, mock_gateway):
        """Phase 1 must call the model for each template section."""
        run_state["current_phase"] = "1"
        run_state["documents_pending"] = ["CONSTITUTION.md"]
        run_state = state_manager.save(project_root, run_state)

        run_dir = Path(project_root) / "planner_runs" / run_state["run_id"]
        (run_dir / "input.txt").write_text("Build an e-commerce API with Stripe")

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)

        # Verify model was called (at least once per section)
        assert mock_gateway.call_model.call_count > 0, (
            "Phase 1 did not call model — intake is generating placeholders instead"
        )
        # Verify all calls used phase="1"
        for call in mock_gateway.call_model.call_args_list:
            assert call.kwargs.get("phase") == "1" or call[1].get("phase") == "1"
