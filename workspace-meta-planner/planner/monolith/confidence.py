"""Confidence scoring for monolith block mappings.

HIGH >80%, MEDIUM 50-80%, LOW <50%.
Non-HIGH blocks flagged for review.
See spec.md §3 (Monolith extraction step 2).
"""

from dataclasses import dataclass
from planner.monolith.mapper import BlockMapping


@dataclass
class ConfidenceResult:
    """Confidence classification for a mapping."""
    mapping: BlockMapping
    confidence: str  # HIGH, MEDIUM, LOW
    top_score: float
    needs_review: bool


def score_mapping(mapping: BlockMapping) -> ConfidenceResult:
    """Score confidence of a block mapping.

    Args:
        mapping: A BlockMapping with targets and scores.

    Returns:
        ConfidenceResult with confidence level.
    """
    if not mapping.scores:
        return ConfidenceResult(
            mapping=mapping, confidence="LOW",
            top_score=0.0, needs_review=True,
        )

    top_score = max(mapping.scores.values())

    if top_score >= 0.80:
        confidence = "HIGH"
    elif top_score >= 0.50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return ConfidenceResult(
        mapping=mapping,
        confidence=confidence,
        top_score=top_score,
        needs_review=confidence != "HIGH",
    )


def score_all(mappings: list[BlockMapping]) -> list[ConfidenceResult]:
    """Score all mappings and return results."""
    return [score_mapping(m) for m in mappings]


def get_review_needed(results: list[ConfidenceResult]) -> list[ConfidenceResult]:
    """Get all mappings that need human or auditor review (<80%)."""
    return [r for r in results if r.needs_review]
