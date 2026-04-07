"""Context compression for agent calls — deny-by-default field filtering.

Every agent receives ONLY the fields it needs. The orchestrator is Python code
(not an LLM) that filters planner_state.json before passing to any agent.

See spec.md §7.1 (Context Compression Rule).
"""

import re
from typing import Any

# Static mapping: each agent role → list of required field paths.
# DENY-BY-DEFAULT: if a field is not in the mapping, it is NOT sent.
# If a new field is added to the state, it must be explicitly added
# to relevant agent mappings before it becomes available.
AGENT_FIELDS: dict[str, list[str]] = {
    "intake_interviewer": [
        "current_document.type",
        "current_document.template",
        "current_document.sections_completed",
        "project_context.foundation_summary",
        "decision_logs",
    ],
    "technical_auditor": [
        "current_document.content",
        "current_document.type",
        "constitution.rules",
        "cross_references",
    ],
    "architecture_reviewer": [
        "current_document.content",
        "current_document.type",
        "project_context.stack",
        "project_context.integrations_summary",
        "cross_references",
    ],
    "plan_generator": [
        "approved_spec.content",
        "constitution.execution_rules",
        "lessons_learned.relevant_entries",
        "data_model.summary",
        "integrations.summary",
    ],
    "cross_doc_validator": [
        "all_entity_maps",
        "constitution.rules",
    ],
    "codebase_reconciler": [
        "git_diff_summary",
        "existing_files_list",
        "original_tasks",
        "blocker_description",
    ],
    "ideation_agent": [
        "current_document.type",
        "current_document.intake_answers",
        "project_context.foundation_summary",
    ],
    "ideation_triager": [
        "current_document.type",
        "ideation_results",
        "project_context.foundation_summary",
    ],
    "document_drafter": [
        "current_document.type",
        "current_document.template",
        "current_document.intake_answers",
        "current_document.accepted_ideation",
        "project_context.foundation_summary",
        "constitution.rules",
        "decision_logs",
    ],
    "pre_audit_checker": [
        "current_document.content",
        "current_document.type",
        "audit_findings.active_entries",
    ],
    "audit_triager": [
        "current_document.content",
        "current_document.type",
        "audit_results_raw",
    ],
    "lessons_validator": [
        "current_document.content",
        "current_document.type",
        "lessons_learned.all_entries",
    ],
    "document_finalizer": [
        "current_document.content",
        "current_document.type",
        "audit_triage_result",
        "lessons_check_result",
    ],
    "record_updater": [
        "current_document.content",
        "current_document.type",
        "conversation_history",
        "decision_logs",
    ],
    "task_generator": [
        "approved_plan.content",
        "approved_spec.content",
        "constitution.execution_rules",
    ],
    "plan_auditor": [
        "plan_content",
        "tasks_content",
        "approved_spec.content",
        "constitution.execution_rules",
    ],
}

# Document name patterns for cross-reference detection
_DOC_PATTERNS = [
    r"PROJECT_FOUNDATION\.md",
    r"CONSTITUTION\.md",
    r"DATA_MODEL\.md",
    r"INTEGRATIONS\.md",
    r"LESSONS_LEARNED\.md",
    r"AUDIT_FINDINGS\.md",
    r"(?:MODULE|WORKFLOW)_SPEC\.md",
    r"spec\.md",
    r"plan\.md",
    r"tasks\.md",
]
_DOC_REF_REGEX = re.compile(
    r"(?:" + "|".join(_DOC_PATTERNS) + r")(?:\s*§\d+(?:\.\d+)?)?",
    re.IGNORECASE,
)


def extract_fields(full_state: dict, field_paths: list[str]) -> dict:
    """Extract only the specified dot-path fields from state.

    Args:
        full_state: The complete state/context dict.
        field_paths: List of dot-separated paths like "current_document.type".

    Returns:
        A filtered dict containing only the requested fields.
    """
    result: dict[str, Any] = {}
    for path in field_paths:
        parts = path.split(".")
        value = _get_nested(full_state, parts)
        if value is not None:
            _set_nested(result, parts, value)
    return result


def _get_nested(d: dict, keys: list[str]) -> Any:
    """Traverse nested dict by key path. Returns None if any key is missing."""
    current = d
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _set_nested(d: dict, keys: list[str], value: Any) -> None:
    """Set a value in a nested dict by key path, creating intermediates."""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def detect_cross_references(content: str) -> list[str]:
    """Scan document content for references to other SDD documents.

    Returns a list of unique document references found (e.g., "CONSTITUTION.md §3").
    """
    matches = _DOC_REF_REGEX.findall(content)
    return sorted(set(matches))


def filter_for_agent(full_state: dict, agent_role: str) -> dict:
    """Filter state to only include fields needed by the specified agent role.

    Args:
        full_state: Complete state/context dict.
        agent_role: The agent role identifier (must be in AGENT_FIELDS).

    Returns:
        Filtered dict with only the fields mapped for this role.

    Raises:
        ValueError: If agent_role has no field mapping defined.
    """
    fields = AGENT_FIELDS.get(agent_role)
    if fields is None:
        raise ValueError(f"No field mapping defined for agent role: {agent_role}")
    return extract_fields(full_state, fields)
