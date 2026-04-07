"""Tests for phases/phase_6_records.py — TASK-029."""

import json
import pytest
from pathlib import Path

from planner.phases.phase_6_records import update_all_records


SAMPLE_HISTORY = [
    {"role": "user", "content": "Use PostgreSQL."},
    {"role": "assistant", "content": "PostgreSQL confirmed."},
]

SAMPLE_DOC = """# CONSTITUTION.md

## 1. Rules
Rule: Never retry with identical parameters.
Must always track run_id.

## 2. States
active, paused, completed.
"""


def _mock_gateway():
    class MockGW:
        def call_model(self, role, prompt, phase="6", document=None, **kw):
            return {
                "content": "EXECUTIVE SUMMARY:\nDecided on PostgreSQL.\n\nHARD DECISIONS:\n- db_choice: PostgreSQL — self-hosted",
                "tokens_in": 200, "tokens_out": 100,
            }
    return MockGW()


class TestUpdateAllRecords:
    def test_full_success(self, tmp_path):
        run_dir = str(tmp_path)
        result = update_all_records(
            run_dir, "CONSTITUTION.md", SAMPLE_DOC, SAMPLE_HISTORY,
            _mock_gateway(),
        )
        assert result.fully_successful
        assert result.history_archived
        assert result.decision_log_built
        assert result.entity_map_generated

    def test_history_archived(self, tmp_path):
        update_all_records(
            str(tmp_path), "doc.md", SAMPLE_DOC, SAMPLE_HISTORY, _mock_gateway(),
        )
        archive = tmp_path / "history_archive" / "doc_md.json"
        assert archive.exists()

    def test_decision_log_saved(self, tmp_path):
        update_all_records(
            str(tmp_path), "doc.md", SAMPLE_DOC, SAMPLE_HISTORY, _mock_gateway(),
        )
        log = tmp_path / "decision_logs" / "doc_md.json"
        assert log.exists()
        data = json.loads(log.read_text())
        assert "summary" in data

    def test_entity_map_saved(self, tmp_path):
        update_all_records(
            str(tmp_path), "doc.md", SAMPLE_DOC, SAMPLE_HISTORY, _mock_gateway(),
        )
        em_dir = tmp_path / "entity_maps"
        assert em_dir.exists()
        assert len(list(em_dir.glob("*.json"))) == 1

    def test_af_proposals(self, tmp_path):
        findings = [
            {"description": "Missing retry logic", "fix": "Add retry", "class": "requires_review"},
        ]
        result = update_all_records(
            str(tmp_path), "doc.md", SAMPLE_DOC, SAMPLE_HISTORY, _mock_gateway(),
            audit_findings_to_propose=findings, run_id="RUN-001",
        )
        assert len(result.af_proposed) == 1

    def test_af_dedup(self, tmp_path):
        from planner.af_manager import AFEntry
        existing = [AFEntry("AF-001", "Test", "ACTIVE", "safe_autofix", "HIGH",
                           "missing retry logic in error handling", "add retry")]
        findings = [
            {"description": "missing retry logic in error handling flow", "fix": "Add retry"},
        ]
        result = update_all_records(
            str(tmp_path), "doc.md", SAMPLE_DOC, SAMPLE_HISTORY, _mock_gateway(),
            existing_af_entries=existing, audit_findings_to_propose=findings,
        )
        assert len(result.af_proposed) == 0  # Deduped

    def test_idempotent(self, tmp_path):
        args = (str(tmp_path), "doc.md", SAMPLE_DOC, SAMPLE_HISTORY, _mock_gateway())
        r1 = update_all_records(*args)
        r2 = update_all_records(*args)
        assert r1.fully_successful
        assert r2.fully_successful

    def test_partial_failure_tracked(self, tmp_path):
        class FailGW:
            def call_model(self, *a, **kw):
                raise RuntimeError("Model down")
        result = update_all_records(
            str(tmp_path), "doc.md", SAMPLE_DOC, SAMPLE_HISTORY, FailGW(),
        )
        assert not result.fully_successful
        assert result.history_archived  # This doesn't need gateway
        assert not result.decision_log_built  # This needs gateway
        assert len(result.errors) > 0
