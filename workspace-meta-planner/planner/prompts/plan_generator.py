"""Prompt templates for Plan and Task generators (Phase 7)."""


def plan_system_prompt() -> str:
    return (
        "You are an SDD plan generator. Convert an approved spec into a build plan "
        "with phases, validation gates, and dependency ordering.\n\n"
        "Rules:\n"
        "- Each phase has a clear goal and deliverables\n"
        "- Each phase ends with a validation gate\n"
        "- Dependencies between phases are explicit\n"
        "- Phases are ordered so dependencies are satisfied\n"
        "- Output valid Markdown following plan.md template"
    )


def plan_prompt(spec_content: str, constitution_rules: str = "") -> str:
    rules = f"\n\nConstitution execution rules:\n{constitution_rules}" if constitution_rules else ""
    return (
        f"Generate a plan.md from the following approved spec.{rules}\n\n"
        f"SPEC:\n{spec_content[:8000]}"
    )


def task_system_prompt() -> str:
    return (
        "You are an SDD task generator. Convert a plan into atomic tasks "
        "(<30 min each) with all 8 required fields.\n\n"
        "Required fields per task:\n"
        "1. Objective\n2. Inputs\n3. Outputs\n4. Files touched\n"
        "5. Done when\n6. depends_on\n7. if_blocked\n8. Estimated\n\n"
        "Rules:\n"
        "- Tasks must be atomic (one responsibility)\n"
        "- Inputs must reference existing doc sections\n"
        "- depends_on must reference other TASK-XXX IDs\n"
        "- No circular dependencies\n"
        "- if_blocked has MINOR/MODERATE/CRITICAL actions"
    )


def task_prompt(plan_content: str, spec_content: str = "") -> str:
    spec = f"\n\nSPEC (for input references):\n{spec_content[:4000]}" if spec_content else ""
    return f"Generate tasks.md from the following plan:{spec}\n\nPLAN:\n{plan_content[:6000]}"
