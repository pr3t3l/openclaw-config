"""Prompt templates for Plan+Tasks auditors (Phase 7 audit)."""


def plan_audit_system_prompt() -> str:
    return (
        "You are auditing a build plan and task list for an SDD project. "
        "Focus on EXECUTABILITY and COMPLETENESS, not style.\n\n"
        "Check:\n"
        "- Every task has all 8 fields (objective, inputs, outputs, files_touched, "
        "done_when, depends_on, if_blocked, estimated)\n"
        "- Tasks are atomic (<30 min) and unambiguous\n"
        "- Dependencies are correct (no missing or circular deps)\n"
        "- Input references point to real spec sections\n"
        "- Plan phases have validation gates\n"
        "- No task requires clarification to execute\n\n"
        "For each issue: SEVERITY, TASK-ID, DESCRIPTION, SUGGESTION"
    )


def plan_audit_prompt(plan_content: str, tasks_content: str, spec_content: str = "") -> str:
    spec = f"\n\nSPEC (for reference validation):\n{spec_content[:3000]}" if spec_content else ""
    return (
        f"Audit the following plan and tasks:{spec}\n\n"
        f"PLAN:\n{plan_content[:4000]}\n\n"
        f"TASKS:\n{tasks_content[:6000]}"
    )
