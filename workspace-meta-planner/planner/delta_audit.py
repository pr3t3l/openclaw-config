"""Delta-audit — classify changes and apply appropriate re-validation.

After human fixes criticals, determines if minor/architecture/full re-audit needed.
See spec.md §4 (delta-audit rule + conditional second round).
"""

import difflib
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Change taxonomy
WORDING_ONLY = "WORDING_ONLY"           # Opus sanity check (1 call)
LOCAL_LOGIC = "LOCAL_LOGIC"             # 1 auditor on affected section
ENTITY_API_RULE_CHANGE = "ENTITY_API_RULE_CHANGE"  # 1 auditor + cross-doc flag
CROSS_DOC_EFFECT = "CROSS_DOC_EFFECT"   # 1 auditor + mandatory cross-doc re-validation


@dataclass
class ChangeClassification:
    """Classification of a document change."""
    category: str  # One of the taxonomy constants
    change_ratio: float  # 0.0-1.0 — fraction of document changed
    affected_sections: list[str]
    requires_cross_doc: bool = False
    description: str = ""


@dataclass
class DeltaAuditResult:
    """Result of a delta-audit."""
    classification: ChangeClassification
    audit_response: Optional[str] = None
    passed: bool = True
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


def classify_change(original: str, modified: str) -> ChangeClassification:
    """Classify the type of change between original and modified document.

    Args:
        original: Original document content.
        modified: Modified document content.

    Returns:
        ChangeClassification with category and details.
    """
    ratio = _compute_change_ratio(original, modified)
    affected = _find_affected_sections(original, modified)
    diff_text = _get_diff_text(original, modified)
    diff_lower = diff_text.lower()

    # Check for entity/API/rule changes
    has_entity_change = any(kw in diff_lower for kw in [
        "api", "endpoint", "schema", "table", "entity", "model",
        "rule", "constraint", "enum", "state machine",
    ])

    # Check for cross-doc references in changes
    has_cross_doc = any(kw in diff_lower for kw in [
        "constitution", "data_model", "integrations", "foundation",
        "see ", "§", "cross-doc", "references",
    ])

    if has_cross_doc and has_entity_change:
        category = CROSS_DOC_EFFECT
    elif has_entity_change:
        category = ENTITY_API_RULE_CHANGE
    elif ratio > 0.1:
        category = LOCAL_LOGIC
    else:
        category = WORDING_ONLY

    return ChangeClassification(
        category=category,
        change_ratio=ratio,
        affected_sections=affected,
        requires_cross_doc=category in (ENTITY_API_RULE_CHANGE, CROSS_DOC_EFFECT),
        description=f"{category}: {len(affected)} sections affected, {ratio:.0%} changed",
    )


def run_delta(
    original: str,
    modified: str,
    gateway: Any,
    doc_type: str = "",
    phase: str = "3",
    document: Optional[str] = None,
) -> DeltaAuditResult:
    """Run a delta-audit based on change classification.

    - WORDING_ONLY → Opus sanity check (1 call)
    - LOCAL_LOGIC → 1 auditor re-audits affected section
    - ENTITY_API_RULE_CHANGE → 1 auditor + flag for cross-doc
    - CROSS_DOC_EFFECT → 1 auditor + mandatory cross-doc

    Args:
        original: Original document.
        modified: Modified document.
        gateway: ModelGateway instance.
        doc_type: Document type.
        phase: Phase for cost tracking.
        document: Document name for cost tracking.

    Returns:
        DeltaAuditResult with classification and audit response.
    """
    classification = classify_change(original, modified)
    diff_text = _get_diff_text(original, modified)

    prompt = (
        f"A {doc_type} document was modified after audit. "
        f"Review ONLY the changes and confirm they are correct.\n\n"
        f"Change classification: {classification.category}\n"
        f"Affected sections: {', '.join(classification.affected_sections) or 'minor edits'}\n\n"
        f"Diff:\n{diff_text[:4000]}\n\n"
        f"Are these changes correct? Flag any new issues introduced."
    )

    if classification.category == WORDING_ONLY:
        role = "primary"  # Opus sanity check
    else:
        role = "auditor_gpt"  # 1 auditor

    response = gateway.call_model(
        role=role,
        prompt=prompt,
        phase=phase,
        document=document,
    )

    return DeltaAuditResult(
        classification=classification,
        audit_response=response["content"],
        passed="no new issues" in response["content"].lower() or "correct" in response["content"].lower(),
    )


def should_full_reaudit(
    original: str,
    modified: str,
    doc_type: str = "",
    human_requested: bool = False,
) -> bool:
    """Determine if a full 4-call re-audit is needed.

    Full re-audit only if:
    - Document changed >30%
    - Human explicitly requests it
    - Document is WORKFLOW_SPEC (high complexity)

    Args:
        original: Original document.
        modified: Modified document.
        doc_type: Document type.
        human_requested: Whether human explicitly asked for full re-audit.

    Returns:
        True if full re-audit recommended.
    """
    if human_requested:
        return True

    ratio = _compute_change_ratio(original, modified)
    if ratio > 0.30:
        return True

    if doc_type in ("WORKFLOW_SPEC",):
        # Only for first audit — after corrections, 1 round is standard
        # This returns True only for initial complexity consideration
        return False

    return False


def _compute_change_ratio(original: str, modified: str) -> float:
    """Compute the fraction of lines changed."""
    orig_lines = original.strip().split("\n")
    mod_lines = modified.strip().split("\n")

    if not orig_lines:
        return 1.0 if mod_lines else 0.0

    matcher = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    return 1.0 - matcher.ratio()


def _find_affected_sections(original: str, modified: str) -> list[str]:
    """Find which sections were modified."""
    import re
    heading_re = re.compile(r"^##\s+(.+)$", re.MULTILINE)

    orig_sections = {m.group(1).strip() for m in heading_re.finditer(original)}
    mod_sections = {m.group(1).strip() for m in heading_re.finditer(modified)}

    # Sections added or removed
    changed = orig_sections.symmetric_difference(mod_sections)

    # Sections with changed content
    orig_parts = _split_by_sections(original)
    mod_parts = _split_by_sections(modified)

    for section in orig_sections & mod_sections:
        if orig_parts.get(section, "") != mod_parts.get(section, ""):
            changed.add(section)

    return sorted(changed)


def _split_by_sections(content: str) -> dict[str, str]:
    """Split content by ## headings."""
    import re
    sections = {}
    parts = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    for part in parts:
        match = re.match(r"^## (.+)$", part, re.MULTILINE)
        if match:
            sections[match.group(1).strip()] = part
    return sections


def _get_diff_text(original: str, modified: str) -> str:
    """Get unified diff between two documents."""
    orig_lines = original.strip().split("\n")
    mod_lines = modified.strip().split("\n")
    diff = difflib.unified_diff(orig_lines, mod_lines, lineterm="", n=2)
    return "\n".join(diff)
