"""Structural document validator for SDD templates.

Catches stubs, TBDs, empty sections, and validates completeness.
Allows [ASSUMPTION — ...] as valid deferred content.
See spec.md §2 (Quality criteria), spec.md §8 (Principle 9 — Assumed Defaults).
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# Forbidden stub patterns (case-insensitive)
FORBIDDEN_PATTERNS = [
    r"\bTBD\b",
    r"\bTODO\s*:",  # Only "TODO:" not "Todo" (the word)
    r"\bTODO\b(?![\w])",  # Standalone TODO (case-sensitive below)
    r"\bplaceholder\b",
    r"\bsome_type\b",
    r"\bexample_value\b",
    r"\bFIXME\b",
    r"\bXXX\b",
]

# Case-sensitive patterns (TODO, TBD, FIXME, XXX are always uppercase)
# Case-insensitive only for: placeholder, some_type, example_value
_CASE_SENSITIVE_PATTERNS = [r"\bTBD\b", r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b"]
_CASE_INSENSITIVE_PATTERNS = [r"\bplaceholder\b", r"\bsome_type\b", r"\bexample_value\b"]

# Compiled forbidden regex
_FORBIDDEN_RE = re.compile(
    "|".join(FORBIDDEN_PATTERNS), re.IGNORECASE
)

# Assumption marker — this is ALLOWED as a valid deferred placeholder
ASSUMPTION_RE = re.compile(r"\[ASSUMPTION\s*[—–-]\s*.+?\]", re.IGNORECASE)

# Heading pattern for section detection
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class Violation:
    """A single validation violation."""
    line_number: int
    line_content: str
    pattern_matched: str
    severity: str = "ERROR"  # ERROR or WARNING


@dataclass
class ValidationResult:
    """Result of validating a document."""
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    empty_sections: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "WARNING")


def validate(
    doc_content: str,
    template_type: Optional[str] = None,
) -> ValidationResult:
    """Validate a document for structural completeness.

    Args:
        doc_content: Full markdown content of the document.
        template_type: Optional SDD template type for type-specific checks.

    Returns:
        ValidationResult with pass/fail and violation details.
    """
    violations: list[Violation] = []
    empty_sections: list[str] = []

    lines = doc_content.split("\n")

    # Check for forbidden stub patterns
    for i, line in enumerate(lines, start=1):
        # Skip if line contains an [ASSUMPTION] marker
        if ASSUMPTION_RE.search(line):
            continue
        # Skip comments
        if line.strip().startswith("<!--") or line.strip().startswith("-->"):
            continue
        # Check for forbidden patterns (case-sensitive for TBD/TODO/FIXME/XXX)
        for pattern in _CASE_SENSITIVE_PATTERNS:
            if re.search(pattern, line):
                violations.append(Violation(
                    line_number=i,
                    line_content=line.strip(),
                    pattern_matched=pattern.replace(r"\b", ""),
                    severity="ERROR",
                ))
        for pattern in _CASE_INSENSITIVE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append(Violation(
                    line_number=i,
                    line_content=line.strip(),
                    pattern_matched=pattern.replace(r"\b", ""),
                    severity="ERROR",
                ))

    # Check for empty sections
    sections = _extract_sections(doc_content)
    for section_name, section_content in sections.items():
        content = section_content.strip()
        if not content or content == "---":
            empty_sections.append(section_name)
            violations.append(Violation(
                line_number=0,
                line_content=f"Section '{section_name}' is empty",
                pattern_matched="empty_section",
                severity="ERROR",
            ))

    # Count assumptions (not violations, just stats)
    assumption_count = len(ASSUMPTION_RE.findall(doc_content))

    passed = all(v.severity != "ERROR" for v in violations)

    return ValidationResult(
        passed=passed,
        violations=violations,
        empty_sections=empty_sections,
        stats={
            "total_lines": len(lines),
            "total_sections": len(sections),
            "empty_sections": len(empty_sections),
            "assumptions": assumption_count,
            "errors": sum(1 for v in violations if v.severity == "ERROR"),
            "warnings": sum(1 for v in violations if v.severity == "WARNING"),
        },
    )


def _extract_sections(doc_content: str) -> dict[str, str]:
    """Extract sections from a markdown document by headings.

    Returns:
        Dict mapping section heading text to its content (text between this
        heading and the next heading of same or higher level).
    """
    sections: dict[str, str] = {}
    headings = list(HEADING_RE.finditer(doc_content))

    for i, match in enumerate(headings):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()

        # Find end: next heading of same or higher level
        end = len(doc_content)
        for j in range(i + 1, len(headings)):
            next_level = len(headings[j].group(1))
            if next_level <= level:
                end = headings[j].start()
                break

        content = doc_content[start:end].strip()
        sections[title] = content

    return sections
