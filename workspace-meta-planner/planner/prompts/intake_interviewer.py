"""Prompt templates for the Intake Interviewer (Phase 1).

See spec.md §8 (Conversation Design).
"""


def system_prompt(doc_type: str, project_context: str = "") -> str:
    """Build the system prompt for the intake interviewer."""
    ctx = f"\n\nProject context:\n{project_context}" if project_context else ""
    return (
        f"You are an SDD Planner intake interviewer. You are helping a human create a "
        f"{doc_type} document following the Spec-Driven Development methodology.\n\n"
        f"Your job is to ask specific, concrete questions about each section of the template. "
        f"Do NOT ask vague questions like 'tell me about your project'. Instead ask targeted "
        f"questions like 'What problem does this solve for the end user?' or "
        f"'What database will you use and why?'\n\n"
        f"Rules:\n"
        f"- One section at a time\n"
        f"- Ask specific questions, not open-ended ones\n"
        f"- Summarize what you understood after each section\n"
        f"- If the human gives a vague answer, ask a follow-up with concrete options\n"
        f"- Max 5 rounds per section — then propose an Assumed Default\n"
        f"- Mark unclear items with [ASSUMPTION — validate during implementation]\n"
        f"- Never accept TBD, TODO, or placeholder as valid answers"
        f"{ctx}"
    )


def section_question(section_title: str, section_content: str, round_num: int) -> str:
    """Build a question prompt for a specific section."""
    if round_num == 1:
        return (
            f"Let's work on the section: **{section_title}**\n\n"
            f"Template guidance:\n{section_content}\n\n"
            f"Based on this template, what should go in this section for your project?"
        )
    return (
        f"Follow-up on section **{section_title}** (round {round_num}/5):\n\n"
        f"Can you provide more specific details? If you're unsure, I'll propose a default."
    )


def assumed_default_prompt(section_title: str, context: str) -> str:
    """Build a prompt to propose an Assumed Default after 5 rounds."""
    return (
        f"We've discussed section **{section_title}** for 5 rounds. "
        f"Based on what you've told me and the project context, here's my best-guess answer:\n\n"
        f"I'll mark it as [ASSUMPTION — validate during implementation] so it's "
        f"flagged for verification later.\n\n"
        f"Context so far: {context}\n\n"
        f"Please propose a concrete default for this section."
    )
