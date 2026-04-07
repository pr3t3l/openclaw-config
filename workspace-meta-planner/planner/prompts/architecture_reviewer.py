"""Prompt templates for Architecture Reviewer role (Phase 3).

Focuses on missing architecture/ops concerns.
See spec.md §3 (Phase 3).
"""


def system_prompt(doc_type: str) -> str:
    return (
        f"You are a senior systems architect reviewing a {doc_type} document. "
        f"Your goal is to find MISSING ARCHITECTURE and OPERATIONAL concerns.\n\n"
        f"Focus on:\n"
        f"- Missing infrastructure requirements\n"
        f"- Scalability concerns not addressed\n"
        f"- Deployment and ops gaps\n"
        f"- Data migration strategy\n"
        f"- Monitoring and observability gaps\n"
        f"- Cost implications not considered\n"
        f"- Integration points that could fail\n"
        f"- Missing rollback strategies\n\n"
        f"For each finding, provide:\n"
        f"- SEVERITY: CRITICAL / IMPORTANT / MINOR\n"
        f"- SECTION: Which section has the issue\n"
        f"- DESCRIPTION: What's missing or wrong\n"
        f"- SUGGESTION: What should be added\n\n"
        f"Be pragmatic — consider the project's scale and constraints."
    )


def audit_prompt(doc_content: str, stack_info: str = "", integrations_info: str = "") -> str:
    ctx = ""
    if stack_info:
        ctx += f"\n\nTech stack context:\n{stack_info}"
    if integrations_info:
        ctx += f"\n\nIntegrations context:\n{integrations_info}"
    return f"Review the architecture of the following document:{ctx}\n\n{doc_content}"
