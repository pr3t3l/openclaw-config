"""Tests for recall.py — TASK-027."""

import json
import pytest
from pathlib import Path

from planner.recall import recall_history, search_all_archives
from planner.decision_log import DecisionLog


@pytest.fixture
def run_dir(tmp_path):
    archive = tmp_path / "history_archive"
    archive.mkdir()
    (archive / "CONSTITUTION_md.json").write_text(json.dumps([
        {"role": "user", "content": "I want cost ceiling at $10 per run."},
        {"role": "assistant", "content": "Got it. Setting cost ceiling to $10/run."},
        {"role": "user", "content": "Use PostgreSQL for the database."},
    ]))
    (archive / "DATA_MODEL_md.json").write_text(json.dumps([
        {"role": "user", "content": "Users table has user_id as UUID."},
    ]))
    return str(tmp_path)


@pytest.fixture
def decision_logs():
    return {
        "CONSTITUTION.md": DecisionLog("CONSTITUTION.md", "summary", {
            "cost_ceiling": "$10/run — solo dev budget",
            "db_choice": "PostgreSQL — self-hosted",
        }),
    }


class TestRecallHistory:
    def test_fast_path_hard_decisions(self, run_dir, decision_logs):
        result = recall_history(run_dir, "CONSTITUTION.md", "cost", decision_logs)
        assert result is not None
        assert "$10" in result

    def test_slow_path_archive(self, run_dir):
        result = recall_history(run_dir, "CONSTITUTION.md", "PostgreSQL")
        assert result is not None
        assert "PostgreSQL" in result

    def test_not_found(self, run_dir):
        result = recall_history(run_dir, "CONSTITUTION.md", "nonexistent_topic_xyz")
        assert result is None

    def test_missing_archive(self, run_dir):
        result = recall_history(run_dir, "MISSING.md", "anything")
        assert result is None

    def test_fast_path_priority(self, run_dir, decision_logs):
        """Hard Decisions searched before archive."""
        result = recall_history(run_dir, "CONSTITUTION.md", "db_choice", decision_logs)
        assert result is not None
        assert "Decision" in result


class TestSearchAllArchives:
    def test_finds_across_docs(self, run_dir):
        results = search_all_archives(run_dir, "UUID")
        assert len(results) >= 1
        assert any("DATA" in r["document"] for r in results)

    def test_no_results(self, run_dir):
        results = search_all_archives(run_dir, "xyz_nonexistent")
        assert results == []

    def test_missing_dir(self, tmp_path):
        results = search_all_archives(str(tmp_path / "nope"), "anything")
        assert results == []

    def test_returns_fragments(self, run_dir):
        results = search_all_archives(run_dir, "cost")
        assert all("fragment" in r for r in results)
        assert all(len(r["fragment"]) > 0 for r in results)
