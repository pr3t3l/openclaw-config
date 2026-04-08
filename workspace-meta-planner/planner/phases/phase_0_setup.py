"""Phase 0: Setup — detect mode, load context, determine doc list.

Detects whether this is a new project, existing project, or monolith extraction.
Asks human MODULE or WORKFLOW. Loads existing project docs as context.
See spec.md §3 (Phase 0), spec.md §2 (Input modes A/B).
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# SDD document types and their standard filenames
FOUNDATION_DOCS = [
    "PROJECT_FOUNDATION.md",
    "CONSTITUTION.md",
    "DATA_MODEL.md",
    "INTEGRATIONS.md",
    "LESSONS_LEARNED.md",
]

CONTEXT_DOCS = FOUNDATION_DOCS + ["AUDIT_FINDINGS.md"]

# New project document order (spec §3: Document Processing Order)
NEW_PROJECT_DOC_ORDER = [
    "PROJECT_FOUNDATION.md",
    "CONSTITUTION.md",
    "DATA_MODEL.md",
    "INTEGRATIONS.md",
    "LESSONS_LEARNED.md",
    # spec.md added after these, type determined by human
]

# Existing project only needs spec + plan + tasks
EXISTING_PROJECT_DOC_ORDER = [
    # spec.md only, type determined by human
]


class SetupResult:
    """Result of Phase 0 setup."""

    def __init__(
        self,
        mode: str,
        doc_type: Optional[str],
        documents_pending: list[str],
        context_loaded: dict[str, str],
        has_attachments: bool = False,
    ) -> None:
        self.mode = mode  # "new_project", "existing_project", "monolith"
        self.doc_type = doc_type  # "MODULE_SPEC" or "WORKFLOW_SPEC" (None until human confirms)
        self.documents_pending = documents_pending
        self.context_loaded = context_loaded  # {doc_name: content}
        self.has_attachments = has_attachments


def detect_mode(project_root: str, has_attachments: bool = False) -> str:
    """Detect the planning mode based on project state.

    Args:
        project_root: Path to the project root.
        has_attachments: Whether user provided document attachments.

    Returns:
        One of: "new_project", "existing_project", "monolith"
    """
    if has_attachments:
        return "monolith"

    docs_dir = Path(project_root) / "docs"
    if not docs_dir.exists():
        return "new_project"

    # Check if foundation docs exist
    existing = [f.name for f in docs_dir.iterdir() if f.is_file() and f.suffix == ".md"]
    foundation_found = sum(1 for d in FOUNDATION_DOCS if d in existing)

    if foundation_found >= 3:
        return "existing_project"

    return "new_project"


def load_context(project_root: str) -> dict[str, str]:
    """Load existing SDD documents as context for the Planner.

    Returns:
        Dict mapping document name to its content.
        Only includes docs that exist and are non-empty.
    """
    context: dict[str, str] = {}
    docs_dir = Path(project_root) / "docs"

    if not docs_dir.exists():
        return context

    for doc_name in CONTEXT_DOCS:
        doc_path = docs_dir / doc_name
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8").strip()
            if content:
                context[doc_name] = content

    return context


def determine_doc_list(
    mode: str,
    doc_type: str,
    context_loaded: dict[str, str],
) -> list[str]:
    """Determine which documents need to be produced.

    Args:
        mode: Planning mode ("new_project", "existing_project", "monolith").
        doc_type: "MODULE_SPEC" or "WORKFLOW_SPEC".
        context_loaded: Already-loaded context docs.

    Returns:
        Ordered list of document names to produce.
    """
    spec_filename = f"{doc_type}.md"

    if mode == "new_project":
        docs = list(NEW_PROJECT_DOC_ORDER)
        docs.append(spec_filename)
        return docs

    if mode == "existing_project":
        return [spec_filename]

    if mode == "monolith":
        # Monolith: produce all docs, but skip ones that already exist with content
        docs = []
        for doc in NEW_PROJECT_DOC_ORDER:
            if doc not in context_loaded:
                docs.append(doc)
        docs.append(spec_filename)
        return docs

    return [spec_filename]


def run_phase_0(
    project_root: str,
    has_attachments: bool = False,
    doc_type: Optional[str] = None,
) -> SetupResult:
    """Execute Phase 0: detect mode, load context, determine doc list.

    Args:
        project_root: Absolute path to project root.
        has_attachments: Whether user provided files (Mode B).
        doc_type: "MODULE_SPEC" or "WORKFLOW_SPEC" (None if not yet confirmed).

    Returns:
        SetupResult with all Phase 0 outputs.
    """
    mode = detect_mode(project_root, has_attachments)
    context = load_context(project_root)

    documents_pending = []
    if doc_type:
        documents_pending = determine_doc_list(mode, doc_type, context)

    logger.info(
        f"Phase 0: mode={mode}, context_docs={len(context)}, "
        f"pending={len(documents_pending)}, doc_type={doc_type}"
    )

    return SetupResult(
        mode=mode,
        doc_type=doc_type,
        documents_pending=documents_pending,
        context_loaded=context,
        has_attachments=has_attachments,
    )
