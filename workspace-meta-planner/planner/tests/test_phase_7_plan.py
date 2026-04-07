"""Tests for phases/phase_7_plan.py — TASK-031."""

import pytest
from planner.phases.phase_7_plan import generate_plan, generate_master_plan, PlanResult


MOCK_PLAN = """# plan.md

## Phase 1: Core
Build the foundation.

## Phase 2: API
Build the API layer.

## Phase 3: UI
Build the frontend.
"""


def _mock_gateway(content=MOCK_PLAN):
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, context=None, phase="7", document=None, **kw):
            self.calls.append({"role": role})
            return {"content": content, "tokens_in": 500, "tokens_out": 800}
    return MockGW()


class TestGeneratePlan:
    def test_generates_plan(self):
        gw = _mock_gateway()
        result = generate_plan("# Spec content", gw)
        assert isinstance(result, PlanResult)
        assert len(result.content) > 0

    def test_uses_primary(self):
        gw = _mock_gateway()
        generate_plan("# Spec", gw)
        assert gw.calls[0]["role"] == "primary"

    def test_counts_modules(self):
        gw = _mock_gateway()
        result = generate_plan("# Spec", gw)
        assert result.module_count == 3

    def test_not_large_project(self):
        gw = _mock_gateway()
        result = generate_plan("# Spec", gw)
        assert not result.is_large_project

    def test_large_project_detection(self):
        phases = "\n\n".join(f"## Phase {i}: Module {i}\nContent." for i in range(12))
        gw = _mock_gateway(f"# Plan\n\n{phases}")
        result = generate_plan("# Spec", gw)
        assert result.is_large_project
        assert result.module_count >= 10

    def test_constitution_rules_passed(self):
        calls = []
        class CaptureGW:
            def call_model(self, role, prompt, context=None, **kw):
                calls.append(prompt)
                return {"content": MOCK_PLAN, "tokens_in": 100, "tokens_out": 200}
        generate_plan("# Spec", CaptureGW(), constitution_rules="Max 2 retries")
        assert "Max 2 retries" in calls[0]


class TestGenerateMasterPlan:
    def test_generates_master(self):
        gw = _mock_gateway("Master plan content here.")
        modules = [
            {"name": "Auth", "description": "User authentication", "depends_on": []},
            {"name": "API", "description": "REST API", "depends_on": ["Auth"]},
        ]
        content = generate_master_plan(modules, gw)
        assert len(content) > 0
