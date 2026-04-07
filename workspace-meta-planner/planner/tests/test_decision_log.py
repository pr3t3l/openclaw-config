"""Tests for decision_log.py — TASK-025."""

import json
import pytest
from pathlib import Path

from planner.decision_log import (
    DecisionLog,
    archive_history,
    build_log,
    extract_hard_decisions,
    search_decisions,
    _parse_decision_log,
)


SAMPLE_HISTORY = [
    {"role": "system", "content": "You are a planner."},
    {"role": "user", "content": "I want to build a finance tracker."},
    {"role": "assistant", "content": "What database will you use?"},
    {"role": "user", "content": "PostgreSQL because I want self-hosted."},
]

OPUS_RESPONSE = """EXECUTIVE SUMMARY:
The discussion established a finance tracker using PostgreSQL for self-hosted data control.
The system will track expenses and Airbnb deductions.

HARD DECISIONS:
- db_choice: PostgreSQL — self-hosted, no vendor lock
- auth_model: JWT with refresh — mobile and web clients
- cost_ceiling: $10/run — solo dev budget
"""


def _mock_gateway(response=OPUS_RESPONSE):
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, phase="6", document=None, **kw):
            self.calls.append(role)
            return {"content": response, "tokens_in": 500, "tokens_out": 300}
    return MockGW()


class TestArchiveHistory:
    def test_creates_archive(self, tmp_path):
        run_dir = str(tmp_path / "run-001")
        path = archive_history(run_dir, "CONSTITUTION.md", SAMPLE_HISTORY)
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert len(data) == 4

    def test_safe_filename(self, tmp_path):
        run_dir = str(tmp_path / "run-001")
        path = archive_history(run_dir, "spec.md", [])
        assert "spec_md" in path


class TestBuildLog:
    def test_builds_log(self):
        gw = _mock_gateway()
        log = build_log("CONSTITUTION.md", SAMPLE_HISTORY, gw)
        assert log.document_name == "CONSTITUTION.md"
        assert len(log.summary) > 0
        assert len(log.hard_decisions) > 0

    def test_uses_primary(self):
        gw = _mock_gateway()
        build_log("doc.md", SAMPLE_HISTORY, gw)
        assert "primary" in gw.calls

    def test_decisions_parsed(self):
        gw = _mock_gateway()
        log = build_log("doc.md", SAMPLE_HISTORY, gw)
        assert "db_choice" in log.hard_decisions
        assert "PostgreSQL" in log.hard_decisions["db_choice"]


class TestExtractHardDecisions:
    def test_extract(self):
        log = DecisionLog("doc.md", "summary", {"db": "PostgreSQL", "auth": "JWT"})
        d = extract_hard_decisions(log)
        assert d["db"] == "PostgreSQL"
        assert d["auth"] == "JWT"


class TestSearchDecisions:
    def test_finds_key(self):
        logs = {
            "doc.md": DecisionLog("doc.md", "summary", {"db_choice": "PostgreSQL"}),
        }
        assert search_decisions(logs, "db_choice") == "PostgreSQL"

    def test_case_insensitive(self):
        logs = {
            "doc.md": DecisionLog("doc.md", "summary", {"DB_Choice": "PostgreSQL"}),
        }
        assert search_decisions(logs, "db_choice") == "PostgreSQL"

    def test_partial_match(self):
        logs = {
            "doc.md": DecisionLog("doc.md", "summary", {"db_choice": "PG"}),
        }
        assert search_decisions(logs, "db") == "PG"

    def test_not_found(self):
        logs = {"doc.md": DecisionLog("doc.md", "summary", {"db": "PG"})}
        assert search_decisions(logs, "auth") is None

    def test_searches_all_docs(self):
        logs = {
            "a.md": DecisionLog("a.md", "s", {"db": "PG"}),
            "b.md": DecisionLog("b.md", "s", {"auth": "JWT"}),
        }
        assert search_decisions(logs, "auth") == "JWT"


class TestParseDecisionLog:
    def test_parses_summary_and_decisions(self):
        summary, decisions = _parse_decision_log(OPUS_RESPONSE)
        assert "finance tracker" in summary.lower()
        assert "db_choice" in decisions
        assert len(decisions) >= 3

    def test_empty_response(self):
        summary, decisions = _parse_decision_log("")
        assert summary == ""
        assert decisions == {}

    def test_summary_only(self):
        summary, decisions = _parse_decision_log("EXECUTIVE SUMMARY:\nJust a summary here.")
        assert "summary" in summary.lower()

    def test_fallback_for_unstructured(self):
        summary, decisions = _parse_decision_log("Some random text without structure.")
        assert len(summary) > 0  # Falls back to raw content
