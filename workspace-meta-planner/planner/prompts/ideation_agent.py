"""Prompt templates for ideation agents (Phase 1.5).

Two models suggest features/improvements. Primary triages.
See spec.md §3 (Phase 1.5).
"""


def ideation_prompt(doc_type: str, intake_summary: str) -> str:
    """Build prompt for an ideation agent (GPT or Gemini)."""
    return (
        f"You are reviewing a {doc_type} concept that a human has described. "
        f"Your job is to suggest features, improvements, or considerations the human "
        f"may have missed.\n\n"
        f"Rules:\n"
        f"- Suggest 3-5 concrete, actionable items\n"
        f"- Each suggestion must be specific (not 'consider scalability' but "
        f"'add connection pooling for PostgreSQL with max 20 connections')\n"
        f"- Focus on what's MISSING, not what's already covered\n"
        f"- Consider: edge cases, failure modes, cost implications, UX gaps\n"
        f"- Do NOT suggest enterprise features for a solo-dev project\n\n"
        f"Here is what the human described:\n\n{intake_summary}\n\n"
        f"Respond with a numbered list of suggestions. For each, include:\n"
        f"1. The feature/improvement\n"
        f"2. Why it matters\n"
        f"3. Rough complexity (low/medium/high)"
    )


def triage_prompt(doc_type: str, gpt_suggestions: str, gemini_suggestions: str) -> str:
    """Build prompt for the triage agent (Opus) to filter ideation results."""
    return (
        f"Two models suggested improvements for a {doc_type}. "
        f"Review both sets and produce a unified recommendation.\n\n"
        f"GPT-5.4 suggestions:\n{gpt_suggestions}\n\n"
        f"Gemini 3.1 Pro suggestions:\n{gemini_suggestions}\n\n"
        f"For each suggestion:\n"
        f"- RECOMMEND if it adds clear value and is feasible\n"
        f"- SKIP if it's enterprise overhead, already covered, or too complex for scope\n"
        f"- Merge duplicates from both models\n\n"
        f"Output format:\n"
        f"RECOMMENDED:\n"
        f"1. [suggestion] — [your assessment]\n"
        f"SKIPPED:\n"
        f"1. [suggestion] — [reason to skip]"
    )
