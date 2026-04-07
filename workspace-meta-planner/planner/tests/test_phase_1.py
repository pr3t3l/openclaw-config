"""Tests for phases/phase_1_intake.py — TASK-016."""

import pytest

from planner.phases.phase_1_intake import IntakeSession, MAX_ROUNDS_PER_SECTION
from planner.template_loader import TemplateSection


def _make_sections(n: int = 3) -> list[TemplateSection]:
    return [
        TemplateSection(2, f"Section {i+1}", f"Template content for section {i+1}")
        for i in range(n)
    ]


class TestIntakeSession:
    def test_init(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections())
        assert not session.is_complete
        assert session.progress == "0/3 sections"
        assert session.current_section.title == "Section 1"

    def test_get_first_prompt(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections())
        result = session.get_next_prompt()
        assert result["action"] == "question"
        assert result["section"] == "Section 1"
        assert result["round_num"] == 1
        assert "system_prompt" in result
        assert "user_prompt" in result

    def test_record_answer(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections())
        session.get_next_prompt()
        result = session.record_answer("This is the answer for section 1")
        assert result["action"] == "confirm_section"
        assert "Section 1" in result["section"]

    def test_confirm_advances(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections())
        session.get_next_prompt()
        session.record_answer("Answer 1")
        result = session.confirm_section(True)
        assert result["action"] == "question"
        assert result["section"] == "Section 2"
        assert session.progress == "1/3 sections"

    def test_reject_retries(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections())
        session.get_next_prompt()
        session.record_answer("Bad answer")
        result = session.confirm_section(False)
        assert result["action"] == "question"
        assert result["section"] == "Section 1"  # Same section

    def test_completes_after_all_sections(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(2))
        for i in range(2):
            session.get_next_prompt()
            session.record_answer(f"Answer {i}")
            result = session.confirm_section(True)
        assert result["action"] == "complete"
        assert session.is_complete
        assert len(session.answers) == 2

    def test_answers_stored(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(1))
        session.get_next_prompt()
        session.record_answer("The purpose is X")
        session.confirm_section(True)
        assert session.answers["Section 1"] == "The purpose is X"


class TestAssumedDefaults:
    def test_assumed_default_after_max_rounds(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(1))
        # Exhaust rounds
        for _ in range(MAX_ROUNDS_PER_SECTION):
            session.get_next_prompt()
        result = session.get_next_prompt()  # Round 6 → assumed default
        assert result["action"] == "assumed_default"
        assert "ASSUMPTION" in result["message"]

    def test_accept_assumption(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(1))
        for _ in range(MAX_ROUNDS_PER_SECTION + 1):
            session.get_next_prompt()
        result = session.accept_assumption("PostgreSQL because self-hosted")
        assert result["action"] == "complete"
        assert "[ASSUMPTION" in session.answers["Section 1"]
        assert len(session.assumptions) == 1

    def test_assumption_tagged(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(2))
        for _ in range(MAX_ROUNDS_PER_SECTION + 1):
            session.get_next_prompt()
        session.accept_assumption("Default value")
        assert session.answers["Section 1"].startswith("[ASSUMPTION")

    def test_propose_assumed_default(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(1))
        result = session.propose_assumed_default()
        assert result["action"] == "assumed_default"


class TestContext:
    def test_decision_logs_in_context(self):
        logs = {"PROJECT_FOUNDATION.md": "Decided to use PostgreSQL."}
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(), decision_logs=logs)
        result = session.get_next_prompt()
        assert "system_prompt" in result

    def test_project_context_used(self):
        session = IntakeSession(
            "WORKFLOW_SPEC", _make_sections(),
            project_context="OpenClaw is a multi-agent platform."
        )
        result = session.get_next_prompt()
        assert "system_prompt" in result

    def test_previous_answers_in_context(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(2))
        session.get_next_prompt()
        session.record_answer("First answer")
        session.confirm_section(True)
        # Second section should have context from first
        result = session.get_next_prompt()
        assert result["action"] == "question"


class TestEdgeCases:
    def test_empty_sections(self):
        session = IntakeSession("WORKFLOW_SPEC", [])
        assert session.is_complete
        result = session.get_next_prompt()
        assert result["action"] == "complete"

    def test_single_section(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(1))
        session.get_next_prompt()
        session.record_answer("The answer")
        result = session.confirm_section(True)
        assert result["action"] == "complete"

    def test_record_after_complete(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(1))
        session.get_next_prompt()
        session.record_answer("Done")
        session.confirm_section(True)
        result = session.record_answer("Extra")
        assert result["action"] == "complete"

    def test_sections_completed_tracking(self):
        session = IntakeSession("WORKFLOW_SPEC", _make_sections(2))
        session.get_next_prompt()
        session.record_answer("A1")
        session.confirm_section(True)
        assert "Section 1" in session.sections_completed
        assert "Section 2" not in session.sections_completed
