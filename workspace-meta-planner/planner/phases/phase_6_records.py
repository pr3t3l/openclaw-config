"""Phase 6: Record coordinator — orchestrate all record-keeping sub-modules.

Calls in order: archive history → build Decision Log → generate Entity Map
→ propose AF entries → update LESSONS_LEARNED → update doc registry.
All operations are idempotent. Partial failure marks run as DEGRADED.
See spec.md §3 (Phase 6).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from planner.decision_log import DecisionLog, archive_history, build_log
from planner.entity_map import EntityMap, extract_entities, save_entity_map
from planner.af_manager import propose as af_propose, AFEntry

logger = logging.getLogger(__name__)


@dataclass
class RecordUpdateResult:
    """Result of updating all records for a document."""
    history_archived: bool = False
    decision_log_built: bool = False
    entity_map_generated: bool = False
    af_proposed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def fully_successful(self) -> bool:
        return len(self.errors) == 0


def update_all_records(
    run_dir: str,
    document_name: str,
    doc_content: str,
    conversation_history: list[dict],
    gateway: Any,
    existing_af_entries: Optional[list[AFEntry]] = None,
    audit_findings_to_propose: Optional[list[dict]] = None,
    run_id: str = "",
) -> RecordUpdateResult:
    """Coordinate all Phase 6 record-keeping operations.

    Args:
        run_dir: Path to the run directory.
        document_name: Name of the approved document.
        doc_content: Final approved document content.
        conversation_history: Raw chat history for this document.
        gateway: ModelGateway instance.
        existing_af_entries: Current AF entries for dedup.
        audit_findings_to_propose: New findings to propose.
        run_id: Run ID for AF first_found field.

    Returns:
        RecordUpdateResult indicating what succeeded/failed.
    """
    result = RecordUpdateResult()

    # 1. Archive history
    try:
        archive_history(run_dir, document_name, conversation_history)
        result.history_archived = True
    except Exception as e:
        result.errors.append(f"History archive failed: {e}")
        logger.error(f"History archive failed for {document_name}: {e}")

    # 2. Build Decision Log
    try:
        log = build_log(document_name, conversation_history, gateway, document=document_name)
        # Save to decision_logs dir
        log_dir = Path(run_dir) / "decision_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        safe = document_name.replace(".", "_")
        import json
        (log_dir / f"{safe}.json").write_text(json.dumps({
            "document_name": log.document_name,
            "summary": log.summary,
            "hard_decisions": log.hard_decisions,
        }, indent=2))
        result.decision_log_built = True
    except Exception as e:
        result.errors.append(f"Decision Log failed: {e}")
        logger.error(f"Decision Log failed for {document_name}: {e}")

    # 3. Generate Entity Map
    try:
        entity_map = extract_entities(doc_content, document_name)
        save_entity_map(entity_map, run_dir)
        result.entity_map_generated = True
    except Exception as e:
        result.errors.append(f"Entity Map failed: {e}")
        logger.error(f"Entity Map failed for {document_name}: {e}")

    # 4. Propose AF entries
    if audit_findings_to_propose:
        existing = existing_af_entries or []
        for finding in audit_findings_to_propose:
            try:
                entry = af_propose(
                    finding.get("description", ""),
                    finding.get("fix", ""),
                    af_class=finding.get("class", "requires_review"),
                    run_id=run_id,
                    existing_entries=existing,
                )
                if entry:
                    result.af_proposed.append(entry.af_id)
                    existing.append(entry)
            except Exception as e:
                result.errors.append(f"AF proposal failed: {e}")

    if result.errors:
        logger.warning(f"Phase 6 partial failure for {document_name}: {result.errors}")
    else:
        logger.info(f"Phase 6 complete for {document_name}")

    return result
