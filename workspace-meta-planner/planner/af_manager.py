"""AF lifecycle manager — propose, dedupe, approve, deprecate, archive.

Manages AUDIT_FINDINGS.md entries through their lifecycle:
PROPOSED → APPROVED → ACTIVE → DEPRECATED → ARCHIVED
See spec.md §11 (AUDIT_FINDINGS lifecycle).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AFEntry:
    """An Audit Finding entry with lifecycle state."""
    af_id: str
    title: str
    status: str  # PROPOSED, APPROVED, ACTIVE, DEPRECATED, ARCHIVED
    af_class: str  # safe_autofix, requires_review
    confidence: str  # HIGH, MEDIUM, LOW
    pattern: str
    fix: str
    applies_to: list[str] = field(default_factory=list)
    first_found: str = ""
    last_triggered: str = ""


def propose(
    finding_description: str,
    fix: str,
    af_class: str = "requires_review",
    confidence: str = "MEDIUM",
    applies_to: Optional[list[str]] = None,
    run_id: str = "",
    existing_entries: Optional[list[AFEntry]] = None,
) -> Optional[AFEntry]:
    """Propose a new AF entry. Deduplicates against existing entries.

    Returns:
        New AFEntry if unique, None if duplicate detected.
    """
    if existing_entries and dedupe(finding_description, existing_entries):
        logger.info(f"Duplicate AF detected, skipping: {finding_description[:50]}")
        return None

    next_id = _next_af_id(existing_entries or [])

    entry = AFEntry(
        af_id=next_id,
        title=finding_description[:80],
        status="PROPOSED",
        af_class=af_class,
        confidence=confidence,
        pattern=finding_description,
        fix=fix,
        applies_to=applies_to or ["ALL"],
        first_found=run_id,
    )

    logger.info(f"Proposed {next_id}: {finding_description[:50]}")
    return entry


def dedupe(description: str, existing: list[AFEntry]) -> bool:
    """Check if a finding is similar to an existing entry.

    Uses keyword overlap for similarity detection.
    """
    desc_words = set(w.lower() for w in description.split() if len(w) > 3)
    if not desc_words:
        return False

    for entry in existing:
        entry_words = set(w.lower() for w in entry.pattern.split() if len(w) > 3)
        if not entry_words:
            continue
        overlap = desc_words & entry_words
        similarity = len(overlap) / max(len(desc_words), len(entry_words))
        if similarity > 0.5:
            return True
    return False


def approve(entry: AFEntry) -> AFEntry:
    """Move entry from PROPOSED to ACTIVE (human approved)."""
    if entry.status not in ("PROPOSED", "APPROVED"):
        logger.warning(f"Cannot approve {entry.af_id} in status {entry.status}")
        return entry
    entry.status = "ACTIVE"
    logger.info(f"Approved {entry.af_id} → ACTIVE")
    return entry


def deprecate(entry: AFEntry) -> AFEntry:
    """Move entry to DEPRECATED."""
    entry.status = "DEPRECATED"
    logger.info(f"Deprecated {entry.af_id}")
    return entry


def archive(entry: AFEntry) -> AFEntry:
    """Move entry to ARCHIVED."""
    entry.status = "ARCHIVED"
    logger.info(f"Archived {entry.af_id}")
    return entry


def classify(finding: str) -> str:
    """Classify a finding as safe_autofix or requires_review.

    Safe: structural/formatting issues.
    Review: logic/architecture changes.
    """
    safe_keywords = ["format", "header", "section", "missing section", "typo", "style", "order"]
    for kw in safe_keywords:
        if kw in finding.lower():
            return "safe_autofix"
    return "requires_review"


def flag_stale(entries: list[AFEntry], months_threshold: int = 3) -> list[AFEntry]:
    """Flag entries not triggered recently for deprecation review.

    Note: actual date comparison would need last_triggered dates.
    For now, flags entries with empty last_triggered.
    """
    stale = []
    for entry in entries:
        if entry.status == "ACTIVE" and not entry.last_triggered:
            stale.append(entry)
    return stale


def _next_af_id(existing: list[AFEntry]) -> str:
    """Generate the next AF-XXX ID."""
    if not existing:
        return "AF-001"
    max_num = 0
    for e in existing:
        match = re.match(r"AF-(\d+)", e.af_id)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"AF-{max_num + 1:03d}"
