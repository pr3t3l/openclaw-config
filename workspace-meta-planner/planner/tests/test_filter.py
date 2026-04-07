"""Tests for filter_for_agent.py — TASK-003."""

import pytest

from planner.filter_for_agent import (
    AGENT_FIELDS,
    detect_cross_references,
    extract_fields,
    filter_for_agent,
)


SAMPLE_STATE = {
    "current_document": {
        "type": "WORKFLOW_SPEC",
        "template": "workflow_spec",
        "content": "# Spec content here\nSee CONSTITUTION.md §3 for rules.",
        "sections_completed": ["purpose", "scope"],
        "intake_answers": {"purpose": "Build a planner"},
        "accepted_ideation": [],
    },
    "project_context": {
        "foundation_summary": "OpenClaw is a multi-agent platform.",
        "stack": {"os": "WSL", "db": "PostgreSQL"},
        "integrations_summary": "Telegram, LiteLLM, Stripe",
    },
    "constitution": {
        "rules": ["No stubs", "Max 2 retries"],
        "execution_rules": ["One task at a time"],
    },
    "decision_logs": {
        "PROJECT_FOUNDATION.md": "Decided to use PostgreSQL.",
    },
    "cross_references": ["CONSTITUTION.md §3"],
    "cost": {"total_usd": 5.0, "by_model": {"opus": 3.0}},
    "run_id": "RUN-20260406-001",
    "all_entity_maps": {"doc1": {"entities": []}},
    "approved_spec": {"content": "Full spec here"},
    "lessons_learned": {
        "relevant_entries": ["LL-PLAN-001"],
        "all_entries": ["LL-PLAN-001", "LL-ARCH-004"],
    },
    "data_model": {"summary": "Users, transactions"},
    "integrations": {"summary": "Telegram, Stripe"},
    "audit_findings": {"active_entries": [{"id": "AF-001"}]},
}


class TestFilterForAgent:
    def test_intake_interviewer(self):
        result = filter_for_agent(SAMPLE_STATE, "intake_interviewer")
        assert result["current_document"]["type"] == "WORKFLOW_SPEC"
        assert result["current_document"]["template"] == "workflow_spec"
        assert result["current_document"]["sections_completed"] == ["purpose", "scope"]
        assert "content" not in result["current_document"]
        assert "cost" not in result
        assert "run_id" not in result

    def test_technical_auditor(self):
        result = filter_for_agent(SAMPLE_STATE, "technical_auditor")
        assert result["current_document"]["content"] is not None
        assert result["current_document"]["type"] == "WORKFLOW_SPEC"
        assert result["constitution"]["rules"] is not None
        assert result["cross_references"] == ["CONSTITUTION.md §3"]
        assert "cost" not in result
        assert "decision_logs" not in result

    def test_architecture_reviewer(self):
        result = filter_for_agent(SAMPLE_STATE, "architecture_reviewer")
        assert result["current_document"]["content"] is not None
        assert result["project_context"]["stack"] is not None
        assert result["project_context"]["integrations_summary"] is not None
        assert "cost" not in result

    def test_plan_generator(self):
        result = filter_for_agent(SAMPLE_STATE, "plan_generator")
        assert result["approved_spec"]["content"] is not None
        assert result["constitution"]["execution_rules"] is not None
        assert result["lessons_learned"]["relevant_entries"] is not None
        assert "current_document" not in result

    def test_cross_doc_validator(self):
        result = filter_for_agent(SAMPLE_STATE, "cross_doc_validator")
        assert result["all_entity_maps"] is not None
        assert result["constitution"]["rules"] is not None
        assert "current_document" not in result

    def test_codebase_reconciler(self):
        state = {
            **SAMPLE_STATE,
            "git_diff_summary": "3 files changed",
            "existing_files_list": ["src/main.py"],
            "original_tasks": ["TASK-001"],
            "blocker_description": "Auth flow broken",
        }
        result = filter_for_agent(state, "codebase_reconciler")
        assert result["git_diff_summary"] == "3 files changed"
        assert "cost" not in result

    def test_undefined_role_raises(self):
        with pytest.raises(ValueError, match="No field mapping defined"):
            filter_for_agent(SAMPLE_STATE, "nonexistent_role")

    def test_all_defined_roles_work(self):
        """Every role in AGENT_FIELDS should work without error."""
        for role in AGENT_FIELDS:
            result = filter_for_agent(SAMPLE_STATE, role)
            assert isinstance(result, dict)

    def test_deny_by_default(self):
        """Fields NOT in the mapping must NOT appear in output."""
        result = filter_for_agent(SAMPLE_STATE, "intake_interviewer")
        assert "cost" not in result
        assert "run_id" not in result
        assert "all_entity_maps" not in result


class TestExtractFields:
    def test_simple_field(self):
        result = extract_fields({"a": 1, "b": 2}, ["a"])
        assert result == {"a": 1}

    def test_nested_field(self):
        data = {"x": {"y": {"z": 42}}}
        result = extract_fields(data, ["x.y.z"])
        assert result == {"x": {"y": {"z": 42}}}

    def test_missing_field_skipped(self):
        result = extract_fields({"a": 1}, ["b"])
        assert result == {}

    def test_multiple_fields(self):
        data = {"a": 1, "b": 2, "c": 3}
        result = extract_fields(data, ["a", "c"])
        assert result == {"a": 1, "c": 3}


class TestDetectCrossReferences:
    def test_finds_doc_references(self):
        content = "See CONSTITUTION.md §3 for rules. Also check DATA_MODEL.md."
        refs = detect_cross_references(content)
        assert "CONSTITUTION.md §3" in refs
        assert "DATA_MODEL.md" in refs

    def test_finds_section_refs(self):
        content = "Defined in INTEGRATIONS.md §4.2"
        refs = detect_cross_references(content)
        assert len(refs) == 1

    def test_no_refs(self):
        content = "This is plain text without document references."
        refs = detect_cross_references(content)
        assert refs == []

    def test_deduplicates(self):
        content = "See CONSTITUTION.md and again CONSTITUTION.md"
        refs = detect_cross_references(content)
        assert refs.count("CONSTITUTION.md") == 1
