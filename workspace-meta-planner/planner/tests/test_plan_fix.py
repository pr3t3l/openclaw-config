"""Tests for reentry/ patcher, reaudit, delta_tasks, coordinator — TASK-038/039."""

import pytest
from pathlib import Path

from planner.reentry.patcher import patch_spec
from planner.reentry.reaudit import selective_reaudit
from planner.reentry.delta_tasks import generate_delta_tasks
from planner.reentry.impact import ImpactReport, TaskImpact
from planner.reentry.coordinator import run_plan_fix


SPEC = "# Spec\n\n## 1. Purpose\nBuild planner.\n\n## 2. Stack\nPostgreSQL."

TASKS = """# tasks.md

### TASK-001: Setup
- depends_on: []
- Files touched: `src/__init__.py`

### TASK-002: API
- depends_on: [TASK-001]
- Files touched: `src/api.py`

### TASK-003: Tests
- depends_on: [TASK-002]
- Files touched: `src/tests.py`
"""


def _mock_gateway(content="Patched spec content. No issues found. Correct."):
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, context=None, phase="fix", document=None, **kw):
            self.calls.append(role)
            return {"content": content, "tokens_in": 200, "tokens_out": 300}
    return MockGW()


class TestPatchSpec:
    def test_patches(self):
        gw = _mock_gateway("# Patched Spec\n## 1. Purpose\nUpdated purpose.")
        result = patch_spec(SPEC, "Auth flow broken", ["1. Purpose"], gw)
        assert len(result) > 0

    def test_uses_primary(self):
        gw = _mock_gateway()
        patch_spec(SPEC, "blocker", [], gw)
        assert "primary" in gw.calls


class TestSelectiveReaudit:
    def test_passes_clean(self):
        gw = _mock_gateway("No issues found. Everything looks correct.")
        result = selective_reaudit("patched spec", ["§1"], gw)
        assert result["passed"]

    def test_fails_with_issues(self):
        gw = _mock_gateway("Found 2 new problems with the patched sections.")
        result = selective_reaudit("patched spec", ["§1"], gw)
        assert not result["passed"]

    def test_uses_auditor(self):
        gw = _mock_gateway()
        selective_reaudit("spec", ["§1"], gw)
        assert "auditor_gpt" in gw.calls


class TestDeltaTasks:
    def test_generates_for_void(self):
        report = ImpactReport(blocker_task="TASK-001", impacts=[
            TaskImpact("TASK-002", "VOID", "Direct dep"),
            TaskImpact("TASK-003", "VALID", "Unaffected"),
        ])
        gw = _mock_gateway("### TASK-002-v2: Rebuilt API\n- Objective: New API")
        result = generate_delta_tasks(report, "patched spec", "code summary", gw)
        assert "TASK-002" in result or "API" in result

    def test_no_void_no_tasks(self):
        report = ImpactReport(blocker_task="TASK-001", impacts=[
            TaskImpact("TASK-002", "VALID", "OK"),
        ])
        gw = _mock_gateway()
        result = generate_delta_tasks(report, "spec", "code", gw)
        assert "No VOID" in result


class TestCoordinator:
    def test_full_flow(self, tmp_path):
        # Create a minimal project
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__init__.py").write_text("")

        gw = _mock_gateway("Patched. No issues. Correct. New tasks generated.")
        result = run_plan_fix(
            str(tmp_path), TASKS, SPEC,
            "TASK-001", "Auth flow doesn't work", gw,
        )
        assert len(result.reconciliation_summary) > 0
        assert len(result.impact_summary) > 0
        assert result.patched_spec

    def test_handles_reconciliation_error(self, tmp_path):
        # Non-existent path should still work (no git)
        gw = _mock_gateway()
        result = run_plan_fix(
            str(tmp_path), TASKS, SPEC,
            "TASK-001", "Blocker", gw,
        )
        # Should complete even without git
        assert len(result.impact_summary) > 0

    def test_result_fields(self, tmp_path):
        gw = _mock_gateway()
        result = run_plan_fix(str(tmp_path), TASKS, SPEC, "TASK-001", "Issue", gw)
        assert hasattr(result, "void_tasks")
        assert hasattr(result, "needs_review_tasks")
        assert hasattr(result, "patched_spec")
        assert hasattr(result, "delta_tasks")
