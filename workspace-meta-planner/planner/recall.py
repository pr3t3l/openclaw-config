"""History recall — search history_archive by keyword/entity.

Returns specific sections, not entire files.
See spec.md §7.2 ("Recall" capability).
"""

import json
import logging
from pathlib import Path
from typing import Optional

from planner.decision_log import DecisionLog

logger = logging.getLogger(__name__)


def recall_history(
    run_dir: str,
    doc_name: str,
    topic: str,
    decision_logs: Optional[dict[str, DecisionLog]] = None,
) -> Optional[str]:
    """Recall a specific discussion fragment from archived history.

    Searches Hard Decisions first (fast), then falls back to full-text.

    Args:
        run_dir: Path to the run directory.
        doc_name: Document to search in.
        topic: Keyword or topic to search for.
        decision_logs: Optional Decision Logs for fast lookup.

    Returns:
        Relevant text fragment, or None if not found.
    """
    # Fast path: search Hard Decisions
    if decision_logs:
        safe_name = doc_name.replace(".", "_").replace("/", "_")
        for name, log in decision_logs.items():
            norm = name.replace(".", "_").replace("/", "_")
            if norm == safe_name or name == doc_name:
                for key, value in log.hard_decisions.items():
                    if topic.lower() in key.lower() or topic.lower() in value.lower():
                        return f"[Decision: {key}] {value}"

    # Slow path: search archived history
    archive_path = _archive_path(run_dir, doc_name)
    if not archive_path.exists():
        return None

    history = json.loads(archive_path.read_text())
    return _search_history(history, topic)


def search_all_archives(run_dir: str, keyword: str) -> list[dict]:
    """Search across all archived histories for a keyword.

    Args:
        run_dir: Path to the run directory.
        keyword: Keyword to search for.

    Returns:
        List of {document, fragment} matches.
    """
    archive_dir = Path(run_dir) / "history_archive"
    if not archive_dir.exists():
        return []

    results = []
    for archive_file in archive_dir.glob("*.json"):
        doc_name = archive_file.stem.replace("_", ".")
        history = json.loads(archive_file.read_text())
        fragment = _search_history(history, keyword)
        if fragment:
            results.append({"document": doc_name, "fragment": fragment})

    return results


def _archive_path(run_dir: str, doc_name: str) -> Path:
    safe_name = doc_name.replace(".", "_").replace("/", "_")
    return Path(run_dir) / "history_archive" / f"{safe_name}.json"


def _search_history(history: list[dict], keyword: str) -> Optional[str]:
    """Search conversation history for messages containing keyword."""
    keyword_lower = keyword.lower()
    matches = []

    for msg in history:
        content = msg.get("content", "")
        if keyword_lower in content.lower():
            role = msg.get("role", "unknown")
            # Extract relevant paragraph
            for para in content.split("\n\n"):
                if keyword_lower in para.lower():
                    matches.append(f"[{role}]: {para.strip()}")
                    break

    if matches:
        return "\n\n".join(matches[:3])  # Return top 3 matches
    return None
