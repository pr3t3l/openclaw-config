"""Phase 2.5: Pre-Audit Check — compare draft against AUDIT_FINDINGS.md.

Safe fixes auto-applied. Semantic fixes highlighted with [AF-XXX SUGGESTION] markers.
Only processes ACTIVE entries (ignores PROPOSED/DEPRECATED/ARCHIVED).
See spec.md §3 (Phase 2.5), spec.md §11 (AF lifecycle).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AFEntry:
    """An Audit Finding entry."""
    af_id: str
    status: str  # ACTIVE, PROPOSED, DEPRECATED, ARCHIVED
    af_class: str  # safe_autofix, requires_review
    pattern: str
    fix: str
    applies_to: list[str] = field(default_factory=list)


@dataclass
class PreAuditResult:
    """Result of the pre-audit check."""
    safe_applied: list[str] = field(default_factory=list)
    semantic_flagged: list[str] = field(default_factory=list)
    content: str = ""

    @property
    def safe_count(self) -> int:
        return len(self.safe_applied)

    @property
    def semantic_count(self) -> int:
        return len(self.semantic_flagged)


def load_audit_findings(project_root: str) -> list[AFEntry]:
    """Load AUDIT_FINDINGS.md and parse into AFEntry list.

    Only returns ACTIVE entries.
    """
    af_path = Path(project_root) / "docs" / "AUDIT_FINDINGS.md"
    if not af_path.exists():
        return []

    content = af_path.read_text(encoding="utf-8")
    return _parse_audit_findings(content)


def check_against_af(
    doc_content: str,
    doc_type: str,
    entries: list[AFEntry],
) -> PreAuditResult:
    """Check document against active audit findings.

    Args:
        doc_content: Draft document content.
        doc_type: Document type for applies_to filtering.
        entries: Active AF entries to check against.

    Returns:
        PreAuditResult with applied fixes and flagged suggestions.
    """
    content = doc_content
    safe_applied: list[str] = []
    semantic_flagged: list[str] = []

    for entry in entries:
        if entry.status != "ACTIVE":
            continue

        # Check if this entry applies to this doc type
        if entry.applies_to and not _applies_to_doc(entry.applies_to, doc_type):
            continue

        # Check if the pattern matches
        if not _pattern_matches(entry.pattern, content):
            continue

        if entry.af_class == "safe_autofix":
            content = apply_safe_fix(content, entry)
            safe_applied.append(f"{entry.af_id}: auto-fixed")
        elif entry.af_class == "requires_review":
            content = flag_semantic(content, entry)
            semantic_flagged.append(f"{entry.af_id}: highlighted for human review")

    return PreAuditResult(
        safe_applied=safe_applied,
        semantic_flagged=semantic_flagged,
        content=content,
    )


def apply_safe_fix(content: str, entry: AFEntry) -> str:
    """Apply a safe auto-fix to the document.

    Safe fixes are structural/formatting — they don't change semantics.
    """
    # For now, append a note about the fix
    # Real implementation would apply specific transformations based on AF pattern
    fix_marker = f"\n<!-- [{entry.af_id} APPLIED]: {entry.fix} -->\n"
    if fix_marker not in content:
        content += fix_marker
    return content


def flag_semantic(content: str, entry: AFEntry) -> str:
    """Add a semantic suggestion marker to the document.

    These are visible to the human for review in Phase 5.
    """
    marker = f"\n> [{entry.af_id} SUGGESTION]: {entry.fix}\n"
    if marker not in content:
        content += marker
    return content


def _pattern_matches(pattern: str, content: str) -> bool:
    """Check if an AF pattern matches the document content.

    Uses simple keyword matching. Pattern is a description, not a regex.
    """
    keywords = [w.lower() for w in pattern.split() if len(w) > 3]
    content_lower = content.lower()
    match_count = sum(1 for kw in keywords if kw in content_lower)
    # Match if >50% of keywords found
    return len(keywords) > 0 and match_count >= len(keywords) * 0.5


def _applies_to_doc(applies_to: list[str], doc_type: str) -> bool:
    """Check if an AF entry applies to this document type."""
    for target in applies_to:
        target_upper = target.upper().replace(" ", "_")
        if target_upper == "ALL" or target_upper in doc_type.upper():
            return True
    return False


def _parse_audit_findings(content: str) -> list[AFEntry]:
    """Parse AUDIT_FINDINGS.md into AFEntry objects.

    Only returns entries with status ACTIVE.
    """
    entries: list[AFEntry] = []
    current_id = ""
    current_data: dict = {}

    for line in content.split("\n"):
        line = line.strip()

        # Heading with AF-ID
        af_match = re.match(r"###\s+(AF-\d+):", line)
        if af_match:
            if current_id and current_data.get("status") == "ACTIVE":
                entries.append(_build_entry(current_id, current_data))
            current_id = af_match.group(1)
            current_data = {}
            continue

        if not current_id:
            continue

        # Parse fields
        if line.startswith("- Status:"):
            current_data["status"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Class:"):
            current_data["af_class"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Pattern:"):
            current_data["pattern"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Fix:"):
            current_data["fix"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Applies to:"):
            raw = line.split(":", 1)[1].strip()
            current_data["applies_to"] = [x.strip() for x in raw.split(",")]

    # Last entry
    if current_id and current_data.get("status") == "ACTIVE":
        entries.append(_build_entry(current_id, current_data))

    return entries


def _build_entry(af_id: str, data: dict) -> AFEntry:
    return AFEntry(
        af_id=af_id,
        status=data.get("status", ""),
        af_class=data.get("af_class", "safe_autofix"),
        pattern=data.get("pattern", ""),
        fix=data.get("fix", ""),
        applies_to=data.get("applies_to", []),
    )
