"""Tests for phases/phase_7_tasks.py + task_validator.py — TASK-032."""

import pytest

from planner.phases.phase_7_tasks import generate_tasks, TasksResult
from planner.task_validator import validate_tasks, TasksValidationResult


VALID_TASKS = """# tasks.md

## Phase 1

### TASK-001: Create project structure
- Objective: Set up directories
- Inputs: spec.md §1
- Outputs: Directory tree
- Files touched: src/__init__.py
- Done when: Directories exist
- depends_on: []
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Ask human
  - CRITICAL: Re-enter spec
- Estimated: 15 min

### TASK-002: Build state manager
- Objective: Create state persistence
- Inputs: spec.md §5
- Outputs: state_manager.py
- Files touched: src/state_manager.py
- Done when: create/load/save works
- depends_on: [TASK-001]
- if_blocked:
  - MINOR: Fix
  - MODERATE: Clarify
  - CRITICAL: Re-enter spec
- Estimated: 25 min
"""

MISSING_FIELDS_TASKS = """# tasks.md

### TASK-001: Incomplete task
- Objective: Something
- Inputs: spec §1
"""

CIRCULAR_TASKS = """# tasks.md

### TASK-001: Task A
- Objective: A
- Inputs: x
- Outputs: y
- Files touched: a.py
- Done when: done
- depends_on: [TASK-002]
- if_blocked: MINOR: fix
- Estimated: 10 min

### TASK-002: Task B
- Objective: B
- Inputs: x
- Outputs: y
- Files touched: b.py
- Done when: done
- depends_on: [TASK-001]
- if_blocked: MINOR: fix
- Estimated: 10 min
"""


def _mock_gateway(content=VALID_TASKS):
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, context=None, phase="7", document=None, **kw):
            self.calls.append(role)
            return {"content": content, "tokens_in": 500, "tokens_out": 1000}
    return MockGW()


class TestValidateTasks:
    def test_valid_tasks_pass(self):
        result = validate_tasks(VALID_TASKS)
        assert result.passed
        assert result.total_tasks == 2
        assert result.invalid_count == 0

    def test_missing_fields_detected(self):
        result = validate_tasks(MISSING_FIELDS_TASKS)
        assert not result.passed
        assert result.invalid_count >= 1
        tv = result.task_results[0]
        assert len(tv.missing_fields) > 0

    def test_circular_deps_detected(self):
        result = validate_tasks(CIRCULAR_TASKS)
        assert len(result.circular_deps) >= 1

    def test_empty_content(self):
        result = validate_tasks("")
        assert result.total_tasks == 0
        assert result.passed

    def test_depends_on_valid_refs(self):
        result = validate_tasks(VALID_TASKS)
        # TASK-002 depends on TASK-001 which exists
        assert all(tv.valid for tv in result.task_results)

    def test_depends_on_invalid_ref(self):
        bad = VALID_TASKS.replace("depends_on: [TASK-001]", "depends_on: [TASK-999]")
        result = validate_tasks(bad)
        task2 = next(t for t in result.task_results if t.task_id == "TASK-002")
        assert len(task2.issues) >= 1


class TestGenerateTasks:
    def test_generates_valid(self):
        gw = _mock_gateway(VALID_TASKS)
        result = generate_tasks("# Plan", "# Spec", gw)
        assert result.validation_passed
        assert result.total_tasks == 2

    def test_retries_on_failure(self):
        call_count = 0
        class RetryGW:
            def call_model(self, role, prompt, context=None, phase="7", document=None, **kw):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"content": MISSING_FIELDS_TASKS, "tokens_in": 100, "tokens_out": 200}
                return {"content": VALID_TASKS, "tokens_in": 100, "tokens_out": 200}

        result = generate_tasks("# Plan", "# Spec", RetryGW(), max_retries=1)
        assert result.validation_passed
        assert call_count == 2

    def test_reports_errors(self):
        gw = _mock_gateway(MISSING_FIELDS_TASKS)
        result = generate_tasks("# Plan", "# Spec", gw, max_retries=0)
        assert not result.validation_passed
        assert len(result.validation_errors) > 0


class TestTasksResult:
    def test_fields(self):
        r = TasksResult("content", True, [], 5)
        assert r.content == "content"
        assert r.validation_passed
        assert r.total_tasks == 5
