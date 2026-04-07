"""Tests for reentry/impact.py — TASK-037."""

import pytest

from planner.reentry.impact import build_graph, compute_impact, mark_tasks


TASKS_WITH_DEPS = """# tasks.md

### TASK-001: Foundation
- depends_on: []

### TASK-002: State manager
- depends_on: [TASK-001]

### TASK-003: API
- depends_on: [TASK-001, TASK-002]

### TASK-004: Tests
- depends_on: [TASK-003]

### TASK-005: Independent
- depends_on: []
"""


class TestBuildGraph:
    def test_parses_deps(self):
        graph = build_graph(TASKS_WITH_DEPS)
        assert graph["TASK-001"] == []
        assert graph["TASK-002"] == ["TASK-001"]
        assert set(graph["TASK-003"]) == {"TASK-001", "TASK-002"}
        assert graph["TASK-004"] == ["TASK-003"]
        assert graph["TASK-005"] == []

    def test_all_tasks_present(self):
        graph = build_graph(TASKS_WITH_DEPS)
        assert len(graph) == 5

    def test_empty_content(self):
        assert build_graph("") == {}


class TestComputeImpact:
    def test_blocker_at_root(self):
        graph = build_graph(TASKS_WITH_DEPS)
        report = compute_impact(graph, "TASK-001")
        assert "TASK-002" in report.void_tasks  # Direct dep
        assert "TASK-003" in report.void_tasks or "TASK-003" in report.needs_review_tasks
        assert "TASK-005" in report.valid_tasks  # Independent

    def test_blocker_at_leaf(self):
        graph = build_graph(TASKS_WITH_DEPS)
        report = compute_impact(graph, "TASK-004")
        # Nothing depends on TASK-004
        assert len(report.void_tasks) == 0
        assert "TASK-001" in report.valid_tasks

    def test_blocker_mid_chain(self):
        graph = build_graph(TASKS_WITH_DEPS)
        report = compute_impact(graph, "TASK-002")
        assert "TASK-003" in report.void_tasks  # Direct dep on TASK-002
        # TASK-004 depends on TASK-003 which is VOID
        assert "TASK-004" in report.void_tasks or "TASK-004" in report.needs_review_tasks
        assert "TASK-001" in report.valid_tasks
        assert "TASK-005" in report.valid_tasks

    def test_independent_unaffected(self):
        graph = build_graph(TASKS_WITH_DEPS)
        report = compute_impact(graph, "TASK-001")
        assert "TASK-005" in report.valid_tasks

    def test_impact_has_reasons(self):
        graph = build_graph(TASKS_WITH_DEPS)
        report = compute_impact(graph, "TASK-001")
        for impact in report.impacts:
            assert len(impact.reason) > 0


class TestMarkTasks:
    def test_marks_void(self):
        graph = build_graph(TASKS_WITH_DEPS)
        report = compute_impact(graph, "TASK-001")
        marked = mark_tasks(TASKS_WITH_DEPS, report)
        assert "[VOID]" in marked
        assert "[VALID]" in marked

    def test_preserves_content(self):
        graph = build_graph(TASKS_WITH_DEPS)
        report = compute_impact(graph, "TASK-001")
        marked = mark_tasks(TASKS_WITH_DEPS, report)
        assert "Foundation" in marked
        assert "depends_on" in marked
