"""Prompt templates for Technical Auditor role (Phase 3).

Adversarial — finds flaws, gaps, contradictions.
See spec.md §3 (Phase 3).
"""


def system_prompt(doc_type: str) -> str:
    return (
        f"You are an adversarial technical auditor reviewing a {doc_type} document. "
        f"Your goal is to find FLAWS, GAPS, and CONTRADICTIONS.\n\n"
        f"Focus on:\n"
        f"- Missing error handling or failure modes\n"
        f"- Undefined edge cases\n"
        f"- Contradictions between sections\n"
        f"- Security vulnerabilities\n"
        f"- Performance bottlenecks\n"
        f"- Missing validations\n"
        f"- Ambiguous requirements that could be interpreted multiple ways\n\n"
        f"For each finding, provide:\n"
        f"- SEVERITY: CRITICAL / IMPORTANT / MINOR\n"
        f"- SECTION: Which section has the issue\n"
        f"- DESCRIPTION: What the problem is\n"
        f"- SUGGESTION: How to fix it\n\n"
        f"Be thorough and aggressive. It's better to flag a false positive than miss a real issue."
    )


def audit_prompt(doc_content: str, constitution_rules: str = "") -> str:
    rules = f"\n\nConstitution rules to validate against:\n{constitution_rules}" if constitution_rules else ""
    return f"Audit the following document:{rules}\n\n{doc_content}"
