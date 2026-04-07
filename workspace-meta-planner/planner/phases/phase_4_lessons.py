"""Phase 4: Lessons Check — compare corrected document against LESSONS_LEARNED.md.

Runs against post-correction document (after delta-audit, NOT pre-fix version).
Opus checks doc against relevant LL entries. 0 violations required for gate G4.
See spec.md §3 (Phase 4).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LessonViolation:
    """A violation of a lesson learned entry."""
    lesson_id: str
    description: str
    section: str
    suggestion: str


@dataclass
class LessonRecommendation:
    """A recommendation based on lessons learned (not a violation)."""
    lesson_id: str
    description: str
    reason: str


@dataclass
class LessonsCheckResult:
    """Result of checking document against LESSONS_LEARNED.md."""
    violations: list[LessonViolation] = field(default_factory=list)
    recommendations: list[LessonRecommendation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    @property
    def violation_count(self) -> int:
        return len(self.violations)


def load_lessons(project_root: str) -> str:
    """Load LESSONS_LEARNED.md content.

    Returns:
        Content string, or empty string if file doesn't exist.
    """
    ll_path = Path(project_root) / "docs" / "LESSONS_LEARNED.md"
    if not ll_path.exists():
        return ""
    return ll_path.read_text(encoding="utf-8")


def check_lessons(
    doc_content: str,
    doc_type: str,
    lessons_content: str,
    gateway: Any,
    phase: str = "4",
    document: Optional[str] = None,
) -> LessonsCheckResult:
    """Check a document against LESSONS_LEARNED.md for violations.

    Args:
        doc_content: The corrected document (post-audit fixes).
        doc_type: Document type.
        lessons_content: Full content of LESSONS_LEARNED.md.
        gateway: ModelGateway instance.
        phase: Phase for cost tracking.
        document: Document name for cost tracking.

    Returns:
        LessonsCheckResult with violations and recommendations.
    """
    if not lessons_content.strip():
        logger.info("No LESSONS_LEARNED.md content — skipping check")
        return LessonsCheckResult()

    prompt = (
        f"Compare the following {doc_type} document against the LESSONS_LEARNED entries below.\n\n"
        f"For each lesson that applies:\n"
        f"- If the document VIOLATES the lesson: report as VIOLATION with lesson ID, description, and fix\n"
        f"- If the lesson is relevant but not violated: report as RECOMMENDATION\n\n"
        f"Output format:\n"
        f"VIOLATIONS:\n"
        f"- LL-XXX: [what's wrong] → [how to fix]\n"
        f"RECOMMENDATIONS:\n"
        f"- LL-XXX: [why it applies]\n"
        f"NO VIOLATIONS if the document is clean.\n\n"
        f"LESSONS_LEARNED:\n{lessons_content[:6000]}\n\n"
        f"DOCUMENT TO CHECK:\n{doc_content[:6000]}"
    )

    response = gateway.call_model(
        role="primary",
        prompt=prompt,
        phase=phase,
        document=document,
    )

    return _parse_lessons_response(response["content"])


def _parse_lessons_response(content: str) -> LessonsCheckResult:
    """Parse the Opus response into violations and recommendations."""
    result = LessonsCheckResult()
    current_section = None

    for line in content.split("\n"):
        line = line.strip()
        upper = line.upper()

        if "VIOLATION" in upper and ":" in upper:
            current_section = "violations"
            continue
        elif "RECOMMENDATION" in upper and ":" in upper:
            current_section = "recommendations"
            continue
        elif "NO VIOLATION" in upper:
            return result  # Clean

        if not line or not line.startswith("-"):
            continue

        item = line.lstrip("- ").strip()

        if current_section == "violations":
            parts = item.split(":", 1)
            lesson_id = parts[0].strip() if parts else ""
            desc = parts[1].strip() if len(parts) > 1 else item
            suggestion = ""
            if "→" in desc:
                desc, suggestion = desc.split("→", 1)
                suggestion = suggestion.strip()
            result.violations.append(LessonViolation(
                lesson_id=lesson_id,
                description=desc.strip(),
                section="",
                suggestion=suggestion,
            ))

        elif current_section == "recommendations":
            parts = item.split(":", 1)
            lesson_id = parts[0].strip() if parts else ""
            reason = parts[1].strip() if len(parts) > 1 else item
            result.recommendations.append(LessonRecommendation(
                lesson_id=lesson_id,
                description=item,
                reason=reason,
            ))

    return result
