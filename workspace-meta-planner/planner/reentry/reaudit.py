"""Selective re-audit — re-audit only changed sections after spec patch.

See spec.md §10 (Re-Entry Step 3-4).
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def selective_reaudit(
    patched_spec: str,
    affected_sections: list[str],
    gateway: Any,
    phase: str = "fix",
    document: Optional[str] = None,
) -> dict:
    """Re-audit only the changed sections of a patched spec.

    Uses 1 auditor (not full 4-call), focused on the patched sections.

    Args:
        patched_spec: The patched spec content.
        affected_sections: Sections that were modified.
        gateway: ModelGateway instance.
        phase: Phase for cost tracking.
        document: Document for cost tracking.

    Returns:
        Dict with passed (bool) and findings (list).
    """
    sections_str = ", ".join(affected_sections)

    prompt = (
        f"A spec was patched after a blocker. Review ONLY the changed sections "
        f"for correctness.\n\n"
        f"Changed sections: {sections_str}\n\n"
        f"Patched spec:\n{patched_spec[:6000]}\n\n"
        f"Are the patched sections correct? Flag any new issues."
    )

    response = gateway.call_model(
        role="auditor_gpt", prompt=prompt, phase=phase, document=document,
    )

    content = response["content"].lower()
    passed = "no issue" in content or "correct" in content or "no new" in content

    return {"passed": passed, "findings": response["content"]}
