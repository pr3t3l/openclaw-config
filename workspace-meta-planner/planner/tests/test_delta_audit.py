"""Tests for delta_audit.py — TASK-022."""

import pytest

from planner.delta_audit import (
    CROSS_DOC_EFFECT,
    ENTITY_API_RULE_CHANGE,
    LOCAL_LOGIC,
    WORDING_ONLY,
    classify_change,
    run_delta,
    should_full_reaudit,
    _compute_change_ratio,
)


ORIGINAL = """# Spec

## 1. Purpose
Build a planner system.

## 2. Stack
PostgreSQL, Python.

## 3. Notes
Some notes here.
"""

MINOR_CHANGE = """# Spec

## 1. Purpose
Build a planner system for SDD.

## 2. Stack
PostgreSQL, Python.

## 3. Notes
Some notes here.
"""

ENTITY_CHANGE = """# Spec

## 1. Purpose
Build a planner system.

## 2. Stack
PostgreSQL, Python, new API endpoint /v2/plans.

## 3. Notes
Updated schema and entity model.
"""

CROSS_DOC_CHANGE = """# Spec

## 1. Purpose
Build a planner system. See CONSTITUTION.md §3 for rules.

## 2. Stack
PostgreSQL, Python, new API endpoint.

## 3. Notes
Updated entity references in DATA_MODEL.md.
"""

MAJOR_CHANGE = """# Spec

## 1. Purpose
Completely rewritten purpose about a different system.

## 2. Stack
MongoDB, Go, gRPC, Kubernetes, Helm.

## 3. Architecture
Microservices with event sourcing.

## 4. New Section
Entirely new content added here.
"""


def _mock_gateway(response="No new issues found. Changes look correct."):
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, phase="3", document=None, **kw):
            self.calls.append(role)
            return {"content": response, "tokens_in": 100, "tokens_out": 50}
    return MockGW()


class TestClassifyChange:
    def test_wording_only(self):
        c = classify_change(ORIGINAL, MINOR_CHANGE)
        assert c.category == WORDING_ONLY
        assert c.change_ratio < 0.15

    def test_entity_change(self):
        c = classify_change(ORIGINAL, ENTITY_CHANGE)
        assert c.category == ENTITY_API_RULE_CHANGE
        assert c.requires_cross_doc

    def test_cross_doc_change(self):
        c = classify_change(ORIGINAL, CROSS_DOC_CHANGE)
        assert c.category == CROSS_DOC_EFFECT
        assert c.requires_cross_doc

    def test_affected_sections(self):
        c = classify_change(ORIGINAL, MINOR_CHANGE)
        assert "1. Purpose" in c.affected_sections

    def test_identical_documents(self):
        c = classify_change(ORIGINAL, ORIGINAL)
        assert c.change_ratio == 0.0
        assert c.category == WORDING_ONLY


class TestRunDelta:
    def test_wording_uses_primary(self):
        gw = _mock_gateway()
        result = run_delta(ORIGINAL, MINOR_CHANGE, gw)
        assert "primary" in gw.calls

    def test_entity_uses_auditor(self):
        gw = _mock_gateway()
        result = run_delta(ORIGINAL, ENTITY_CHANGE, gw)
        assert "auditor_gpt" in gw.calls

    def test_passes_when_no_issues(self):
        gw = _mock_gateway("No new issues found.")
        result = run_delta(ORIGINAL, MINOR_CHANGE, gw)
        assert result.passed

    def test_fails_when_issues(self):
        gw = _mock_gateway("Found 2 new problems introduced by the changes.")
        result = run_delta(ORIGINAL, MINOR_CHANGE, gw)
        assert not result.passed

    def test_classification_included(self):
        gw = _mock_gateway()
        result = run_delta(ORIGINAL, MINOR_CHANGE, gw)
        assert result.classification is not None
        assert result.classification.category == WORDING_ONLY


class TestShouldFullReaudit:
    def test_small_change_no_reaudit(self):
        assert not should_full_reaudit(ORIGINAL, MINOR_CHANGE)

    def test_large_change_triggers_reaudit(self):
        assert should_full_reaudit(ORIGINAL, MAJOR_CHANGE)

    def test_human_requested(self):
        assert should_full_reaudit(ORIGINAL, MINOR_CHANGE, human_requested=True)

    def test_workflow_spec_no_auto_reaudit(self):
        # WORKFLOW_SPEC doesn't auto-trigger re-audit after corrections
        assert not should_full_reaudit(ORIGINAL, MINOR_CHANGE, doc_type="WORKFLOW_SPEC")


class TestComputeChangeRatio:
    def test_identical(self):
        assert _compute_change_ratio("a\nb\nc", "a\nb\nc") == 0.0

    def test_completely_different(self):
        ratio = _compute_change_ratio("a\nb\nc", "x\ny\nz")
        assert ratio > 0.5

    def test_empty_original(self):
        assert _compute_change_ratio("", "new content") == 1.0

    def test_both_empty(self):
        assert _compute_change_ratio("", "") == 0.0
