"""Tests for phases/phase_2_5_preaudit.py — TASK-019."""

import pytest
from pathlib import Path

from planner.phases.phase_2_5_preaudit import (
    AFEntry,
    PreAuditResult,
    check_against_af,
    load_audit_findings,
    apply_safe_fix,
    flag_semantic,
    _pattern_matches,
    _applies_to_doc,
    _parse_audit_findings,
)


SAMPLE_AF_CONTENT = """# AUDIT_FINDINGS.md

## Active Patterns

### AF-001: Missing error handling in data flow specs
- Status: ACTIVE
- Class: safe_autofix
- Confidence: HIGH
- Pattern: Specs define happy path but no failure retry for data
- Fix: Add Failure & Recovery row to every data flow table
- Applies to: WORKFLOW_SPEC, MODULE_SPEC

### AF-002: Constitution rules referenced but not enforced
- Status: ACTIVE
- Class: requires_review
- Confidence: MEDIUM
- Pattern: Rules listed but no gate or check references
- Fix: Every rule must link to a gate ID or pre-flight check item
- Applies to: CONSTITUTION, MODULE_SPEC, WORKFLOW_SPEC

### AF-003: Deprecated pattern
- Status: DEPRECATED
- Class: safe_autofix
- Pattern: Old pattern
- Fix: Old fix
- Applies to: ALL

## Deprecated Patterns
"""


def _make_entry(af_id="AF-001", status="ACTIVE", af_class="safe_autofix",
                pattern="missing error handling", fix="add error handling",
                applies_to=None):
    return AFEntry(
        af_id=af_id, status=status, af_class=af_class,
        pattern=pattern, fix=fix, applies_to=applies_to or ["ALL"],
    )


class TestLoadAuditFindings:
    def test_loads_active_only(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "AUDIT_FINDINGS.md").write_text(SAMPLE_AF_CONTENT)
        entries = load_audit_findings(str(tmp_path))
        assert len(entries) == 2  # AF-001 and AF-002 (not DEPRECATED AF-003)
        assert all(e.status == "ACTIVE" for e in entries)

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_audit_findings(str(tmp_path)) == []

    def test_parses_fields(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "AUDIT_FINDINGS.md").write_text(SAMPLE_AF_CONTENT)
        entries = load_audit_findings(str(tmp_path))
        af1 = next(e for e in entries if e.af_id == "AF-001")
        assert af1.af_class == "safe_autofix"
        assert "happy path" in af1.pattern.lower()
        assert "WORKFLOW_SPEC" in af1.applies_to


class TestCheckAgainstAF:
    def test_safe_fix_applied(self):
        entry = _make_entry(af_class="safe_autofix",
                           pattern="happy path only without failure handling retry")
        doc = "# Spec\n\n## Data Flow\nHappy path only, no failure handling or retry."
        result = check_against_af(doc, "WORKFLOW_SPEC", [entry])
        assert result.safe_count == 1
        assert "AF-001" in result.safe_applied[0]
        assert "AF-001 APPLIED" in result.content

    def test_semantic_flagged(self):
        entry = _make_entry(af_id="AF-002", af_class="requires_review",
                           pattern="rules listed without gate check enforcement")
        doc = "# Spec\nRules are listed without any gate check or enforcement."
        result = check_against_af(doc, "WORKFLOW_SPEC", [entry])
        assert result.semantic_count == 1
        assert "AF-002" in result.semantic_flagged[0]
        assert "AF-002 SUGGESTION" in result.content

    def test_ignores_non_active(self):
        entry = _make_entry(status="DEPRECATED")
        result = check_against_af("any content", "WORKFLOW_SPEC", [entry])
        assert result.safe_count == 0
        assert result.semantic_count == 0

    def test_ignores_non_matching_doc_type(self):
        entry = _make_entry(applies_to=["DATA_MODEL"])
        result = check_against_af("missing error handling", "WORKFLOW_SPEC", [entry])
        assert result.safe_count == 0

    def test_applies_to_all(self):
        entry = _make_entry(applies_to=["ALL"])
        result = check_against_af("missing error handling", "WHATEVER", [entry])
        assert result.safe_count == 1

    def test_no_match_no_change(self):
        entry = _make_entry(pattern="completely unrelated xyz abc")
        doc = "This document has nothing to do with the pattern."
        result = check_against_af(doc, "WORKFLOW_SPEC", [entry])
        assert result.safe_count == 0
        assert result.content == doc

    def test_multiple_entries(self):
        e1 = _make_entry(af_id="AF-001",
                        pattern="failure handling missing from data flow specs")
        e2 = _make_entry(af_id="AF-002", af_class="requires_review",
                        pattern="rules listed without gate enforcement checks")
        doc = "# Spec\nData flow specs with no failure handling. Rules listed without gate enforcement checks."
        result = check_against_af(doc, "WORKFLOW_SPEC", [e1, e2])
        assert result.safe_count == 1
        assert result.semantic_count == 1

    def test_empty_entries(self):
        result = check_against_af("any doc", "WORKFLOW_SPEC", [])
        assert result.safe_count == 0
        assert result.semantic_count == 0


class TestPatternMatches:
    def test_matches_keywords(self):
        assert _pattern_matches("missing error handling in specs", "No error handling here")

    def test_no_match(self):
        assert not _pattern_matches("database migration schema", "This is about UI design")

    def test_empty_pattern(self):
        assert not _pattern_matches("", "any content")

    def test_partial_match(self):
        # Less than 50% keywords
        assert not _pattern_matches("very specific technical database migration", "just database")


class TestAppliesToDoc:
    def test_all_matches_everything(self):
        assert _applies_to_doc(["ALL"], "WORKFLOW_SPEC")
        assert _applies_to_doc(["ALL"], "ANYTHING")

    def test_specific_match(self):
        assert _applies_to_doc(["WORKFLOW_SPEC"], "WORKFLOW_SPEC")

    def test_no_match(self):
        assert not _applies_to_doc(["DATA_MODEL"], "WORKFLOW_SPEC")

    def test_multiple_targets(self):
        assert _applies_to_doc(["CONSTITUTION", "WORKFLOW_SPEC"], "WORKFLOW_SPEC")


class TestPreAuditResult:
    def test_counts(self):
        r = PreAuditResult(safe_applied=["a", "b"], semantic_flagged=["c"])
        assert r.safe_count == 2
        assert r.semantic_count == 1
