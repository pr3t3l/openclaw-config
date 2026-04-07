"""Tests for phases/phase_1_5_ideation.py — TASK-017."""

import pytest

from planner.phases.phase_1_5_ideation import (
    SKIP_IDEATION_TYPES,
    IdeationResult,
    ideate,
    should_skip,
    _parse_suggestions,
    _parse_triage,
)


def _mock_gateway():
    """Create a mock gateway that returns canned responses."""
    class MockGateway:
        def __init__(self):
            self.calls = []

        def call_model(self, role, prompt, phase="1.5", document=None, **kw):
            self.calls.append({"role": role, "prompt": prompt})
            if role == "ideation_a":
                return {"content": "1. Add caching layer\n2. Add rate limiting", "tokens_in": 100, "tokens_out": 50}
            elif role == "ideation_b":
                return {"content": "1. Add health checks\n2. Add retry logic", "tokens_in": 80, "tokens_out": 40}
            else:  # triage
                return {"content": "RECOMMENDED:\n1. Add caching layer — high value\n2. Add health checks — essential\nSKIPPED:\n1. Add rate limiting — overkill for solo dev", "tokens_in": 200, "tokens_out": 100}
    return MockGateway()


class TestShouldSkip:
    def test_skips_foundation_docs(self):
        for doc_type in SKIP_IDEATION_TYPES:
            assert should_skip(doc_type) is True

    def test_does_not_skip_specs(self):
        assert should_skip("MODULE_SPEC") is False
        assert should_skip("WORKFLOW_SPEC") is False

    def test_all_foundation_types(self):
        expected = {"PROJECT_FOUNDATION", "CONSTITUTION", "DATA_MODEL", "INTEGRATIONS", "LESSONS_LEARNED"}
        assert SKIP_IDEATION_TYPES == expected


class TestIdeate:
    def test_skips_foundation(self):
        gw = _mock_gateway()
        result = ideate("CONSTITUTION", "Some intake", gw)
        assert result.skipped is True
        assert result.is_empty is True
        assert len(gw.calls) == 0

    def test_runs_for_spec(self):
        gw = _mock_gateway()
        result = ideate("WORKFLOW_SPEC", "Build a planner system", gw)
        assert result.skipped is False
        assert len(result.gpt_suggestions) > 0
        assert len(result.gemini_suggestions) > 0
        assert "recommended" in result.triage_result

    def test_three_model_calls(self):
        gw = _mock_gateway()
        ideate("WORKFLOW_SPEC", "Build X", gw)
        roles = [c["role"] for c in gw.calls]
        assert "ideation_a" in roles  # GPT
        assert "ideation_b" in roles  # Gemini
        assert "primary" in roles     # Triage (Opus)
        assert len(gw.calls) == 3

    def test_no_op_on_skip(self):
        result = IdeationResult(skipped=True)
        assert result.is_empty
        assert result.accepted == []

    def test_accepted_starts_empty(self):
        gw = _mock_gateway()
        result = ideate("WORKFLOW_SPEC", "Build X", gw)
        assert result.accepted == []  # Human decides


class TestParseSuggestions:
    def test_numbered_list(self):
        content = "1. Add caching\n2. Add monitoring\n3. Improve error handling"
        suggestions = _parse_suggestions(content, "gpt")
        assert len(suggestions) == 3
        assert suggestions[0]["feature"] == "Add caching"
        assert suggestions[0]["source"] == "gpt"

    def test_with_descriptions(self):
        content = "1. Add caching\n   This improves performance\n2. Add monitoring"
        suggestions = _parse_suggestions(content, "gemini")
        assert len(suggestions) == 2
        assert "performance" in suggestions[0]["assessment"]

    def test_empty_content(self):
        assert _parse_suggestions("", "gpt") == []

    def test_no_numbered_items(self):
        assert _parse_suggestions("Just some text without numbers", "gpt") == []


class TestParseTriage:
    def test_recommended_and_skipped(self):
        content = "RECOMMENDED:\n1. Caching — good\n2. Health checks — essential\nSKIPPED:\n1. Rate limiting — overkill"
        result = _parse_triage(content)
        assert len(result["recommended"]) == 2
        assert len(result["skipped"]) == 1

    def test_empty_sections(self):
        result = _parse_triage("RECOMMENDED:\nSKIPPED:")
        assert result["recommended"] == []
        assert result["skipped"] == []

    def test_empty_content(self):
        result = _parse_triage("")
        assert result["recommended"] == []
        assert result["skipped"] == []


class TestIdeationResult:
    def test_is_empty_when_skipped(self):
        assert IdeationResult(skipped=True).is_empty

    def test_is_empty_no_accepted(self):
        assert IdeationResult(skipped=False, accepted=[]).is_empty

    def test_not_empty_with_accepted(self):
        result = IdeationResult(skipped=False, accepted=[{"feature": "X"}])
        assert not result.is_empty
