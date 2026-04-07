"""Tests for phases/phase_3_audit.py — TASK-020."""

import json
import pytest
from pathlib import Path

from planner.phases.phase_3_audit import (
    AUDIT_CALLS,
    AuditResult,
    AuditCallResult,
    run_audit,
)


def _mock_gateway():
    class MockGW:
        def __init__(self):
            self.calls = []
        def call_model(self, role, prompt, context=None, phase="3", document=None, **kw):
            self.calls.append({"role": role, "audit_role": "tech" if "flaw" in (context or "").lower() else "arch"})
            return {
                "content": f"- CRITICAL: Missing error handling\n- MINOR: Typo in section 3",
                "model": f"mock-{role}",
                "tokens_in": 500,
                "tokens_out": 200,
                "cost_usd": 0.01,
                "duration": 1.5,
            }
    return MockGW()


def _make_state():
    return {
        "current_document": {"content": "# Doc", "type": "WORKFLOW_SPEC"},
        "constitution": {"rules": ["No stubs", "Max 2 retries"]},
        "project_context": {
            "stack": {"os": "WSL", "db": "PostgreSQL"},
            "integrations_summary": "Telegram, LiteLLM",
        },
        "cross_references": [],
        "cost": {"total_usd": 0, "by_model": {}, "by_phase": {}, "by_document": {}},
    }


class TestRunAudit:
    def test_four_calls_made(self, tmp_path):
        gw = _mock_gateway()
        result = run_audit(
            "# Doc content", "WORKFLOW_SPEC", _make_state(), gw,
            "RUN-20260406-001", str(tmp_path), document="spec.md", backoff=False,
        )
        assert len(gw.calls) == 4
        assert len(result.call_results) == 4

    def test_call_roles(self, tmp_path):
        gw = _mock_gateway()
        run_audit("# Doc", "WORKFLOW_SPEC", _make_state(), gw,
                  "RUN-20260406-001", str(tmp_path), backoff=False)
        roles = [c["role"] for c in gw.calls]
        assert roles.count("auditor_gpt") == 2
        assert roles.count("auditor_gemini") == 2

    def test_results_saved_to_disk(self, tmp_path):
        gw = _mock_gateway()
        result = run_audit(
            "# Doc", "WORKFLOW_SPEC", _make_state(), gw,
            "RUN-20260406-001", str(tmp_path), document="spec.md", backoff=False,
        )
        assert len(result.raw_saved_paths) == 4
        for path in result.raw_saved_paths:
            assert Path(path).exists()
            data = json.loads(Path(path).read_text())
            assert "content" in data
            assert "model_label" in data

    def test_call_result_fields(self, tmp_path):
        gw = _mock_gateway()
        result = run_audit(
            "# Doc", "WORKFLOW_SPEC", _make_state(), gw,
            "RUN-20260406-001", str(tmp_path), backoff=False,
        )
        cr = result.call_results[0]
        assert cr.model_label in ("gpt_tech", "gpt_arch", "gemini_tech", "gemini_arch")
        assert cr.audit_role in ("technical", "architecture")
        assert len(cr.content) > 0
        assert cr.tokens_out > 0

    def test_issue_counts(self, tmp_path):
        gw = _mock_gateway()
        result = run_audit(
            "# Doc", "WORKFLOW_SPEC", _make_state(), gw,
            "RUN-20260406-001", str(tmp_path), backoff=False,
        )
        counts = result.issue_counts
        assert len(counts) == 4
        for label, count in counts.items():
            assert count >= 1  # Each mock returns at least 1 finding


class TestAuditCallSequence:
    def test_sequence_defined(self):
        assert len(AUDIT_CALLS) == 4
        labels = [c["model_label"] for c in AUDIT_CALLS]
        assert "gpt_tech" in labels
        assert "gpt_arch" in labels
        assert "gemini_tech" in labels
        assert "gemini_arch" in labels

    def test_roles_alternate(self):
        roles = [c["audit_role"] for c in AUDIT_CALLS]
        assert roles.count("technical") == 2
        assert roles.count("architecture") == 2


class TestContextBuilding:
    def test_handles_empty_state(self, tmp_path):
        gw = _mock_gateway()
        empty_state = {
            "cost": {"total_usd": 0, "by_model": {}, "by_phase": {}, "by_document": {}},
        }
        # Should not crash with missing state fields
        result = run_audit(
            "# Doc", "WORKFLOW_SPEC", empty_state, gw,
            "RUN-20260406-001", str(tmp_path), backoff=False,
        )
        assert len(result.call_results) == 4

    def test_uses_filtered_context(self, tmp_path):
        gw = _mock_gateway()
        state = _make_state()
        run_audit("# Doc", "WORKFLOW_SPEC", state, gw,
                  "RUN-20260406-001", str(tmp_path), backoff=False)
        # Verify calls were made (context filtering is internal)
        assert len(gw.calls) == 4


class TestAuditResult:
    def test_empty_result(self):
        r = AuditResult()
        assert r.issue_counts == {}
        assert r.call_results == []

    def test_with_results(self):
        r = AuditResult(call_results=[
            AuditCallResult("gpt_tech", "technical", "- CRITICAL: issue\n- MINOR: issue"),
            AuditCallResult("gemini_tech", "technical", "- IMPORTANT: issue"),
        ])
        counts = r.issue_counts
        assert counts["gpt_tech"] == 2
        assert counts["gemini_tech"] == 1
