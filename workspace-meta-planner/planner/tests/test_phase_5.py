"""Tests for phases/phase_5_finalize.py — TASK-024."""

import pytest

from planner.phases.phase_5_finalize import (
    apply_fixes,
    present_for_approval,
    remove_af_markers,
    _extract_af_markers,
)


DOC_WITH_MARKERS = """# Spec

## 1. Purpose
Build a planner.

> [AF-001 SUGGESTION]: Add error handling section

## 2. Stack
PostgreSQL.

<!-- [AF-003 APPLIED]: Fixed missing section header -->
"""

CLEAN_DOC = """# Spec

## 1. Purpose
Build a planner.

## 2. Stack
PostgreSQL.
"""


class TestApplyFixes:
    def test_audit_fix(self):
        doc = "# Spec\n\n## 1. Purpose\nBuild things.\n\n## 2. Stack\nPython."
        result = apply_fixes(doc, [{"section": "1. Purpose", "fix_text": "Added error handling."}], [])
        assert "error handling" in result

    def test_lessons_fix(self):
        result = apply_fixes("# Doc", [], [{"lesson_id": "LL-001", "fix_text": "Added retry"}])
        assert "LL-001" in result
        assert "retry" in result

    def test_no_fixes(self):
        doc = "# Doc\nContent."
        assert apply_fixes(doc, [], []) == doc

    def test_multiple_fixes(self):
        doc = "# Spec\n\n## 1. Purpose\nX\n\n## 2. Stack\nY"
        result = apply_fixes(
            doc,
            [{"section": "1. Purpose", "fix_text": "Fix A"}],
            [{"lesson_id": "LL-001", "fix_text": "Fix B"}],
        )
        assert "Fix A" in result
        assert "Fix B" in result


class TestPresentForApproval:
    def test_summary_fields(self):
        result = present_for_approval(
            DOC_WITH_MARKERS, "CONSTITUTION.md",
            "Added error handling", 2.50, 8.00, 3,
        )
        assert "CONSTITUTION.md" in result.summary
        assert "$2.50" in result.summary
        assert "$8.00" in result.summary
        assert "3" in result.summary
        assert "Approve" in result.summary

    def test_af_markers_extracted(self):
        result = present_for_approval(DOC_WITH_MARKERS, "doc.md", "changes", 0, 0)
        assert "AF-001" in result.af_markers
        assert "AF-003" in result.af_markers

    def test_clean_content_no_markers(self):
        result = present_for_approval(DOC_WITH_MARKERS, "doc.md", "changes", 0, 0)
        assert "AF-001 SUGGESTION" not in result.clean_content
        assert "AF-003 APPLIED" not in result.clean_content

    def test_content_has_markers(self):
        result = present_for_approval(DOC_WITH_MARKERS, "doc.md", "changes", 0, 0)
        assert "AF-001 SUGGESTION" in result.content

    def test_no_markers(self):
        result = present_for_approval(CLEAN_DOC, "doc.md", "changes", 0, 0)
        assert result.af_markers == []
        assert "none" in result.summary.lower()


class TestRemoveAFMarkers:
    def test_removes_suggestions(self):
        result = remove_af_markers(DOC_WITH_MARKERS)
        assert "AF-001 SUGGESTION" not in result

    def test_removes_applied(self):
        result = remove_af_markers(DOC_WITH_MARKERS)
        assert "AF-003 APPLIED" not in result

    def test_preserves_content(self):
        result = remove_af_markers(DOC_WITH_MARKERS)
        assert "Build a planner" in result
        assert "PostgreSQL" in result

    def test_no_markers(self):
        result = remove_af_markers(CLEAN_DOC)
        assert "Build a planner" in result

    def test_no_triple_newlines(self):
        result = remove_af_markers(DOC_WITH_MARKERS)
        assert "\n\n\n" not in result


class TestExtractAFMarkers:
    def test_finds_both_types(self):
        markers = _extract_af_markers(DOC_WITH_MARKERS)
        assert "AF-001" in markers
        assert "AF-003" in markers

    def test_deduplicates(self):
        doc = "text\n> [AF-001 SUGGESTION]: x\n\n> [AF-001 SUGGESTION]: y\n"
        markers = _extract_af_markers(doc)
        assert markers.count("AF-001") == 1

    def test_empty_doc(self):
        assert _extract_af_markers("no markers here") == []
