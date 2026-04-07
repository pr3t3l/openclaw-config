"""Spec patcher — update affected spec sections after blocker.

See spec.md §10 (Re-Entry Step 3).
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def patch_spec(
    spec_content: str,
    blocker_description: str,
    affected_sections: list[str],
    gateway: Any,
    phase: str = "fix",
    document: Optional[str] = None,
) -> str:
    """Patch affected sections of the spec based on blocker context.

    Args:
        spec_content: Current spec content.
        blocker_description: What went wrong and why.
        affected_sections: Section headings to patch.
        gateway: ModelGateway instance.
        phase: Phase for cost tracking.
        document: Document for cost tracking.

    Returns:
        Patched spec content.
    """
    sections_str = ", ".join(affected_sections) if affected_sections else "relevant sections"

    prompt = (
        f"A spec needs to be patched because of a blocker during implementation.\n\n"
        f"BLOCKER: {blocker_description}\n\n"
        f"AFFECTED SECTIONS: {sections_str}\n\n"
        f"CURRENT SPEC:\n{spec_content[:8000]}\n\n"
        f"Produce the updated spec with ONLY the affected sections modified. "
        f"Keep all other sections unchanged. Mark changes with <!-- PATCHED --> comments."
    )

    response = gateway.call_model(
        role="primary", prompt=prompt, phase=phase, document=document,
    )

    return response["content"]
