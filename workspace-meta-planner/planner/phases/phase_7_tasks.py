"""Phase 7: Task generator — plan → tasks.md with all 8 required fields.

See spec.md §3 (Phase 7), spec.md §10 (task schema).
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from planner.prompts import plan_generator as prompts
from planner.task_validator import validate_tasks

logger = logging.getLogger(__name__)


@dataclass
class TasksResult:
    """Result of task generation."""
    content: str
    validation_passed: bool
    validation_errors: list[str]
    total_tasks: int = 0


def generate_tasks(
    plan_content: str,
    spec_content: str,
    gateway: Any,
    phase: str = "7",
    document: Optional[str] = None,
    max_retries: int = 1,
) -> TasksResult:
    """Generate tasks.md from plan.md.

    Args:
        plan_content: Approved plan.md content.
        spec_content: Approved spec content (for input references).
        gateway: ModelGateway instance.
        phase: Phase for cost tracking.
        document: Document for cost tracking.
        max_retries: Re-generation attempts if validation fails.

    Returns:
        TasksResult with content and validation status.
    """
    system = prompts.task_system_prompt()
    user_prompt = prompts.task_prompt(plan_content, spec_content)

    content = ""
    validation_passed = False
    validation_errors: list[str] = []

    for attempt in range(1 + max_retries):
        if attempt > 0:
            user_prompt = (
                f"The previous tasks had validation errors:\n"
                + "\n".join(f"- {e}" for e in validation_errors)
                + f"\n\nFix the issues and regenerate.\n\nPrevious tasks:\n{content[:4000]}"
            )

        response = gateway.call_model(
            role="primary",
            prompt=user_prompt,
            context=system,
            phase=phase,
            document=document,
        )
        content = response["content"]

        result = validate_tasks(content, spec_content)

        if result.passed:
            validation_passed = True
            validation_errors = []
            logger.info(f"Tasks validated on attempt {attempt + 1}: {result.total_tasks} tasks")
            break
        else:
            validation_errors = []
            for tv in result.task_results:
                if not tv.valid:
                    if tv.missing_fields:
                        validation_errors.append(f"{tv.task_id}: missing {', '.join(tv.missing_fields)}")
                    for issue in tv.issues:
                        validation_errors.append(f"{tv.task_id}: {issue}")
            for cycle in result.circular_deps:
                validation_errors.append(f"Circular dependency: {cycle}")
            logger.warning(f"Tasks validation failed (attempt {attempt + 1}): {len(validation_errors)} issues")

    return TasksResult(
        content=content,
        validation_passed=validation_passed,
        validation_errors=validation_errors,
        total_tasks=len([l for l in content.split("\n") if l.strip().startswith("### TASK-")]),
    )
