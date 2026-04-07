"""Tests for telegram/formatter.py — TASK-011."""

import pytest

from planner.telegram import formatter


RUN_ID = "RUN-20260406-001"
DOC = "CONSTITUTION.md"


class TestPrefix:
    def test_run_only(self):
        assert "[RUN-20260406-001]" in formatter._prefix(RUN_ID)

    def test_with_doc(self):
        p = formatter._prefix(RUN_ID, doc=DOC)
        assert "[CONSTITUTION.md]" in p

    def test_with_phase(self):
        p = formatter._prefix(RUN_ID, doc=DOC, phase="3")
        assert "[Phase 3]" in p


class TestShouldSendAsFile:
    def test_short_text(self):
        assert formatter.should_send_as_file("short") is False

    def test_long_text(self):
        assert formatter.should_send_as_file("x" * 4000) is True

    def test_at_threshold(self):
        assert formatter.should_send_as_file("x" * 3500) is False
        assert formatter.should_send_as_file("x" * 3501) is True


class TestTruncate:
    def test_short_text_unchanged(self):
        assert formatter.truncate_for_telegram("short") == "short"

    def test_long_text_truncated(self):
        long = "x" * 5000
        result = formatter.truncate_for_telegram(long)
        assert len(result) <= formatter.TELEGRAM_CHAR_LIMIT
        assert "truncated" in result


class TestIntakeStart:
    def test_format(self):
        msg = formatter.intake_start(
            RUN_ID, "new project", "WORKFLOW_SPEC",
            ["PROJECT_FOUNDATION.md", "CONSTITUTION.md"],
            "What problem does this solve?"
        )
        assert RUN_ID in msg
        assert "new project" in msg
        assert "WORKFLOW_SPEC" in msg
        assert "What problem" in msg
        assert "PROJECT_FOUNDATION.md" in msg


class TestSectionComplete:
    def test_format(self):
        msg = formatter.section_complete(RUN_ID, DOC, "Purpose", "It tracks finances.")
        assert RUN_ID in msg
        assert "Purpose" in msg
        assert "tracks finances" in msg
        assert "correct?" in msg.lower()


class TestIdeationResults:
    def test_format(self):
        msg = formatter.ideation_results(
            RUN_ID, DOC,
            [{"feature": "Auto-import", "assessment": "worth adding"}],
            [{"feature": "Export PDF", "assessment": "skip — low priority"}],
            [1],
        )
        assert "Auto-import" in msg
        assert "Export PDF" in msg
        assert "#1" in msg
        assert "skip ideation" in msg.lower()


class TestPreAuditSummary:
    def test_format(self):
        msg = formatter.pre_audit_summary(RUN_ID, DOC, 3, 2)
        assert "3 safe patterns" in msg
        assert "2 semantic" in msg
        assert "auditors" in msg.lower()


class TestAuditSummary:
    def test_format(self):
        msg = formatter.audit_summary(
            RUN_ID, DOC,
            {"gpt_tech": 5, "gpt_arch": 3, "gemini_tech": 2, "gemini_arch": 1},
            [{"severity": "CRITICAL", "description": "Missing error handling", "suggestion": "Add retry logic"}],
            4, 2,
        )
        assert "5 issues" in msg
        assert "Missing error handling" in msg
        assert "retry logic" in msg
        assert "4 minor" in msg
        assert "2 items were noise" in msg


class TestAuditConflict:
    def test_format(self):
        msg = formatter.audit_conflict(
            RUN_ID, DOC,
            "This needs a database index",
            "Index not needed at this scale",
        )
        assert "DISAGREE" in msg
        assert "database index" in msg
        assert "not needed" in msg
        assert "Something else" in msg


class TestDocumentApproval:
    def test_format(self):
        msg = formatter.document_approval(
            RUN_ID, DOC,
            "Added error handling section",
            ["AF-001", "AF-003"],
            5, 1.50, 4.20,
        )
        assert "$1.50" in msg
        assert "$4.20" in msg
        assert "AF-001" in msg
        assert "Approve" in msg


class TestCrossdocResult:
    def test_no_contradictions(self):
        msg = formatter.crossdoc_result(RUN_ID, ["DOC_A.md", "DOC_B.md"], [])
        assert "0 contradictions" in msg
        assert "Ready for plan" in msg

    def test_with_contradictions(self):
        msg = formatter.crossdoc_result(
            RUN_ID, ["DOC_A.md"],
            [{"description": "user_id UUID vs integer", "question": "Which is correct?"}],
        )
        assert "1 contradictions" in msg
        assert "UUID vs integer" in msg


class TestRunComplete:
    def test_format(self):
        msg = formatter.run_complete(
            RUN_ID, 8.50, {"opus": 5.0, "gpt": 2.5, "gemini": 1.0}, 45,
        )
        assert "$8.50" in msg
        assert "opus $5.00" in msg
        assert "45 minutes" in msg
        assert "TASK-001" in msg


class TestCostAlert:
    def test_format(self):
        msg = formatter.cost_alert(RUN_ID, 31.50, 30.0)
        assert "$31.50" in msg
        assert "$30.00" in msg


class TestProgressUpdate:
    def test_format(self):
        msg = formatter.progress_update(RUN_ID, DOC, "2", "Drafting document...")
        assert RUN_ID in msg
        assert DOC in msg
        assert "Phase 2" in msg
        assert "Drafting" in msg


class TestAllTemplatesUnder4096:
    def test_short_messages_under_limit(self):
        """All templates with reasonable inputs should stay under 4096."""
        messages = [
            formatter.intake_start(RUN_ID, "new project", "WORKFLOW_SPEC", ["DOC.md"], "Q?"),
            formatter.section_complete(RUN_ID, DOC, "Purpose", "Short summary."),
            formatter.pre_audit_summary(RUN_ID, DOC, 3, 2),
            formatter.audit_conflict(RUN_ID, DOC, "arg1", "arg2"),
            formatter.crossdoc_result(RUN_ID, ["DOC.md"], []),
            formatter.run_complete(RUN_ID, 5.0, {"opus": 3.0}, 30),
            formatter.cost_alert(RUN_ID, 30.0, 30.0),
        ]
        for msg in messages:
            assert len(msg) < formatter.TELEGRAM_CHAR_LIMIT
