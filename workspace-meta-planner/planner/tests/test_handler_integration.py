"""Integration test: real handlers through dispatcher with schema validation.

Verifies that phase handlers never put extra fields in state dict,
which would cause state_manager.save() to fail (additionalProperties: false).
"""

import json
import pytest
from unittest.mock import patch

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


def _fake_call_fn(**kwargs):
    """Mock LiteLLM call that returns a plausible response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "Mock response for testing.",
                    "role": "assistant",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": kwargs.get("model", "mock-model"),
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
    # Pop transient key like dispatcher does before saving
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

    def test_phase1_no_extra_fields(self, project_root, run_state):
        """Phase 1 handler must save intake_answers to file, not state."""
        # Advance past Phase 0 gate
        run_state["current_phase"] = "1"
        run_state["documents_pending"] = ["CONSTITUTION.md"]
        run_state = state_manager.save(project_root, run_state)

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        _assert_state_schema_clean(state, "Phase 1")
        _assert_save_succeeds(project_root, state, "Phase 1")

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
        # The dispatcher should have saved state without schema errors
        # (it calls state_manager.save internally)

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
