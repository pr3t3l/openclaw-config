"""Telegram message formatter — templates for all message types.

Handles 4096 char limit. Every message includes [RUN-ID] [DOC] [PHASE] prefix.
See spec.md §8 (Conversation Design), spec.md §7.3 (Telegram Interface Rules).
"""

from typing import Optional

TELEGRAM_CHAR_LIMIT = 4096
FILE_THRESHOLD = 3500  # Send as file if message exceeds this


def _prefix(run_id: str, doc: Optional[str] = None, phase: Optional[str] = None) -> str:
    """Build the standard [RUN-ID] [DOC] [PHASE] prefix."""
    parts = [f"[{run_id}]"]
    if doc:
        parts.append(f"[{doc}]")
    if phase:
        parts.append(f"[Phase {phase}]")
    return " ".join(parts)


def should_send_as_file(text: str) -> bool:
    """Check if text exceeds the threshold for inline delivery."""
    return len(text) > FILE_THRESHOLD


def truncate_for_telegram(text: str, suffix: str = "\n\n_(truncated — full content in file)_") -> str:
    """Truncate text to fit Telegram's 4096 char limit."""
    if len(text) <= TELEGRAM_CHAR_LIMIT:
        return text
    return text[: TELEGRAM_CHAR_LIMIT - len(suffix)] + suffix


def intake_start(
    run_id: str,
    mode: str,
    doc_type: str,
    doc_list: list[str],
    first_question: str,
) -> str:
    """Format the intake start message. Spec §8 template."""
    prefix = _prefix(run_id)
    docs = "\n".join(f"  - {d}" for d in doc_list)
    return (
        f"📋 Starting SDD Planner {prefix}\n\n"
        f"I detected this is a {mode}.\n"
        f"Document type: {doc_type} — confirmed by you.\n"
        f"Documents to produce:\n{docs}\n\n"
        f"Let's start with {doc_list[0] if doc_list else 'the first document'}. "
        f"I'll ask you questions section by section.\n\n"
        f"First question: {first_question}"
    )


def section_complete(
    run_id: str,
    doc: str,
    section: str,
    summary: str,
) -> str:
    """Format section completion confirmation. Spec §8 template."""
    prefix = _prefix(run_id, doc)
    return (
        f"✅ {prefix} Section \"{section}\" captured:\n\n"
        f"{summary}\n\n"
        f"Is this correct? (yes / needs changes)"
    )


def ideation_results(
    run_id: str,
    doc: str,
    gpt_suggestions: list[dict],
    gemini_suggestions: list[dict],
    recommendations: list[int],
) -> str:
    """Format ideation results. Spec §8 template."""
    prefix = _prefix(run_id, doc, "1.5")
    lines = [f"💡 {prefix} Feature suggestions from 2 models:\n"]

    lines.append("*GPT-5.4 suggested:*")
    for i, s in enumerate(gpt_suggestions, 1):
        lines.append(f"{i}. {s.get('feature', '')} — My take: {s.get('assessment', '')}")

    lines.append("\n*Gemini 3.1 suggested:*")
    for i, s in enumerate(gemini_suggestions, 1):
        lines.append(f"{i}. {s.get('feature', '')} — My take: {s.get('assessment', '')}")

    if recommendations:
        rec_str = ", ".join(f"#{r}" for r in recommendations)
        lines.append(f"\nI recommend adding {rec_str}. Your call — accept/reject/modify each.")
    lines.append("Or skip ideation entirely for this document.")

    return "\n".join(lines)


def pre_audit_summary(
    run_id: str,
    doc: str,
    safe_count: int,
    semantic_count: int,
) -> str:
    """Format pre-audit check summary. Spec §8 template."""
    prefix = _prefix(run_id, doc, "2.5")
    return (
        f"🔧 {prefix} Pre-audit check:\n"
        f"- {safe_count} safe patterns auto-fixed (formatting/structure)\n"
        f"- {semantic_count} semantic suggestions highlighted with [AF-XXX] markers for your review\n\n"
        f"Sending to auditors now."
    )


