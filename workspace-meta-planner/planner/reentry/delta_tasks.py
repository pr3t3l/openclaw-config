"""Delta task generator — generate new tasks for VOID items only.

See spec.md §10 (Re-Entry Step 4).
"""

import logging
from typing import Any, Optional

from planner.reentry.impact import ImpactReport

logger = logging.getLogger(__name__)


def generate_delta_tasks(
    impact_report: ImpactReport,
    patched_spec: str,
    existing_code_summary: str,
    gateway: Any,
    phase: str = "fix",
    document: Optional[str] = None,
) -> str:
    """Generate delta tasks for VOID items.

    NEEDS_REVIEW items are flagged but not regenerated.
    Delta tasks are aware of existing code state.

    Args:
        impact_report: Impact analysis with VOID/NEEDS_REVIEW tasks.
        patched_spec: Updated spec content.
        existing_code_summary: What exists in the codebase (from reconciler).
        gateway: ModelGateway instance.
        phase: Phase for cost tracking.
        document: Document for cost tracking.

    Returns:
        New tasks.md content for delta tasks.
    """
    void_tasks = impact_report.void_tasks
    review_tasks = impact_report.needs_review_tasks

    if not void_tasks:
        return "# Delta Tasks\n\nNo VOID tasks — no delta tasks needed.\n"

    prompt = (
        f"Generate replacement tasks for the following VOID tasks.\n\n"
        f"VOID tasks (must be regenerated): {', '.join(void_tasks)}\n"
        f"NEEDS_REVIEW tasks (flagged, not regenerated): {', '.join(review_tasks) or 'none'}\n\n"
        f"Existing code state:\n{existing_code_summary[:2000]}\n\n"
        f"Updated spec:\n{patched_spec[:4000]}\n\n"
        f"Generate new tasks with all 8 required fields. "
        f"Tasks must account for existing code (don't re-create what exists)."
    )

    response = gateway.call_model(
        role="primary", prompt=prompt, phase=phase, document=document,
    )

    return response["content"]
