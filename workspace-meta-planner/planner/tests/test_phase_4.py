"""Tests for phases/phase_4_lessons.py — TASK-023."""

import pytest
from pathlib import Path

from planner.phases.phase_4_lessons import (
    LessonsCheckResult,
    check_lessons,
    load_lessons,
    _parse_lessons_response,
)


SAMPLE_LESSONS = """# LESSONS_LEARNED.md

## PLAN
| ID | Lesson |
|----|--------|
| LL-PLAN-001 | Plan data flow before building agents |
| LL-PLAN-003 | Test ONE item E2E before batch |

## ARCH
| ID | Lesson |
|----|--------|
| LL-ARCH-023 | Validate structurally before quality check |
"""


def _mock_gateway(response="NO VIOLATIONS found."):
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, phase="4", document=None, **kw):
            self.calls.append({"role": role, "prompt": prompt})
            return {"content": response, "tokens_in": 500, "tokens_out": 200}
    return MockGW()


class TestLoadLessons:
    def test_loads_file(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "LESSONS_LEARNED.md").write_text(SAMPLE_LESSONS)
        content = load_lessons(str(tmp_path))
        assert "LL-PLAN-001" in content

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_lessons(str(tmp_path)) == ""


class TestCheckLessons:
    def test_clean_document(self):
        gw = _mock_gateway("NO VIOLATIONS found.")
        result = check_lessons("# Clean doc", "WORKFLOW_SPEC", SAMPLE_LESSONS, gw)
        assert result.passed
        assert result.violation_count == 0

    def test_uses_primary_model(self):
        gw = _mock_gateway("NO VIOLATIONS found.")
        check_lessons("# Doc", "WORKFLOW_SPEC", SAMPLE_LESSONS, gw)
        assert gw.calls[0]["role"] == "primary"

    def test_with_violations(self):
        response = (
            "VIOLATIONS:\n"
            "- LL-PLAN-001: No data flow defined → Add data flow diagram\n"
            "- LL-ARCH-023: Quality check runs before structural → Reorder validation\n"
            "RECOMMENDATIONS:\n"
            "- LL-PLAN-003: Consider adding E2E test phase"
        )
        gw = _mock_gateway(response)
        result = check_lessons("# Doc", "WORKFLOW_SPEC", SAMPLE_LESSONS, gw)
        assert not result.passed
        assert result.violation_count == 2
        assert len(result.recommendations) == 1

    def test_empty_lessons(self):
        gw = _mock_gateway()
        result = check_lessons("# Doc", "WORKFLOW_SPEC", "", gw)
        assert result.passed
        assert len(gw.calls) == 0  # No call made

    def test_prompt_includes_doc_and_lessons(self):
        gw = _mock_gateway("NO VIOLATIONS")
        check_lessons("# My special doc", "WORKFLOW_SPEC", "LL-PLAN-001 lesson", gw)
        prompt = gw.calls[0]["prompt"]
        assert "special doc" in prompt
        assert "LL-PLAN-001" in prompt


class TestParseLessonsResponse:
    def test_no_violations(self):
        result = _parse_lessons_response("NO VIOLATIONS found.")
        assert result.passed
        assert result.violation_count == 0

    def test_parse_violations(self):
        response = "VIOLATIONS:\n- LL-PLAN-001: Missing data flow → Add diagram\n"
        result = _parse_lessons_response(response)
        assert result.violation_count == 1
        v = result.violations[0]
        assert v.lesson_id == "LL-PLAN-001"
        assert "data flow" in v.description.lower()
        assert "diagram" in v.suggestion.lower()

    def test_parse_recommendations(self):
        response = "VIOLATIONS:\nRECOMMENDATIONS:\n- LL-PLAN-003: Should add E2E test\n"
        result = _parse_lessons_response(response)
        assert result.passed
        assert len(result.recommendations) == 1

    def test_parse_mixed(self):
        response = (
            "VIOLATIONS:\n"
            "- LL-ARCH-023: Wrong order → Fix order\n"
            "RECOMMENDATIONS:\n"
            "- LL-PLAN-003: Add testing phase\n"
        )
        result = _parse_lessons_response(response)
        assert result.violation_count == 1
        assert len(result.recommendations) == 1

    def test_empty_response(self):
        result = _parse_lessons_response("")
        assert result.passed


class TestLessonsCheckResult:
    def test_passed_no_violations(self):
        r = LessonsCheckResult()
        assert r.passed

    def test_failed_with_violations(self):
        from planner.phases.phase_4_lessons import LessonViolation
        r = LessonsCheckResult(violations=[
            LessonViolation("LL-001", "issue", "", "fix"),
        ])
        assert not r.passed
        assert r.violation_count == 1
