"""Monolith mapper — assign content blocks to SDD templates.

Supports multi-tagging (one block can feed multiple templates).
See spec.md §3 (Monolith extraction step 2).
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from planner.monolith.parser import ContentBlock

# Keyword-based mapping rules: template → keywords that indicate relevance
TEMPLATE_KEYWORDS: dict[str, list[str]] = {
    "PROJECT_FOUNDATION": [
        "purpose", "vision", "mission", "stack", "roadmap", "tech stack",
        "what this is", "problem", "who it's for", "monetization",
        "competitive", "design system",
    ],
    "CONSTITUTION": [
        "rule", "principle", "constraint", "forbidden", "never", "always",
        "must", "policy", "guardrail", "emergency", "kill switch",
    ],
    "DATA_MODEL": [
        "schema", "table", "database", "column", "field", "entity",
        "migration", "postgresql", "model", "index", "foreign key",
    ],
    "INTEGRATIONS": [
        "api", "endpoint", "webhook", "integration", "external",
        "telegram", "stripe", "oauth", "authentication", "provider",
    ],
    "LESSONS_LEARNED": [
        "lesson", "failure", "fix", "bug", "incident", "mistake",
        "workaround", "anti-pattern", "learned",
    ],
    "WORKFLOW_SPEC": [
        "workflow", "pipeline", "phase", "agent", "gate", "trigger",
        "input", "output", "contract", "orchestrat",
    ],
    "MODULE_SPEC": [
        "module", "feature", "component", "service", "function",
        "interface", "specification",
    ],
}


@dataclass
class BlockMapping:
    """Mapping of a content block to one or more SDD templates."""
    block: ContentBlock
    targets: list[str] = field(default_factory=list)  # Template types
    scores: dict[str, float] = field(default_factory=dict)  # template → score


def map_blocks(blocks: list[ContentBlock]) -> list[BlockMapping]:
    """Assign each block to SDD templates based on keyword matching.

    Supports multi-tagging: a block can map to multiple templates.

    Args:
        blocks: Parsed content blocks.

    Returns:
        List of BlockMapping with target templates and confidence scores.
    """
    mappings: list[BlockMapping] = []

    for block in blocks:
        scores = _score_block(block)
        # Include all templates with score > 0
        targets = sorted(
            [t for t, s in scores.items() if s > 0],
            key=lambda t: scores[t],
            reverse=True,
        )
        mappings.append(BlockMapping(
            block=block,
            targets=targets,
            scores={t: scores[t] for t in targets},
        ))

    return mappings


def _score_block(block: ContentBlock) -> dict[str, float]:
    """Score a block against each template type."""
    text = (block.heading + " " + block.content).lower()
    scores: dict[str, float] = {}

    for template, keywords in TEMPLATE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        total = len(keywords)
        scores[template] = hits / total if total > 0 else 0.0

    return scores
