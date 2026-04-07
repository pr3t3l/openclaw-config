"""Tests for state_manager.py — TASK-001."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from planner import state_manager


@pytest.fixture
def project_root(tmp_path: Path) -> str:
    return str(tmp_path)


class TestCreateRun:
    def test_creates_valid_state(self, project_root: str) -> None:
        state = state_manager.create_run(
            project_root=project_root,
            project_id="test-project",
            documents_pending=["PROJECT_FOUNDATION.md", "CONSTITUTION.md"],
        )
        assert state["run_status"] == "active"
        assert state["state_version"] == 1
        assert state["schema_version"] == "1.0.0"
        assert state["current_phase"] == "0"
        assert state["current_document"] is None
        assert state["documents_pending"] == ["PROJECT_FOUNDATION.md", "CONSTITUTION.md"]
        assert state["documents_completed"] == []
        assert state["cost"]["total_usd"] == 0.0

    def test_run_id_format(self, project_root: str) -> None:
        state = state_manager.create_run(
            project_root=project_root,
            project_id="test",
            documents_pending=[],
        )
        assert state["run_id"].startswith("RUN-")
        parts = state["run_id"].split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 3  # NNN

    def test_explicit_run_id(self, project_root: str) -> None:
        state = state_manager.create_run(
            project_root=project_root,
            project_id="test",
            documents_pending=[],
            run_id="RUN-20260406-001",
        )
        assert state["run_id"] == "RUN-20260406-001"

    def test_creates_run_directories(self, project_root: str) -> None:
        state = state_manager.create_run(
            project_root=project_root,
            project_id="test",
            documents_pending=[],
        )
        run_dir = Path(project_root) / "planner_runs" / state["run_id"]
        assert run_dir.exists()
        for subdir in ["drafts", "audits", "decision_logs", "history_archive", "output"]:
            assert (run_dir / subdir).exists()

    def test_state_file_written(self, project_root: str) -> None:
        state = state_manager.create_run(
            project_root=project_root,
            project_id="test",
            documents_pending=[],
        )
        path = Path(project_root) / "planner_runs" / state["run_id"] / "planner_state.json"
        assert path.exists()
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == state

    def test_sequential_run_ids(self, project_root: str) -> None:
        s1 = state_manager.create_run(project_root, "test", [])
        s2 = state_manager.create_run(project_root, "test2", [])
        # Same date, sequential numbers
        seq1 = int(s1["run_id"].split("-")[-1])
        seq2 = int(s2["run_id"].split("-")[-1])
        assert seq2 == seq1 + 1


class TestLoad:
    def test_load_valid_state(self, project_root: str) -> None:
        created = state_manager.create_run(project_root, "test", ["DOC.md"])
        loaded = state_manager.load(project_root, created["run_id"])
        assert loaded == created

    def test_load_missing_file(self, project_root: str) -> None:
        with pytest.raises(FileNotFoundError):
            state_manager.load(project_root, "RUN-99999999-999")

    def test_load_invalid_state(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "test", [])
        path = Path(project_root) / "planner_runs" / state["run_id"] / "planner_state.json"
        # Corrupt the file
        with open(path, "w") as f:
            json.dump({"invalid": True}, f)
        with pytest.raises(ValueError, match="State validation failed"):
            state_manager.load(project_root, state["run_id"])


class TestSave:
    def test_save_increments_version(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "test", [])
        assert state["state_version"] == 1
        state = state_manager.save(project_root, state)
        assert state["state_version"] == 2
        state = state_manager.save(project_root, state)
        assert state["state_version"] == 3

    def test_save_updates_timestamp(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "test", [])
        old_ts = state["updated_at"]
        state = state_manager.save(project_root, state)
        assert state["updated_at"] >= old_ts

    def test_save_persists_changes(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "test", ["DOC.md"])
        state["current_phase"] = "1"
        state["run_status"] = "paused"
        state = state_manager.save(project_root, state)
        loaded = state_manager.load(project_root, state["run_id"])
        assert loaded["current_phase"] == "1"
        assert loaded["run_status"] == "paused"
        assert loaded["state_version"] == 2

    def test_save_rejects_invalid_state(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "test", [])
        state["run_status"] = "INVALID_STATUS"
        with pytest.raises(ValueError, match="State validation failed"):
            state_manager.save(project_root, state)


class TestValidate:
    def test_valid_state(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "test", [])
        assert state_manager.validate(state) == []

    def test_invalid_run_id(self) -> None:
        errors = state_manager.validate({"run_id": "bad-id"})
        assert len(errors) > 0

    def test_missing_required_fields(self) -> None:
        errors = state_manager.validate({})
        assert len(errors) > 0


class TestSchemaVersion:
    def test_schema_version_present(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "test", [])
        assert "schema_version" in state
        assert state["schema_version"] == "1.0.0"

    def test_schema_file_has_version(self) -> None:
        with open(state_manager._schema_path) as f:
            schema = json.load(f)
        assert "schema_version" in schema


class TestListAndFind:
    def test_list_empty(self, project_root: str) -> None:
        assert state_manager.list_runs(project_root) == []

    def test_list_runs(self, project_root: str) -> None:
        state_manager.create_run(project_root, "proj-a", [])
        state_manager.create_run(project_root, "proj-b", [])
        runs = state_manager.list_runs(project_root)
        assert len(runs) == 2

    def test_find_active_run(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "proj-a", [])
        found = state_manager.find_active_run(project_root, "proj-a")
        assert found == state["run_id"]

    def test_find_no_active_run(self, project_root: str) -> None:
        state = state_manager.create_run(project_root, "proj-a", [])
        state["run_status"] = "completed"
        state_manager.save(project_root, state)
        assert state_manager.find_active_run(project_root, "proj-a") is None

    def test_find_wrong_project(self, project_root: str) -> None:
        state_manager.create_run(project_root, "proj-a", [])
        assert state_manager.find_active_run(project_root, "proj-b") is None
