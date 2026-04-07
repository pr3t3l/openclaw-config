"""Phase 1.5: Ideation — multi-model feature suggestions (conditional).

Sends concept to GPT + Gemini for ideas. Opus triages. Human filters.
Auto-skips for foundation docs. Human can also manually skip.
See spec.md §3 (Phase 1.5).
"""

import logging
from typing import Any, Optional

from planner.prompts import ideation_agent as prompts

logger = logging.getLogger(__name__)

# Document types that skip ideation automatically
SKIP_IDEATION_TYPES = {
    "PROJECT_FOUNDATION",
    "CONSTITUTION",
    "DATA_MODEL",
    "INTEGRATIONS",
    "LESSONS_LEARNED",
}


def should_skip(doc_type: str) -> bool:
    """Check if ideation should be skipped for this document type."""
    return doc_type in SKIP_IDEATION_TYPES


class IdeationResult:
    """Result of the ideation phase."""

    def __init__(
        self,
        skipped: bool = False,
        gpt_suggestions: Optional[list[dict]] = None,
        gemini_suggestions: Optional[list[dict]] = None,
        triage_result: Optional[dict] = None,
        accepted: Optional[list[dict]] = None,
    ) -> None:
        self.skipped = skipped
        self.gpt_suggestions = gpt_suggestions or []
        self.gemini_suggestions = gemini_suggestions or []
        self.triage_result = triage_result or {}
        self.accepted = accepted or []

    @property
    def is_empty(self) -> bool:
        return self.skipped or len(self.accepted) == 0


def ideate(
    doc_type: str,
    intake_summary: str,
    gateway: Any,
    phase: str = "1.5",
    document: Optional[str] = None,
) -> IdeationResult:
    """Run ideation with GPT + Gemini, then triage with Opus.

    Args:
        doc_type: Document type being worked on.
        intake_summary: Summary of intake answers to send to ideation agents.
        gateway: ModelGateway instance for making LLM calls.
        phase: Phase identifier for cost tracking.
        document: Document name for cost tracking.

    Returns:
        IdeationResult with suggestions from both models and triage.
    """
    if should_skip(doc_type):
        logger.info(f"Ideation skipped for {doc_type} (foundation doc)")
        return IdeationResult(skipped=True)

    prompt = prompts.ideation_prompt(doc_type, intake_summary)

    # Call GPT
    gpt_response = gateway.call_model(
        role="ideation_a",
        prompt=prompt,
        phase=phase,
        document=document,
    )

    # Call Gemini
    gemini_response = gateway.call_model(
        role="ideation_b",
        prompt=prompt,
        phase=phase,
        document=document,
    )

    # Parse suggestions
    gpt_suggestions = _parse_suggestions(gpt_response["content"], "gpt")
    gemini_suggestions = _parse_suggestions(gemini_response["content"], "gemini")

    # Triage with Opus
    triage_prompt = prompts.triage_prompt(
        doc_type, gpt_response["content"], gemini_response["content"]
    )
    triage_response = gateway.call_model(
        role="primary",
        prompt=triage_prompt,
        phase=phase,
        document=document,
    )

    triage_result = _parse_triage(triage_response["content"])

    return IdeationResult(
        skipped=False,
        gpt_suggestions=gpt_suggestions,
        gemini_suggestions=gemini_suggestions,
        triage_result=triage_result,
        accepted=[],  # Human decides what to accept
    )


def _parse_suggestions(content: str, source: str) -> list[dict]:
    """Parse numbered suggestions from model output."""
    suggestions = []
    lines = content.strip().split("\n")
    current = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Match numbered items: "1.", "2.", etc.
        if len(line) > 2 and line[0].isdigit() and line[1] in ".)" :
            if current:
                suggestions.append(current)
            current = {
                "feature": line[2:].strip().lstrip(". "),
                "source": source,
                "assessment": "",
            }
        elif current:
            current["assessment"] += " " + line

    if current:
        suggestions.append(current)

    return suggestions


def _parse_triage(content: str) -> dict:
    """Parse triage output into recommended/skipped lists."""
    recommended = []
    skipped = []
    current_section = None

    for line in content.strip().split("\n"):
        line = line.strip()
        upper = line.upper()
        if "RECOMMEND" in upper:
            current_section = "recommended"
        elif "SKIP" in upper:
            current_section = "skipped"
        elif line and line[0].isdigit() and current_section:
            item = line[2:].strip().lstrip(". ")
            if current_section == "recommended":
                recommended.append(item)
            else:
                skipped.append(item)

    return {"recommended": recommended, "skipped": skipped}
