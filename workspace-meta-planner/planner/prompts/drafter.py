"""Prompt templates for the Document Drafter (Phase 2).

See spec.md §3 (Phase 2).
"""


def system_prompt(doc_type: str, constitution_rules: str = "") -> str:
    """Build system prompt for the drafter."""
    rules = f"\n\nConstitution rules to follow:\n{constitution_rules}" if constitution_rules else ""
    return (
        f"You are an SDD document drafter. You produce complete, production-ready "
        f"{doc_type} documents following the Spec-Driven Development methodology.\n\n"
        f"Rules:\n"
        f"- Fill EVERY section completely — no empty sections\n"
        f"- No stubs: TBD, TODO, placeholder, some_type → FORBIDDEN\n"
        f"- [ASSUMPTION — ...] markers are allowed for deferred items\n"
        f"- Be specific and concrete — not 'consider using a database' but 'PostgreSQL 16 because...'\n"
        f"- Tables must have real data, not example_value\n"
        f"- Output valid Markdown\n"
        f"- Only include sections that are relevant to THIS project\n"
        f"- Do NOT generate 'Not applicable' or 'N/A' sections — if a section doesn't apply, omit it entirely\n"
        f"- Use the project's actual name in headers, not the template platform name"
        f"{rules}"
    )


def draft_prompt(
    doc_type: str,
    template_content: str,
    intake_answers: dict[str, str],
    ideation_accepted: list[dict],
) -> str:
    """Build the drafting prompt."""
    answers_text = "\n\n".join(
        f"### {section}\n{answer}" for section, answer in intake_answers.items()
    )

    ideation_text = ""
    if ideation_accepted:
        items = "\n".join(f"- {s.get('feature', '')}" for s in ideation_accepted)
        ideation_text = f"\n\nAccepted ideation suggestions to incorporate:\n{items}"

    project_name = intake_answers.get("Project Name", "")
    project_line = f"\nProject name: {project_name}\n" if project_name else ""

    return (
        f"Draft a complete {doc_type} document based on the following inputs.\n\n"
        f"{project_line}"
        f"Template structure to follow:\n{template_content}\n\n"
        f"Captured answers from intake:\n{answers_text}"
        f"{ideation_text}\n\n"
        f"Produce the complete document in Markdown. Fill every section. "
        f"No stubs, no placeholders. "
        f"Only include sections relevant to this project — omit any section "
        f"that would just say 'Not applicable' or 'N/A'."
    )
