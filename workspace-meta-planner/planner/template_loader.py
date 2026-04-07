"""Template loader — loads SDD templates and returns section structure.

Loads templates from the sdd-system repo (or local copy).
See spec.md §2 (Output), sdd-system/templates/.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default template directory (sdd-system repo in openclaw-config)
DEFAULT_TEMPLATE_DIR = Path.home() / ".openclaw" / "docs"

# Template type → filename mapping
TEMPLATE_FILES = {
    "PROJECT_FOUNDATION": "PROJECT_FOUNDATION.md",
    "CONSTITUTION": "CONSTITUTION.md",
    "DATA_MODEL": "DATA_MODEL.md",
    "INTEGRATIONS": "INTEGRATIONS.md",
    "LESSONS_LEARNED": "LESSONS_LEARNED.md",
    "MODULE_SPEC": "MODULE_SPEC.md",
    "WORKFLOW_SPEC": "WORKFLOW_SPEC.md",
}

# Section heading regex
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


class TemplateSection:
    """A section within an SDD template."""

    def __init__(self, level: int, title: str, content: str = "") -> None:
        self.level = level
        self.title = title
        self.content = content

    def __repr__(self) -> str:
        return f"TemplateSection(level={self.level}, title='{self.title}')"


def load_template(
    doc_type: str,
    template_dir: Optional[str] = None,
) -> list[TemplateSection]:
    """Load an SDD template and return its section structure.

    Args:
        doc_type: Template type (e.g., "MODULE_SPEC", "WORKFLOW_SPEC").
        template_dir: Override for template directory path.

    Returns:
        Ordered list of TemplateSection objects.

    Raises:
        ValueError: If doc_type is not a known template type.
        FileNotFoundError: If template file doesn't exist.
    """
    if doc_type not in TEMPLATE_FILES:
        raise ValueError(
            f"Unknown template type: '{doc_type}'. "
            f"Known types: {list(TEMPLATE_FILES.keys())}"
        )

    tpl_dir = Path(template_dir) if template_dir else DEFAULT_TEMPLATE_DIR
    tpl_path = tpl_dir / TEMPLATE_FILES[doc_type]

    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tpl_path}")

    content = tpl_path.read_text(encoding="utf-8")
    return extract_sections(content)


def extract_sections(content: str) -> list[TemplateSection]:
    """Extract ordered sections from markdown content.

    Returns:
        List of TemplateSection with level, title, and content.
    """
    sections: list[TemplateSection] = []
    headings = list(_HEADING_RE.finditer(content))

    for i, match in enumerate(headings):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()

        # Content goes until next heading of same or higher level
        end = len(content)
        for j in range(i + 1, len(headings)):
            next_level = len(headings[j].group(1))
            if next_level <= level:
                end = headings[j].start()
                break

        section_content = content[start:end].strip()
        sections.append(TemplateSection(level, title, section_content))

    return sections


def get_section_titles(doc_type: str, template_dir: Optional[str] = None) -> list[str]:
    """Get just the section titles for a template type.

    Convenience function for intake interviewer to know which sections to ask about.
    """
    sections = load_template(doc_type, template_dir)
    return [s.title for s in sections]


def init_audit_findings(project_root: str) -> str:
    """Initialize an empty AUDIT_FINDINGS.md if it doesn't exist.

    Returns:
        Path to the AUDIT_FINDINGS.md file.
    """
    af_path = Path(project_root) / "docs" / "AUDIT_FINDINGS.md"
    if not af_path.exists():
        af_path.parent.mkdir(parents=True, exist_ok=True)
        af_path.write_text(
            "# AUDIT_FINDINGS.md\n\n"
            "## Active Patterns\n\n"
            "(No active patterns yet.)\n\n"
            "## Deprecated Patterns\n\n"
            "## Archived Patterns\n",
            encoding="utf-8",
        )
        logger.info(f"Initialized empty AUDIT_FINDINGS.md at {af_path}")
    return str(af_path)
