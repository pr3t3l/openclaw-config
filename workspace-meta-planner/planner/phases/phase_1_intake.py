"""Phase 1: Intake — section-by-section Q&A with Opus.

Max 5 rounds per section, then proposes Assumed Default.
Uses Decision Logs from previous docs (not raw history).
See spec.md §3 (Phase 1), spec.md §8 (Conversation Design).
"""

import logging
from typing import Any, Optional

from planner.prompts import intake_interviewer as prompts
from planner.template_loader import TemplateSection

logger = logging.getLogger(__name__)

MAX_ROUNDS_PER_SECTION = 5


class IntakeSession:
    """Manages the intake interview for a single document.

    Tracks sections, rounds, and captured answers.
    Designed for async Telegram interaction (non-blocking).
    """

    def __init__(
        self,
        doc_type: str,
        sections: list[TemplateSection],
        decision_logs: Optional[dict[str, str]] = None,
        project_context: str = "",
    ) -> None:
        self.doc_type = doc_type
        self.sections = sections
        self.decision_logs = decision_logs or {}
        self.project_context = project_context

        self._current_section_idx = 0
        self._current_round = 0
        self._answers: dict[str, str] = {}
        self._completed_sections: list[str] = []
        self._assumptions: list[str] = []

    @property
    def current_section(self) -> Optional[TemplateSection]:
        if self._current_section_idx < len(self.sections):
            return self.sections[self._current_section_idx]
        return None

    @property
    def is_complete(self) -> bool:
        return self._current_section_idx >= len(self.sections)

    @property
    def sections_completed(self) -> list[str]:
        return list(self._completed_sections)

    @property
    def answers(self) -> dict[str, str]:
        return dict(self._answers)

    @property
    def assumptions(self) -> list[str]:
        return list(self._assumptions)

    @property
    def progress(self) -> str:
        total = len(self.sections)
        done = len(self._completed_sections)
        return f"{done}/{total} sections"

    def get_next_prompt(self, gateway: Any = None) -> dict:
        """Get the next question/action for the human.

        Returns:
            Dict with: action, section, prompt, round_num
            Actions: "question", "confirm_section", "assumed_default", "complete"
        """
        if self.is_complete:
            return {
                "action": "complete",
                "message": "All sections captured. Ready for review.",
                "answers": self._answers,
            }

        section = self.current_section
        self._current_round += 1

        if self._current_round > MAX_ROUNDS_PER_SECTION:
            return self._propose_assumed_default(section)

        # Build context from decision logs
        ctx = self._build_context()

        if self._current_round == 1:
            system = prompts.system_prompt(self.doc_type, ctx)
            question = prompts.section_question(
                section.title, section.content, self._current_round
            )
        else:
            system = prompts.system_prompt(self.doc_type, ctx)
            question = prompts.section_question(
                section.title, section.content, self._current_round
            )

        return {
            "action": "question",
            "section": section.title,
            "round_num": self._current_round,
            "system_prompt": system,
            "user_prompt": question,
        }

    def record_answer(self, answer: str) -> dict:
        """Record the human's answer for the current section.

        Args:
            answer: The human's response.

        Returns:
            Dict with: action ("confirm_section" or next question info)
        """
        section = self.current_section
        if section is None:
            return {"action": "complete", "message": "Already complete"}

        # Store answer
        self._answers[section.title] = answer

        return {
            "action": "confirm_section",
            "section": section.title,
            "summary": answer,
            "message": f"Section \"{section.title}\" captured. Is this correct?",
        }

    def confirm_section(self, confirmed: bool) -> dict:
        """Confirm or reject the current section's answer.

        Args:
            confirmed: True if human approves the captured answer.

        Returns:
            Next action dict.
        """
        section = self.current_section
        if section is None:
            return {"action": "complete", "message": "Already complete"}

        if confirmed:
            self._completed_sections.append(section.title)
            self._current_section_idx += 1
            self._current_round = 0
            logger.info(f"Section '{section.title}' confirmed ({self.progress})")

            if self.is_complete:
                return {
                    "action": "complete",
                    "message": "All sections captured. Ready for review.",
                    "answers": self._answers,
                }

            return self.get_next_prompt()
        else:
            # Human wants changes — reset round for this section
            self._current_round = 0
            return self.get_next_prompt()

    def propose_assumed_default(self) -> dict:
        """Propose an assumed default for the current section."""
        return self._propose_assumed_default(self.current_section)

    def accept_assumption(self, assumption_text: str) -> dict:
        """Accept an assumed default for the current section.

        Args:
            assumption_text: The proposed default text.

        Returns:
            Next action dict.
        """
        section = self.current_section
        if section is None:
            return {"action": "complete", "message": "Already complete"}

        tagged = f"[ASSUMPTION — validate during implementation] {assumption_text}"
        self._answers[section.title] = tagged
        self._assumptions.append(f"{section.title}: {assumption_text}")
        self._completed_sections.append(section.title)
        self._current_section_idx += 1
        self._current_round = 0

        logger.info(f"Assumed default accepted for '{section.title}' ({self.progress})")

        if self.is_complete:
            return {
                "action": "complete",
                "message": "All sections captured. Ready for review.",
                "answers": self._answers,
            }

        return self.get_next_prompt()

    def _propose_assumed_default(self, section: Optional[TemplateSection]) -> dict:
        """Build an assumed default proposal."""
        if section is None:
            return {"action": "complete", "message": "Already complete"}

        ctx = self._build_context()
        prompt = prompts.assumed_default_prompt(section.title, ctx)

        return {
            "action": "assumed_default",
            "section": section.title,
            "system_prompt": prompts.system_prompt(self.doc_type, ctx),
            "user_prompt": prompt,
            "message": (
                f"After 5 rounds on \"{section.title}\", proposing an Assumed Default. "
                f"It will be marked [ASSUMPTION — validate during implementation]."
            ),
        }

    def _build_context(self) -> str:
        """Build context string from decision logs and previous answers."""
        parts = []
        if self.decision_logs:
            parts.append("Previous document decisions:")
            for doc, log in self.decision_logs.items():
                parts.append(f"  {doc}: {log[:200]}...")
        if self._answers:
            parts.append("\nAlready captured for this document:")
            for title, answer in self._answers.items():
                parts.append(f"  {title}: {answer[:100]}...")
        if self.project_context:
            parts.append(f"\nProject context: {self.project_context[:300]}")
        return "\n".join(parts) if parts else ""