def audit_summary(
    run_id: str,
    doc: str,
    results: dict,
    critical_items: list[dict],
    auto_fix_count: int,
    noise_count: int,
) -> str:
    """Format audit summary (no conflicts). Spec §8 template."""
    prefix = _prefix(run_id, doc, "3")
    lines = [
        f"🔍 {prefix} Audit complete\n",
        "4 audit calls completed:",
        f"- GPT-5.4 Technical: {results.get('gpt_tech', 0)} issues",
        f"- GPT-5.4 Architecture: {results.get('gpt_arch', 0)} issues",
        f"- Gemini 3.1 Technical: {results.get('gemini_tech', 0)} issues",
        f"- Gemini 3.1 Architecture: {results.get('gemini_arch', 0)} issues",
        f"\nAfter triage — {len(critical_items)} need your input:\n",
    ]

    for i, item in enumerate(critical_items, 1):
        lines.append(f"{i}. [{item.get('severity', 'CRITICAL')}]: {item.get('description', '')}")
        if item.get('suggestion'):
            lines.append(f"   My suggestion: {item['suggestion']}")
        lines.append("   Your call: accept / modify / reject\n")

    lines.append(f"{auto_fix_count} minor issues I'll fix automatically.")
    lines.append(f"{noise_count} items were noise (not applicable).")

    return "\n".join(lines)


def audit_conflict(
    run_id: str,
    doc: str,
    gpt_argument: str,
    gemini_argument: str,
) -> str:
    """Format audit conflict message. Spec §8 template."""
    prefix = _prefix(run_id, doc, "3")
    return (
        f"⚠️ {prefix} Audit CONFLICT\n\n"
        f"The auditors DISAGREE on a critical finding:\n\n"
        f"*GPT-5.4 says:* \"{gpt_argument}\"\n\n"
        f"*Gemini 3.1 says:* \"{gemini_argument}\"\n\n"
        f"I'm not filtering this one — your call:\n"
        f"A) Side with GPT's concern\n"
        f"B) Side with Gemini's assessment\n"
        f"C) Something else: [tell me]"
    )


def document_approval(
    run_id: str,
    doc: str,
    changes_summary: str,
    af_markers: list[str],
    audit_resolved: int,
    doc_cost: float,
    total_cost: float,
) -> str:
    """Format document approval message. Spec §8 template."""
    prefix = _prefix(run_id, doc, "5")
    af_str = ", ".join(af_markers) if af_markers else "none"
    return (
        f"📄 {prefix} Ready for review\n\n"
        f"Key changes in this version:\n"
        f"- {changes_summary}\n"
        f"- AF markers applied: {af_str}\n"
        f"- Audit findings resolved: {audit_resolved}\n\n"
        f"📎 _{doc}_ attached — open for full review if needed\n\n"
        f"Cost for this document: ${doc_cost:.2f} | Total so far: ${total_cost:.2f}\n\n"
        f"✅ Approve | 🔄 Another round | ❌ Start over"
    )


def crossdoc_result(
    run_id: str,
    docs_checked: list[str],
    contradictions: list[dict],
) -> str:
    """Format cross-document validation result. Spec §8 template."""
    prefix = _prefix(run_id, phase="6.5")
    docs_str = ", ".join(docs_checked)
    lines = [f"🔗 {prefix} Cross-document validation complete\n"]
    lines.append(f"Checked: {docs_str}\n")

    if contradictions:
        lines.append(f"{len(contradictions)} contradictions found:\n")
        for i, c in enumerate(contradictions, 1):
            lines.append(f"{i}. {c.get('description', 'Unknown contradiction')}")
            if c.get("question"):
                lines.append(f"   → {c['question']}")
    else:
        lines.append("0 contradictions → ✅ Ready for plan generation.")

    return "\n".join(lines)


def run_complete(
    run_id: str,
    total_cost: float,
    cost_by_model: dict,
    time_minutes: Optional[float] = None,
) -> str:
    """Format run completion message. Spec §8 template."""
    model_breakdown = " | ".join(f"{k} ${v:.2f}" for k, v in cost_by_model.items())
    time_str = f"\nYour time: ~{time_minutes:.0f} minutes" if time_minutes else ""
    return (
        f"🎉 [{run_id}] SDD Planning complete!\n\n"
        f"📎 All documents attached.\n\n"
        f"Total cost: ${total_cost:.2f} ({model_breakdown})"
        f"{time_str}\n\n"
        f"Next step: Pass tasks.md to Claude Code:\n"
        f"\"Read docs/specs/[name]/spec.md and plan.md. Start with TASK-001.\""
    )


def cost_alert(run_id: str, total: float, threshold: float) -> str:
    """Format cost alert message."""
    prefix = _prefix(run_id)
    return (
        f"💰 {prefix} Cost Alert\n\n"
        f"Total cost: ${total:.2f} (threshold: ${threshold:.2f})\n"
        f"Continue? (yes / stop)"
    )


def progress_update(run_id: str, doc: str, phase: str, message: str) -> str:
    """Format a generic progress update."""
    prefix = _prefix(run_id, doc, phase)
    return f"{prefix} {message}"
