"""Tests for phases/phase_2_draft.py — TASK-018."""

import pytest

from planner.phases.phase_2_draft import draft_document, DraftResult


VALID_DOC = """# WORKFLOW_SPEC — Test

## 1. Purpose
Build a planner system.

## 2. Scope
In scope: planning. Out of scope: execution.

## 3. Architecture
Uses PostgreSQL and Python.
"""

DOC_WITH_STUBS = """# WORKFLOW_SPEC — Test

## 1. Purpose
TBD

## 2. Scope
TODO
"""


def _mock_gateway(content=VALID_DOC):
    class MockGW:
        def __init__(self):
            self.calls = []
            self._content = content
        def call_model(self, role, prompt, context=None, phase="2", document=None, **kw):
            self.calls.append({"role": role, "prompt": prompt})
            return {"content": self._content, "tokens_in": 500, "tokens_out": 1000}
    return MockGW()


class TestDraftDocument:
    def test_produces_valid_draft(self):
        gw = _mock_gateway(VALID_DOC)
        result = draft_document(
            doc_type="WORKFLOW_SPEC",
            template_content="## 1. Purpose\n## 2. Scope\n## 3. Architecture",
            intake_answers={"Purpose": "Build a planner", "Scope": "Planning only"},
            gateway=gw,
        )
        assert result.validation_passed
        assert len(result.content) > 0
        assert result.validation_errors == []

    def test_calls_primary_model(self):
        gw = _mock_gateway(VALID_DOC)
        draft_document("WORKFLOW_SPEC", "", {"S": "A"}, gw)
        assert gw.calls[0]["role"] == "primary"

    def test_includes_ideation(self):
        gw = _mock_gateway(VALID_DOC)
        draft_document(
            "WORKFLOW_SPEC", "", {"S": "A"}, gw,
            ideation_accepted=[{"feature": "Add caching"}],
        )
        assert "caching" in gw.calls[0]["prompt"].lower()

    def test_handles_empty_ideation(self):
        gw = _mock_gateway(VALID_DOC)
        result = draft_document("WORKFLOW_SPEC", "", {"S": "A"}, gw, ideation_accepted=[])
        assert result.validation_passed

    def test_handles_none_ideation(self):
        gw = _mock_gateway(VALID_DOC)
        result = draft_document("WORKFLOW_SPEC", "", {"S": "A"}, gw, ideation_accepted=None)
        assert result.validation_passed


class TestValidation:
    def test_catches_stubs(self):
        gw = _mock_gateway(DOC_WITH_STUBS)
        result = draft_document("WORKFLOW_SPEC", "", {"S": "A"}, gw, max_retries=0)
        assert not result.validation_passed
        assert len(result.validation_errors) > 0

    def test_retries_on_failure(self):
        call_count = 0
        class RetryGW:
            def __init__(self):
                self.calls = []
            def call_model(self, role, prompt, context=None, phase="2", document=None, **kw):
                nonlocal call_count
                call_count += 1
                self.calls.append(prompt)
                if call_count == 1:
                    return {"content": DOC_WITH_STUBS, "tokens_in": 100, "tokens_out": 200}
                return {"content": VALID_DOC, "tokens_in": 100, "tokens_out": 200}

        gw = RetryGW()
        result = draft_document("WORKFLOW_SPEC", "", {"S": "A"}, gw, max_retries=1)
        assert result.validation_passed
        assert call_count == 2

    def test_retry_includes_errors(self):
        calls = []
        class CaptureGW:
            def call_model(self, role, prompt, context=None, phase="2", document=None, **kw):
                calls.append(prompt)
                if len(calls) == 1:
                    return {"content": DOC_WITH_STUBS, "tokens_in": 100, "tokens_out": 200}
                return {"content": VALID_DOC, "tokens_in": 100, "tokens_out": 200}

        draft_document("WORKFLOW_SPEC", "", {"S": "A"}, CaptureGW(), max_retries=1)
        # Second call should mention validation errors
        assert "validation errors" in calls[1].lower()


class TestDraftResult:
    def test_result_fields(self):
        r = DraftResult("content", "WORKFLOW_SPEC", True, [])
        assert r.content == "content"
        assert r.doc_type == "WORKFLOW_SPEC"
        assert r.validation_passed
        assert r.version == 1

    def test_constitution_rules(self):
        gw = _mock_gateway(VALID_DOC)
        draft_document(
            "WORKFLOW_SPEC", "", {"S": "A"}, gw,
            constitution_rules="No stubs allowed",
        )
        # Rules should be in the system prompt (context)
        # We can verify the call was made
        assert len(gw.calls) == 1
