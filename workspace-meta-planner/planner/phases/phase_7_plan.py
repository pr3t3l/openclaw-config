"""Phase 7: Plan generator — spec → plan.md with phases and gates.

Handles large projects via module-by-module with human confirmation.
See spec.md §3 (Phase 7), spec.md §9 (Large Plan Handling).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from planner.prompts import plan_generator as prompts

logger = logging.getLogger(__name__)

LARGE_PROJECT_THRESHOLD = 10  # modules


@dataclass
class PlanResult:
    """Result of plan generation."""
    content: str
    is_large_project: bool = False
    module_count: int = 0


def generate_plan(
    spec_content: str,
    gateway: Any,
    constitution_rules: str = "",
    phase: str = "7",
    document: Optional[str] = None,
) -> PlanResult:
    """Generate plan.md from an approved spec.

    Args:
        spec_content: Full approved spec content.
        gateway: ModelGateway instance.
        constitution_rules: Constitution execution rules for context.
        phase: Phase for cost tracking.
        document: Document for cost tracking.

    Returns:
        PlanResult with plan content.
    """
    system = prompts.plan_system_prompt()
    prompt = prompts.plan_prompt(spec_content, constitution_rules)

    response = gateway.call_model(
        role="primary",
        prompt=prompt,
        context=system,
        phase=phase,
        document=document,
    )

    content = response["content"]
    module_count = _count_modules(content)

    return PlanResult(
        content=content,
        is_large_project=module_count >= LARGE_PROJECT_THRESHOLD,
        module_count=module_count,
    )


def generate_master_plan(
    modules: list[dict],
    gateway: Any,
    phase: str = "7",
) -> str:
    """Generate a master plan for large projects (10+ modules).

    Lists all modules with 1-line description and dependency order.

    Args:
        modules: List of {name, description, depends_on} dicts.
        gateway: ModelGateway instance.
        phase: Phase for cost tracking.

    Returns:
        Master plan content as markdown.
    """
    module_list = "\n".join(
        f"- **{m['name']}**: {m.get('description', '')} "
        f"(depends on: {', '.join(m.get('depends_on', [])) or 'none'})"
        for m in modules
    )

    prompt = (
        f"Create a master plan for a large project with {len(modules)} modules.\n\n"
        f"Modules:\n{module_list}\n\n"
        f"Output: Ordered list with dependency sequence. "
        f"One module at a time through full Phases 1-7."
    )

    response = gateway.call_model(role="primary", prompt=prompt, phase=phase)
    return response["content"]


def _count_modules(plan_content: str) -> int:
    """Estimate the number of modules/phases in a plan."""
    import re
    phase_headers = re.findall(r"^##\s+Phase\s+\d+", plan_content, re.MULTILINE)
    return len(phase_headers)
