"""Decision Log builder — archive raw history, generate structured Decision Logs.

Decision Log: 500-word executive summary + Hard Decisions (key:value).
Replaces raw history in active context to save tokens.
See spec.md §7.2 (Conversation History Management).
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DecisionLog:
    """Structured Decision Log for a document."""
    document_name: str
    summary: str  # 500-word executive summary
    hard_decisions: dict[str, str] = field(default_factory=dict)


def archive_history(
    run_dir: str,
    document_name: str,
    conversation_history: list[dict],
) -> str:
    """Archive raw conversation history to history_archive/.

    Args:
        run_dir: Path to the run directory.
        document_name: Document being archived.
        conversation_history: Raw chat messages.

    Returns:
        Path to the archive file.
    """
    archive_dir = Path(run_dir) / "history_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    safe_name = document_name.replace(".", "_").replace("/", "_")
    archive_path = archive_dir / f"{safe_name}.json"
    archive_path.write_text(json.dumps(conversation_history, indent=2, default=str))

    logger.info(f"Archived history for {document_name} → {archive_path}")
    return str(archive_path)


def build_log(
    document_name: str,
    conversation_history: list[dict],
    gateway: Any,
    phase: str = "6",
    document: Optional[str] = None,
) -> DecisionLog:
    """Generate a structured Decision Log from conversation history.

    Args:
        document_name: Document the log is for.
        conversation_history: Raw chat messages.
        gateway: ModelGateway for summary generation.
        phase: Phase for cost tracking.
        document: Document name for cost tracking.

    Returns:
        DecisionLog with summary and Hard Decisions.
    """
    history_text = _format_history(conversation_history)

    prompt = (
        f"Analyze the following conversation about {document_name} and produce:\n\n"
        f"1. EXECUTIVE SUMMARY (max 500 words): What was decided and why.\n"
        f"2. HARD DECISIONS (key: value pairs): Every significant decision made.\n"
        f"   Format: key: value — reason\n"
        f"   Example: db_choice: PostgreSQL — self-hosted, no vendor lock\n\n"
        f"Conversation:\n{history_text[:8000]}"
    )

    response = gateway.call_model(
        role="primary",
        prompt=prompt,
        phase=phase,
        document=document,
    )

    summary, decisions = _parse_decision_log(response["content"])

    return DecisionLog(
        document_name=document_name,
        summary=summary,
        hard_decisions=decisions,
    )


def extract_hard_decisions(log: DecisionLog) -> dict[str, str]:
    """Get the Hard Decisions dict from a Decision Log."""
    return dict(log.hard_decisions)


def search_decisions(logs: dict[str, DecisionLog], key: str) -> Optional[str]:
    """Search all Decision Logs for a specific decision key.

    Args:
        logs: Dict of document_name → DecisionLog.
        key: Decision key to search for (case-insensitive).

    Returns:
        Decision value if found, None otherwise.
    """
    key_lower = key.lower()
    for doc_name, log in logs.items():
        for k, v in log.hard_decisions.items():
            if key_lower in k.lower():
                return v
    return None


def _format_history(history: list[dict]) -> str:
    """Format conversation history into readable text."""
    lines = []
    for msg in history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"[{role}]: {content}")
    return "\n\n".join(lines)


def _parse_decision_log(content: str) -> tuple[str, dict[str, str]]:
    """Parse Opus response into summary and Hard Decisions."""
    summary_parts = []
    decisions: dict[str, str] = {}
    in_summary = False
    in_decisions = False

    for line in content.split("\n"):
        stripped = line.strip()
        upper = stripped.upper()

        if "EXECUTIVE SUMMARY" in upper or "SUMMARY" in upper and not in_decisions:
            in_summary = True
            in_decisions = False
            continue
        elif "HARD DECISION" in upper:
            in_summary = False
            in_decisions = True
            continue

        if in_summary and stripped:
            summary_parts.append(stripped)
        elif in_decisions and ":" in stripped:
            # Parse key: value — reason
            parts = stripped.lstrip("- ").split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if key and not key[0].isdigit():
                    decisions[key] = value

    summary = " ".join(summary_parts)
    if not summary and not decisions:
        summary = content[:2000]

    return summary, decisions
