"""Monolith reviewer — audit low-confidence blocks, present mapping to human.

See spec.md §3 (Monolith extraction steps 3-4).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from planner.monolith.confidence import ConfidenceResult
from planner.monolith.mapper import BlockMapping

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result of reviewing a low-confidence block."""
    block_id: int
    original_targets: list[str]
    auditor_targets: list[str]
    auditor_reasoning: str = ""
    accepted: bool = False


@dataclass
class MappingPresentation:
    """Human-readable mapping presentation for approval."""
    template: str
    blocks: list[dict] = field(default_factory=list)  # {block_id, heading, confidence, word_count}


def audit_low_confidence(
    low_confidence: list[ConfidenceResult],
    gateway: Any,
    phase: str = "0",
    document: Optional[str] = None,
) -> list[ReviewResult]:
    """Send low-confidence blocks to 1 auditor model for validation.

    Args:
        low_confidence: Blocks with confidence < 80%.
        gateway: ModelGateway instance.
        phase: Phase for cost tracking.
        document: Document for cost tracking.

    Returns:
        List of ReviewResult with auditor recommendations.
    """
    if not low_confidence:
        return []

    results = []

    for cr in low_confidence:
        block = cr.mapping.block
        prompt = (
            f"A content block from a monolith document needs classification.\n\n"
            f"Block heading: {block.heading}\n"
            f"Block content ({block.word_count} words):\n{block.content[:2000]}\n\n"
            f"Current best guess: {', '.join(cr.mapping.targets) or 'none'} "
            f"(confidence: {cr.confidence}, score: {cr.top_score:.0%})\n\n"
            f"Which SDD template(s) should this block map to?\n"
            f"Options: PROJECT_FOUNDATION, CONSTITUTION, DATA_MODEL, INTEGRATIONS, "
            f"LESSONS_LEARNED, WORKFLOW_SPEC, MODULE_SPEC, NONE\n\n"
            f"Respond with: TARGETS: [comma-separated list]\nREASON: [brief explanation]"
        )

        response = gateway.call_model(
            role="auditor_gpt",
            prompt=prompt,
            phase=phase,
            document=document,
        )

        targets, reasoning = _parse_auditor_response(response["content"])

        results.append(ReviewResult(
            block_id=block.block_id,
            original_targets=cr.mapping.targets,
            auditor_targets=targets,
            auditor_reasoning=reasoning,
        ))

    return results


def present_mapping(
    all_results: list[ConfidenceResult],
    review_results: Optional[list[ReviewResult]] = None,
) -> list[MappingPresentation]:
    """Build human-readable mapping presentation per template.

    Args:
        all_results: All confidence results.
        review_results: Optional auditor review results for low-confidence blocks.

    Returns:
        List of MappingPresentation, one per template.
    """
    # Build review lookup
    review_map = {}
    if review_results:
        for rr in review_results:
            review_map[rr.block_id] = rr

    # Group blocks by target template
    template_blocks: dict[str, list[dict]] = {}

    for cr in all_results:
        # Use auditor targets for reviewed blocks, original otherwise
        rr = review_map.get(cr.mapping.block.block_id)
        targets = rr.auditor_targets if rr else cr.mapping.targets

        for target in targets:
            if target not in template_blocks:
                template_blocks[target] = []
            template_blocks[target].append({
                "block_id": cr.mapping.block.block_id,
                "heading": cr.mapping.block.heading,
                "confidence": cr.confidence,
                "word_count": cr.mapping.block.word_count,
                "reviewed": rr is not None if rr else False,
            })

    return [
        MappingPresentation(template=t, blocks=blocks)
        for t, blocks in sorted(template_blocks.items())
    ]


def format_mapping_for_telegram(presentations: list[MappingPresentation]) -> str:
    """Format mapping presentation for Telegram display."""
    lines = ["📋 Monolith Mapping Results:\n"]

    for p in presentations:
        lines.append(f"**{p.template}** ({len(p.blocks)} blocks):")
        for b in p.blocks:
            reviewed = " ✓audited" if b.get("reviewed") else ""
            lines.append(
                f"  - Block {b['block_id']}: \"{b['heading']}\" "
                f"({b['confidence']}, {b['word_count']} words){reviewed}"
            )
        lines.append("")

    lines.append("Approve this mapping? (yes / adjust)")
    return "\n".join(lines)


def _parse_auditor_response(content: str) -> tuple[list[str], str]:
    """Parse auditor response into targets and reasoning."""
    targets = []
    reasoning = ""

    for line in content.split("\n"):
        line = line.strip()
        if line.upper().startswith("TARGETS:") or line.upper().startswith("TARGET:"):
            raw = line.split(":", 1)[1].strip()
            targets = [t.strip() for t in raw.split(",") if t.strip() and t.strip() != "NONE"]
        elif line.upper().startswith("REASON:"):
            reasoning = line.split(":", 1)[1].strip()

    return targets, reasoning
