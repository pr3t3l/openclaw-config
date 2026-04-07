"""Phase 3: Audit — 4 sequential model calls with jittered backoff.

GPT (tech + arch) and Gemini (tech + arch), 5-10s between calls.
Each call uses filtered context from filter_for_agent.
Raw results saved to planner_runs/{run_id}/audits/.
See spec.md §3 (Phase 3), spec.md §4 (Model Selection).
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from planner.filter_for_agent import filter_for_agent
from planner.prompts import technical_auditor, architecture_reviewer

logger = logging.getLogger(__name__)

# Audit call sequence: 4 calls total
AUDIT_CALLS = [
    {"role": "auditor_gpt", "audit_role": "technical", "model_label": "gpt_tech"},
    {"role": "auditor_gpt", "audit_role": "architecture", "model_label": "gpt_arch"},
    {"role": "auditor_gemini", "audit_role": "technical", "model_label": "gemini_tech"},
    {"role": "auditor_gemini", "audit_role": "architecture", "model_label": "gemini_arch"},
]

BACKOFF_MIN = 5.0
BACKOFF_MAX = 10.0


@dataclass
class AuditCallResult:
    """Result from a single audit call."""
    model_label: str
    audit_role: str
    content: str
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration: float = 0.0


@dataclass
class AuditResult:
    """Combined result from all 4 audit calls."""
    call_results: list[AuditCallResult] = field(default_factory=list)
    raw_saved_paths: list[str] = field(default_factory=list)

    @property
    def issue_counts(self) -> dict[str, int]:
        """Count issues per model_label (approximate by line counting)."""
        counts = {}
        for cr in self.call_results:
            lines = [l for l in cr.content.split("\n") if l.strip().startswith("-") or "CRITICAL" in l or "IMPORTANT" in l or "MINOR" in l]
            counts[cr.model_label] = len(lines)
        return counts


def run_audit(
    doc_content: str,
    doc_type: str,
    full_state: dict,
    gateway: Any,
    run_id: str,
    project_root: str,
    document: Optional[str] = None,
    phase: str = "3",
    backoff: bool = True,
) -> AuditResult:
    """Execute the 4-call audit sequence.

    Args:
        doc_content: The document to audit.
        doc_type: Document type.
        full_state: Full planner state (for filter_for_agent).
        gateway: ModelGateway instance.
        run_id: Run ID for saving results.
        project_root: Project root path.
        document: Document name for cost tracking.
        phase: Phase identifier.
        backoff: Whether to apply jittered backoff between calls.

    Returns:
        AuditResult with all 4 call results.
    """
    result = AuditResult()
    audits_dir = Path(project_root) / "planner_runs" / run_id / "audits"
    audits_dir.mkdir(parents=True, exist_ok=True)

    for i, call_spec in enumerate(AUDIT_CALLS):
        if i > 0 and backoff:
            delay = random.uniform(BACKOFF_MIN, BACKOFF_MAX)
            logger.info(f"Backoff {delay:.1f}s before audit call {i+1}/4")
            time.sleep(delay)

        # Build prompt based on role
        if call_spec["audit_role"] == "technical":
            context = _build_technical_context(doc_type, full_state)
            system = technical_auditor.system_prompt(doc_type)
            prompt = technical_auditor.audit_prompt(doc_content, context.get("rules", ""))
        else:
            context = _build_architecture_context(doc_type, full_state)
            system = architecture_reviewer.system_prompt(doc_type)
            prompt = architecture_reviewer.audit_prompt(
                doc_content,
                context.get("stack", ""),
                context.get("integrations", ""),
            )

        # Make the call
        response = gateway.call_model(
            role=call_spec["role"],
            prompt=prompt,
            context=system,
            phase=phase,
            document=document,
        )

        call_result = AuditCallResult(
            model_label=call_spec["model_label"],
            audit_role=call_spec["audit_role"],
            content=response["content"],
            model=response.get("model", ""),
            tokens_in=response.get("tokens_in", 0),
            tokens_out=response.get("tokens_out", 0),
            cost_usd=response.get("cost_usd", 0.0),
            duration=response.get("duration", 0.0),
        )
        result.call_results.append(call_result)

        # Save raw result
        doc_safe = (document or "unknown").replace(".", "_").replace("/", "_")
        filename = f"{doc_safe}_{call_spec['audit_role']}_{call_spec['model_label']}.json"
        save_path = audits_dir / filename
        save_path.write_text(json.dumps({
            "model_label": call_result.model_label,
            "audit_role": call_result.audit_role,
            "model": call_result.model,
            "content": call_result.content,
            "tokens_in": call_result.tokens_in,
            "tokens_out": call_result.tokens_out,
            "cost_usd": call_result.cost_usd,
            "duration": call_result.duration,
        }, indent=2))
        result.raw_saved_paths.append(str(save_path))

        logger.info(
            f"Audit call {i+1}/4 ({call_spec['model_label']}) complete: "
            f"{call_result.tokens_out} tokens, ${call_result.cost_usd:.4f}"
        )

    return result


def _build_technical_context(doc_type: str, full_state: dict) -> dict:
    """Build filtered context for technical auditor."""
    try:
        filtered = filter_for_agent(full_state, "technical_auditor")
        rules = filtered.get("constitution", {}).get("rules", "")
        if isinstance(rules, list):
            rules = "\n".join(f"- {r}" for r in rules)
        return {"rules": rules}
    except (ValueError, KeyError):
        return {"rules": ""}


def _build_architecture_context(doc_type: str, full_state: dict) -> dict:
    """Build filtered context for architecture reviewer."""
    try:
        filtered = filter_for_agent(full_state, "architecture_reviewer")
        stack = filtered.get("project_context", {}).get("stack", "")
        integrations = filtered.get("project_context", {}).get("integrations_summary", "")
        if isinstance(stack, dict):
            stack = json.dumps(stack, indent=2)
        return {"stack": str(stack), "integrations": str(integrations)}
    except (ValueError, KeyError):
        return {"stack": "", "integrations": ""}
