"""Tests for document_validator.py — TASK-006."""

import pytest

from planner.validators.document_validator import validate, ValidationResult


VALID_DOC = """# My Document

## 1. Purpose
This document describes the system architecture.

## 2. Stack
PostgreSQL, Python, React.

## 3. Notes
All systems operational.
"""

DOC_WITH_STUBS = """# My Document

## 1. Purpose
This is TBD.

## 2. Stack
TODO: decide on database.

## 3. Details
The type is some_type and value is placeholder.
"""

DOC_WITH_ASSUMPTIONS = """# My Document

## 1. Purpose
This document serves [ASSUMPTION — validate during implementation] purposes.

## 2. Stack
[ASSUMPTION — PostgreSQL unless requirements change]
"""

DOC_WITH_EMPTY_SECTION = """# My Document

## 1. Purpose
This is the purpose.

## 2. Empty Section

## 3. Notes
Some notes here.
"""


class TestValidateCleanDoc:
    def test_valid_doc_passes(self):
        result = validate(VALID_DOC)
        assert result.passed is True
        assert result.error_count == 0
        assert len(result.empty_sections) == 0

    def test_stats_populated(self):
        result = validate(VALID_DOC)
        assert result.stats["total_lines"] > 0
        assert result.stats["total_sections"] > 0
        assert result.stats["errors"] == 0


class TestForbiddenPatterns:
    def test_catches_tbd(self):
        result = validate(DOC_WITH_STUBS)
        assert result.passed is False
        tbd_violations = [v for v in result.violations if "TBD" in v.pattern_matched]
        assert len(tbd_violations) >= 1

    def test_catches_todo(self):
        result = validate(DOC_WITH_STUBS)
        todo_violations = [v for v in result.violations if "TODO" in v.pattern_matched]
        assert len(todo_violations) >= 1

    def test_catches_placeholder(self):
        result = validate(DOC_WITH_STUBS)
        ph_violations = [v for v in result.violations if "placeholder" in v.pattern_matched]
        assert len(ph_violations) >= 1

    def test_catches_some_type(self):
        result = validate(DOC_WITH_STUBS)
        st_violations = [v for v in result.violations if "some_type" in v.pattern_matched]
        assert len(st_violations) >= 1

    def test_line_numbers_present(self):
        result = validate(DOC_WITH_STUBS)
        for v in result.violations:
            if v.pattern_matched != "empty_section":
                assert v.line_number > 0

    def test_fixme_caught(self):
        result = validate("# Doc\n## Section\nFIXME: this needs work")
        assert result.passed is False


class TestAssumptions:
    def test_assumptions_allowed(self):
        result = validate(DOC_WITH_ASSUMPTIONS)
        assert result.passed is True
        assert result.stats["assumptions"] == 2

    def test_assumption_not_counted_as_violation(self):
        result = validate(DOC_WITH_ASSUMPTIONS)
        assert result.error_count == 0

    def test_tbd_inside_assumption_allowed(self):
        doc = "# Doc\n## Section\n[ASSUMPTION — TBD until design review]"
        result = validate(doc)
        assert result.passed is True


class TestEmptySections:
    def test_empty_section_detected(self):
        result = validate(DOC_WITH_EMPTY_SECTION)
        assert result.passed is False
        assert "2. Empty Section" in result.empty_sections

    def test_non_empty_sections_ok(self):
        result = validate(DOC_WITH_EMPTY_SECTION)
        assert "1. Purpose" not in result.empty_sections
        assert "3. Notes" not in result.empty_sections


class TestEdgeCases:
    def test_empty_document(self):
        result = validate("")
        assert isinstance(result, ValidationResult)

    def test_comments_ignored(self):
        doc = "# Doc\n## Section\n<!-- TODO: remove this comment -->\nReal content."
        result = validate(doc)
        assert result.passed is True

    def test_case_insensitive_placeholder(self):
        doc = "# Doc\n## Section\nThis is TBD and also Placeholder."
        result = validate(doc)
        assert result.passed is False
        assert result.error_count >= 2  # TBD (uppercase) + Placeholder (case-insensitive)

    def test_template_type_accepted(self):
        result = validate(VALID_DOC, template_type="WORKFLOW_SPEC")
        assert result.passed is True
