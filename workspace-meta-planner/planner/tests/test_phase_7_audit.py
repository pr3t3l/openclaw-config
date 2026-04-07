"""Tests for plan+tasks audit (TASK-033) — reuses audit infrastructure."""

import pytest

from planner.phases.phase_3_audit import run_audit, AUDIT_CALLS


MOCK_PLAN = "# Plan\n## Phase 1\nBuild core.\n## Phase 2\nBuild API."
MOCK_TASKS = "# Tasks\n### TASK-001: Setup\n- Objective: dirs\n### TASK-002: API\n- Objective: endpoints"


def _mock_gateway():
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, context=None, phase="7", document=None, **kw):
            self.calls.append({"role": role, "prompt": prompt[:100]})
            return {
                "content": "- MINOR: Task formatting could improve",
                "model": f"mock-{role}",
                "tokens_in": 300, "tokens_out": 150,
                "cost_usd": 0.005, "duration": 1.0,
            }
    return MockGW()


def _make_state():
    return {
        "current_document": {"content": MOCK_PLAN + "\n" + MOCK_TASKS, "type": "plan"},
        "constitution": {"rules": ["Max 2 retries"]},
        "project_context": {"stack": {}, "integrations_summary": ""},
        "cross_references": [],
        "cost": {"total_usd": 0, "by_model": {}, "by_phase": {}, "by_document": {}},
    }


class TestPlanTasksAudit:
    def test_four_calls_for_plan(self, tmp_path):
        """Plan+tasks get the same 4-call audit as documents."""
        gw = _mock_gateway()
        result = run_audit(
            MOCK_PLAN + "\n\n" + MOCK_TASKS,
            "plan",
            _make_state(),
            gw,
            "RUN-20260406-001",
            str(tmp_path),
            document="plan+tasks",
            backoff=False,
        )
        assert len(result.call_results) == 4
        assert len(gw.calls) == 4

    def test_results_saved(self, tmp_path):
        gw = _mock_gateway()
        result = run_audit(
            MOCK_PLAN, "plan", _make_state(), gw,
            "RUN-20260406-001", str(tmp_path), document="plan.md", backoff=False,
        )
        assert len(result.raw_saved_paths) == 4

    def test_uses_both_providers(self, tmp_path):
        gw = _mock_gateway()
        run_audit(
            MOCK_PLAN, "plan", _make_state(), gw,
            "RUN-20260406-001", str(tmp_path), backoff=False,
        )
        roles = [c["role"] for c in gw.calls]
        assert "auditor_gpt" in roles
        assert "auditor_gemini" in roles

    def test_issue_counts(self, tmp_path):
        gw = _mock_gateway()
        result = run_audit(
            MOCK_TASKS, "tasks", _make_state(), gw,
            "RUN-20260406-001", str(tmp_path), backoff=False,
        )
        counts = result.issue_counts
        assert len(counts) == 4
