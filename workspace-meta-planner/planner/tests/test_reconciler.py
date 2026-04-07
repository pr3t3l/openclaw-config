"""Tests for reentry/reconciler.py — TASK-036."""

import pytest
from pathlib import Path

from planner.reentry.reconciler import map_files_to_tasks, produce_status


TASKS_CONTENT = """# tasks.md

### TASK-001: Create project structure
- Files touched: `src/__init__.py`, `src/config.py`

### TASK-002: Build state manager
- Files touched: `src/state_manager.py`, `src/tests/test_state.py`

### TASK-003: Build API
- Files touched: `src/api.py`
"""


class TestMapFilesToTasks:
    def test_maps_known_files(self):
        files = ["src/__init__.py", "src/config.py", "src/state_manager.py"]
        mapping = map_files_to_tasks(files, TASKS_CONTENT)
        assert mapping["src/__init__.py"] == "TASK-001"
        assert mapping["src/state_manager.py"] == "TASK-002"

    def test_unmapped_files(self):
        files = ["src/unknown.py"]
        mapping = map_files_to_tasks(files, TASKS_CONTENT)
        assert mapping["src/unknown.py"] is None

    def test_empty_files(self):
        assert map_files_to_tasks([], TASKS_CONTENT) == {}


class TestProduceStatus:
    def test_status_report(self):
        mapping = {
            "src/__init__.py": "TASK-001",
            "src/config.py": "TASK-001",
            "src/state_manager.py": "TASK-002",
            "src/unknown.py": None,
        }
        report = produce_status(mapping, TASKS_CONTENT)
        assert "TASK-001" in report.tasks_completed
        assert "TASK-002" in report.tasks_completed
        assert "TASK-003" in report.tasks_not_started
        assert report.total_files == 4
        assert len(report.summary) > 0

    def test_empty_mapping(self):
        report = produce_status({}, TASKS_CONTENT)
        assert report.total_files == 0
        assert "TASK-001" in report.tasks_not_started
