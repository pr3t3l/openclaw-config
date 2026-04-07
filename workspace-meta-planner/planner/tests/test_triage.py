"""Tests for audit_triage.py — TASK-021."""

import pytest

from planner.audit_triage import (
    ConflictFlag,
    Finding,
    TriageResult,
    detect_conflicts,
    format_summary,
    triage,
    _parse_findings,
    _topics_overlap,
)


AUDIT_GPT_TECH = {
    "model_label": "gpt_tech",
    "content": "- CRITICAL: Missing error handling for API timeouts\nSECTION: Data Flow\nSUGGESTION: Add retry with backoff\n- MINOR: Typo in section header",
}

AUDIT_GPT_ARCH = {
    "model_label": "gpt_arch",
    "content": "- IMPORTANT: No rollback strategy for migrations\nSUGGESTION: Add migration rollback plan",
}

AUDIT_GEMINI_TECH = {
    "model_label": "gemini_tech",
    "content": "- CRITICAL: Database connection pooling not configured\n- MINOR: Missing version number",
}

AUDIT_GEMINI_ARCH = {
    "model_label": "gemini_arch",
    "content": "- IMPORTANT: Cost tracking incomplete",
}


class TestTriage:
    def test_categorizes_all(self):
        results = [AUDIT_GPT_TECH, AUDIT_GPT_ARCH, AUDIT_GEMINI_TECH, AUDIT_GEMINI_ARCH]
        tr = triage(results)
        assert tr.critical_count >= 2
        assert len(tr.important) >= 1
        assert tr.auto_fix_count >= 1

    def test_counts(self):
        results = [AUDIT_GPT_TECH]
        tr = triage(results)
        assert tr.critical_count >= 1
        assert tr.auto_fix_count >= 1

    def test_empty_input(self):
        tr = triage([])
        assert tr.critical_count == 0
        assert tr.auto_fix_count == 0
        assert not tr.has_conflicts


class TestParseFindings:
    def test_parses_critical(self):
        findings = _parse_findings(AUDIT_GPT_TECH["content"], "gpt_tech")
        critical = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical) >= 1
        assert "error handling" in critical[0].description.lower() or "timeout" in critical[0].description.lower()

    def test_parses_minor(self):
        findings = _parse_findings(AUDIT_GPT_TECH["content"], "gpt_tech")
        minor = [f for f in findings if f.severity == "MINOR"]
        assert len(minor) >= 1

    def test_source_preserved(self):
        findings = _parse_findings(AUDIT_GPT_TECH["content"], "gpt_tech")
        assert all(f.source == "gpt_tech" for f in findings)

    def test_suggestion_parsed(self):
        findings = _parse_findings(AUDIT_GPT_TECH["content"], "gpt_tech")
        with_suggestion = [f for f in findings if f.suggestion]
        assert len(with_suggestion) >= 1

    def test_empty_content(self):
        assert _parse_findings("", "gpt") == []


class TestDetectConflicts:
    def test_no_conflicts_when_agree(self):
        findings = [
            Finding("CRITICAL", "S1", "Missing auth", "Add JWT", "gpt_tech"),
            Finding("CRITICAL", "S1", "Missing auth flow", "Add JWT tokens", "gemini_tech"),
        ]
        conflicts = detect_conflicts(findings)
        assert len(conflicts) == 0  # Both say CRITICAL — no disagreement

    def test_conflict_on_severity(self):
        findings = [
            Finding("CRITICAL", "S1", "Missing database connection pooling config", "Add pooling", "gpt_tech"),
            Finding("MINOR", "S1", "Missing database connection pooling config", "Optional pooling", "gemini_tech"),
        ]
        conflicts = detect_conflicts(findings)
        assert len(conflicts) >= 1
        assert conflicts[0].gpt_argument
        assert conflicts[0].gemini_argument

    def test_no_findings_no_conflicts(self):
        assert detect_conflicts([]) == []


class TestTopicsOverlap:
    def test_same_topic(self):
        assert _topics_overlap(
            "Missing error handling for API timeouts",
            "Error handling for API timeout not implemented",
        )

    def test_different_topics(self):
        assert not _topics_overlap(
            "Missing database index",
            "UI rendering performance",
        )

    def test_empty_strings(self):
        assert not _topics_overlap("", "")


class TestFormatSummary:
    def test_format_with_criticals(self):
        tr = TriageResult(
            critical=[Finding("CRITICAL", "S1", "Missing auth", "Add JWT", "gpt_tech")],
            minor=[Finding("MINOR", "S2", "Typo", "Fix typo", "gemini_tech")],
        )
        summary = format_summary(tr)
        assert "CRITICAL" in summary
        assert "Missing auth" in summary
        assert "1 minor" in summary

    def test_format_with_conflicts(self):
        tr = TriageResult(
            conflicts=[ConflictFlag("Auth issue", "GPT: critical", "Gemini: minor")],
        )
        summary = format_summary(tr)
        assert "CONFLICT" in summary
        assert "GPT" in summary

    def test_format_empty(self):
        summary = format_summary(TriageResult())
        assert "0 minor" in summary
        assert "0 noise" in summary


class TestTriageResult:
    def test_has_conflicts(self):
        tr = TriageResult(conflicts=[ConflictFlag("X", "A", "B")])
        assert tr.has_conflicts

    def test_no_conflicts(self):
        assert not TriageResult().has_conflicts
