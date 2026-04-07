"""Phase 2: Draft — populate SDD template with intake + ideation.

Opus produces complete markdown following the template. Validates with document_validator.
See spec.md §3 (Phase 2).
"""

import logging
from typing import Any, Optional

from planner.prompts import drafter as prompts
from planner.validators.document_validator import validate as validate_doc

logger = logging.getLogger(__name__)


class DraftResult:
    """Result of the drafting phase."""

    def __init__(
        self,
        content: str,
        doc_type: str,
        validation_passed: bool,
        validation_errors: list[str],
        version: int = 1,
    ) -> None:
        self.content = content
        self.doc_type = doc_type
        self.validation_passed = validation_passed
        self.validation_errors = validation_errors
        self.version = version


def draft_document(
    doc_type: str,
    template_content: str,
    intake_answers: dict[str, str],
    gateway: Any,
    ideation_accepted: Optional[list[dict]] = None,
    constitution_rules: str = "",
    phase: str = "2",
    document: Optional[str] = None,
    max_retries: int = 1,
) -> DraftResult:
    """Draft a complete SDD document from intake answers and ideation.

    Args:
        doc_type: Template type (e.g., "WORKFLOW_SPEC").
        template_content: Raw template markdown for structure reference.
        intake_answers: Dict of section → answer from Phase 1.
        gateway: ModelGateway instance.
        ideation_accepted: Accepted ideation suggestions (or empty/None if skipped).
        constitution_rules: Constitution rules to include in context.
        phase: Phase identifier for cost tracking.
        document: Document name for cost tracking.
        max_retries: Number of re-draft attempts if validation fails.

    Returns:
        DraftResult with content and validation status.
    """
    accepted = ideation_accepted or []

    system = prompts.system_prompt(doc_type, constitution_rules)
    user_prompt = prompts.draft_prompt(doc_type, template_content, intake_answers, accepted)

    content = ""
    validation_passed = False
    validation_errors: list[str] = []

    for attempt in range(1 + max_retries):
        if attempt > 0:
            # Re-draft with error feedback
            user_prompt = (
                f"The previous draft had validation errors:\n"
                + "\n".join(f"- {e}" for e in validation_errors)
                + f"\n\nPlease fix these issues and produce a corrected version.\n\n"
                f"Previous draft:\n{content}"
            )

        response = gateway.call_model(
            role="primary",
            prompt=user_prompt,
            context=system,
            phase=phase,
            document=document,
        )
        content = response["content"]

        # Validate
        result = validate_doc(content, template_type=doc_type)

        if result.passed:
            validation_passed = True
            validation_errors = []
            logger.info(f"Draft validated on attempt {attempt + 1}")
            break
        else:
            validation_errors = [
                f"Line {v.line_number}: {v.pattern_matched} — {v.line_content}"
                for v in result.violations[:10]
            ]
            logger.warning(
                f"Draft validation failed (attempt {attempt + 1}): "
                f"{len(result.violations)} issues"
            )

    return DraftResult(
        content=content,
        doc_type=doc_type,
        validation_passed=validation_passed,
        validation_errors=validation_errors,
    )
