"""Tests for orchestrator/checkpoint.py — TASK-009."""

import pytest

from planner import state_manager
from planner.state_manager import RunLockedException
from planner.orchestrator.checkpoint import CheckpointManager, StaleResumeError


@pytest.fixture
def project_root(tmp_path):
    return str(tmp_path)


@pytest.fixture
def active_run(project_root):
    return state_manager.create_run(
        project_root, "test-project", ["DOC_A.md", "DOC_B.md"],
    )


@pytest.fixture
def checkpoint(project_root):
    return CheckpointManager(project_root)


class TestSaveCheckpoint:
    def test_saves_checkpoint(self, project_root, active_run, checkpoint):
        state = checkpoint.save_checkpoint(active_run, "G0", "Please confirm mode")
        assert "G0" in state["last_checkpoint"]
        assert state["locked_by"] is None  # Lock released

    def test_checkpoint_persists(self, project_root, active_run, checkpoint):
        state = checkpoint.save_checkpoint(active_run, "G1")
        loaded = state_manager.load(project_root, state["run_id"])
        assert "G1" in loaded["last_checkpoint"]

    def test_releases_lock(self, project_root, active_run, checkpoint):
        # Acquire lock first
        state = state_manager.acquire_lock(project_root, active_run)
        assert state["locked_by"] is not None
        state = checkpoint.save_checkpoint(state, "G0")
        assert state["locked_by"] is None

    def test_saves_without_lock(self, project_root, active_run, checkpoint):
        # No lock held — should still save fine
        state = checkpoint.save_checkpoint(active_run, "G0")
        assert "G0" in state["last_checkpoint"]


class TestResumeFrom:
    def test_resume_loads_state(self, project_root, active_run, checkpoint):
        checkpoint.save_checkpoint(active_run, "G0")
        state = checkpoint.resume_from(active_run["run_id"])
        assert state["run_id"] == active_run["run_id"]
        assert state["locked_by"] is not None  # Lock acquired

    def test_resume_acquires_lock(self, project_root, active_run, checkpoint):
        checkpoint.save_checkpoint(active_run, "G0")
        state = checkpoint.resume_from(active_run["run_id"])
        assert state["locked_by"] == "planner_orchestrator"

    def test_resume_missing_run(self, project_root, checkpoint):
        with pytest.raises(FileNotFoundError):
            checkpoint.resume_from("RUN-99999999-999")

    def test_stale_version_rejected(self, project_root, active_run, checkpoint):
        checkpoint.save_checkpoint(active_run, "G0")
        with pytest.raises(StaleResumeError) as exc_info:
            checkpoint.resume_from(active_run["run_id"], expected_version=1)
        assert exc_info.value.expected == 1

    def test_correct_version_accepted(self, project_root, active_run, checkpoint):
        state = checkpoint.save_checkpoint(active_run, "G0")
        loaded = checkpoint.resume_from(state["run_id"], expected_version=state["state_version"])
        assert loaded["run_id"] == state["run_id"]

    def test_resume_detects_completed_run(self, project_root, active_run, checkpoint):
        active_run["run_status"] = "completed"
        state_manager.save(project_root, active_run)
        state = checkpoint.resume_from(active_run["run_id"])
        assert state["run_status"] == "degraded"  # Flagged as inconsistent

    def test_resume_locked_run_raises(self, project_root, active_run, checkpoint):
        state = state_manager.acquire_lock(
            project_root, active_run, locked_by="other_process"
        )
        with pytest.raises(RunLockedException):
            checkpoint.resume_from(state["run_id"])


class TestConsistencyCheck:
    def test_clean_state(self, project_root, active_run, checkpoint):
        issues = checkpoint._consistency_check(active_run)
        assert issues == []

    def test_invalid_phase(self, project_root, active_run, checkpoint):
        active_run["current_phase"] = "99"
        issues = checkpoint._consistency_check(active_run)
        assert any("Invalid phase" in i for i in issues)

    def test_doc_in_completed(self, project_root, active_run, checkpoint):
        active_run["current_document"] = {
            "name": "DOC_A.md", "version": 1,
            "phase_status": "intake", "phase_attempt": 1,
        }
        active_run["documents_completed"] = ["DOC_A.md"]
        issues = checkpoint._consistency_check(active_run)
        assert any("already in documents_completed" in i for i in issues)

    def test_non_resumable_status(self, project_root, active_run, checkpoint):
        active_run["run_status"] = "failed"
        issues = checkpoint._consistency_check(active_run)
        assert any("not resumable" in i for i in issues)


class TestGetCheckpointInfo:
    def test_returns_info(self, project_root, active_run, checkpoint):
        info = checkpoint.get_checkpoint_info(active_run["run_id"])
        assert info["run_id"] == active_run["run_id"]
        assert info["run_status"] == "active"
        assert info["current_phase"] == "0"
        assert "cost_total" in info
        assert "state_version" in info

    def test_info_with_document(self, project_root, active_run, checkpoint):
        active_run["current_document"] = {
            "name": "CONSTITUTION.md", "version": 1,
            "phase_status": "intake", "phase_attempt": 1,
        }
        state_manager.save(project_root, active_run)
        info = checkpoint.get_checkpoint_info(active_run["run_id"])
        assert info["current_document"] == "CONSTITUTION.md"
