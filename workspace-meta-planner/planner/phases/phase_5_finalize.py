"""Phase 5: Finalize — apply fixes, present to human for approval.

Human receives inline summary (key changes, AF markers, cost) + .md file.
AF markers visible in document for review, removed from final approved version.
See spec.md §3 (Phase 5), spec.md §8 (document approval template).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

AF_MARKER_RE = re.compile(r"\n>\s*\[AF-\d+\s+SUGGESTION\]:.*\n", re.IGNORECASE)
AF_APPLIED_RE = re.compile(r"\n<!--\s*\[AF-\d+\s+APPLIED\]:.*-->\n", re.IGNORECASE)


@dataclass
class FinalizeResult:
    """Result of the finalize phase."""
    content: str
    clean_content: str  # AF markers removed (for final approved version)
    summary: str
    af_markers: list[str] = field(default_factory=list)
    changes_description: str = ""
    doc_cost: float = 0.0
    total_cost: float = 0.0


def apply_fixes(
    doc_content: str,
    audit_fixes: list[dict],
    lessons_fixes: list[dict],
) -> str:
    """Apply fixes from audit and lessons check to the document.

    Args:
        doc_content: Current document content.
        audit_fixes: List of {section, fix_text} from triage.
        lessons_fixes: List of {lesson_id, fix_text} from lessons check.

    Returns:
        Updated document content with fixes applied.
    """
    content = doc_content

    for fix in audit_fixes:
        section = fix.get("section", "")
        fix_text = fix.get("fix_text", "")
        if section and fix_text:
            content = _apply_section_fix(content, section, fix_text)

    for fix in lessons_fixes:
        fix_text = fix.get("fix_text", "")
        if fix_text:
            content += f"\n\n<!-- Lessons fix ({fix.get('lesson_id', '')}): {fix_text} -->\n"

    return content


def present_for_approval(
    doc_content: str,
    document_name: str,
    changes_description: str,
    doc_cost: float,
    total_cost: float,
    audit_resolved_count: int = 0,
) -> FinalizeResult:
    """Prepare the document for human approval.

    Args:
        doc_content: Document with all fixes applied (AF markers still visible).
        document_name: Name of the document.
        changes_description: Summary of what changed since last draft.
        doc_cost: Cost for this document so far.
        total_cost: Total run cost so far.
        audit_resolved_count: Number of audit findings resolved.

    Returns:
        FinalizeResult with content, clean content, and summary.
    """
    # Extract AF markers present
    af_markers = _extract_af_markers(doc_content)

    # Build clean version (AF markers removed)
    clean = remove_af_markers(doc_content)

    # Build inline summary
    af_str = ", ".join(af_markers) if af_markers else "none"
    summary = (
        f"📄 {document_name} ready for review\n\n"
        f"Key changes:\n- {changes_description}\n"
        f"- AF markers applied: {af_str}\n"
        f"- Audit findings resolved: {audit_resolved_count}\n\n"
        f"Cost for this document: ${doc_cost:.2f} | Total: ${total_cost:.2f}\n\n"
        f"✅ Approve | 🔄 Another round | ❌ Start over"
    )

    return FinalizeResult(
        content=doc_content,
        clean_content=clean,
        summary=summary,
        af_markers=af_markers,
        changes_description=changes_description,
        doc_cost=doc_cost,
        total_cost=total_cost,
    )


def remove_af_markers(content: str) -> str:
    """Remove all AF markers from document (for final approved version)."""
    content = AF_MARKER_RE.sub("\n", content)
    content = AF_APPLIED_RE.sub("\n", content)
    # Clean up multiple blank lines
    while "\n\n\n" in content:
        content = content.replace("\n\n\n", "\n\n")
    return content.strip() + "\n"


def _extract_af_markers(content: str) -> list[str]:
    """Extract AF-XXX IDs from markers in the document."""
    markers = set()
    for match in re.finditer(r"\[AF-(\d+)\s+(?:SUGGESTION|APPLIED)\]", content):
        markers.add(f"AF-{match.group(1)}")
    return sorted(markers)


def _apply_section_fix(content: str, section_heading: str, fix_text: str) -> str:
    """Apply a fix to a specific section of the document."""
    pattern = re.compile(
        rf"(^##\s+.*{re.escape(section_heading)}.*$)",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(content)
    if match:
        insert_pos = match.end()
        content = content[:insert_pos] + f"\n\n{fix_text}" + content[insert_pos:]
    return content
