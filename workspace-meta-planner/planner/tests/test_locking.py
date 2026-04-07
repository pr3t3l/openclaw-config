"""Tests for run locking + project-level admission control — TASK-002."""

import time
from datetime import datetime, timedelta, timezone

import pytest

from planner import state_manager
from planner.state_manager import (
    ProjectAdmissionError,
    RunLockedException,
)


@pytest.fixture
def project_root(tmp_path):
    return str(tmp_path)


@pytest.fixture
def active_run(project_root):
    return state_manager.create_run(project_root, "test-project", ["DOC.md"])


class TestAcquireLock:
    def test_acquire_lock(self, project_root, active_run):
        state = state_manager.acquire_lock(project_root, active_run)
        assert state["locked_by"] == "planner_orchestrator"
        assert state["locked_until"] is not None

    def test_lock_persists(self, project_root, active_run):
        state = state_manager.acquire_lock(project_root, active_run)
        loaded = state_manager.load(project_root, state["run_id"])
        assert loaded["locked_by"] == "planner_orchestrator"

    def test_double_lock_same_owner(self, project_root, active_run):
        state = state_manager.acquire_lock(project_root, active_run)
        # Same owner can re-acquire (renew)
        state = state_manager.acquire_lock(project_root, state)
        assert state["locked_by"] == "planner_orchestrator"

    def test_double_lock_different_owner_raises(self, project_root, active_run):
        state = state_manager.acquire_lock(
            project_root, active_run, locked_by="process_A"
        )
        with pytest.raises(RunLockedException) as exc_info:
            state_manager.acquire_lock(
                project_root, state, locked_by="process_B"
            )
        assert exc_info.value.run_id == state["run_id"]
        assert exc_info.value.locked_by == "process_A"

    def test_expired_lock_reclaimable(self, project_root, active_run):
        # Acquire with 0-second TTL (immediately expired)
        state = state_manager.acquire_lock(
            project_root, active_run, locked_by="process_A", ttl_seconds=0
        )
        # Different owner can reclaim expired lock
        state = state_manager.load(project_root, state["run_id"])
        state = state_manager.acquire_lock(
            project_root, state, locked_by="process_B"
        )
        assert state["locked_by"] == "process_B"

    def test_custom_ttl(self, project_root, active_run):
        state = state_manager.acquire_lock(
            project_root, active_run, ttl_seconds=600
        )
        lock_until = datetime.fromisoformat(state["locked_until"])
        now = datetime.now(timezone.utc)
        # Should be ~10 minutes from now
        delta = (lock_until - now).total_seconds()
        assert 590 < delta < 610


class TestReleaseLock:
    def test_release_lock(self, project_root, active_run):
        state = state_manager.acquire_lock(project_root, active_run)
        assert state["locked_by"] is not None
        state = state_manager.release_lock(project_root, state)
        assert state["locked_by"] is None
        assert state["locked_until"] is None

    def test_release_persists(self, project_root, active_run):
        state = state_manager.acquire_lock(project_root, active_run)
        state = state_manager.release_lock(project_root, state)
        loaded = state_manager.load(project_root, state["run_id"])
        assert loaded["locked_by"] is None


class TestRenewLock:
    def test_renew_lock(self, project_root, active_run):
        state = state_manager.acquire_lock(project_root, active_run, ttl_seconds=60)
        old_until = state["locked_until"]
        state = state_manager.renew_lock(project_root, state, ttl_seconds=600)
        assert state["locked_until"] > old_until

    def test_renew_unlocked_raises(self, project_root, active_run):
        # Not locked
        with pytest.raises(RunLockedException):
            state_manager.renew_lock(project_root, active_run)


class TestProjectAdmission:
    def test_admission_blocks_duplicate(self, project_root):
        state_manager.create_run(project_root, "proj-a", [])
        with pytest.raises(ProjectAdmissionError) as exc_info:
            state_manager.create_run(project_root, "proj-a", [])
        assert exc_info.value.project_id == "proj-a"

    def test_admission_allows_different_projects(self, project_root):
        state_manager.create_run(project_root, "proj-a", [])
        state = state_manager.create_run(project_root, "proj-b", [])
        assert state["project_id"] == "proj-b"

    def test_admission_allows_after_completed(self, project_root):
        state = state_manager.create_run(project_root, "proj-a", [])
        state["run_status"] = "completed"
        state_manager.save(project_root, state)
        # Should work — no active run for proj-a
        new_state = state_manager.create_run(project_root, "proj-a", [])
        assert new_state["run_status"] == "active"

    def test_admission_blocks_paused(self, project_root):
        state = state_manager.create_run(project_root, "proj-a", [])
        state["run_status"] = "paused"
        state_manager.save(project_root, state)
        with pytest.raises(ProjectAdmissionError):
            state_manager.create_run(project_root, "proj-a", [])

    def test_admission_blocks_degraded(self, project_root):
        state = state_manager.create_run(project_root, "proj-a", [])
        state["run_status"] = "degraded"
        state_manager.save(project_root, state)
        with pytest.raises(ProjectAdmissionError):
            state_manager.create_run(project_root, "proj-a", [])

    def test_check_project_admission_standalone(self, project_root):
        state_manager.create_run(project_root, "proj-a", [])
        with pytest.raises(ProjectAdmissionError):
            state_manager.check_project_admission(project_root, "proj-a")
        # No error for different project
        state_manager.check_project_admission(project_root, "proj-b")
