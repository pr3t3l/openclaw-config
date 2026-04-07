"""Re-entry coordinator — orchestrate full /plan-fix flow.

Flow: reconcile → impact → patch → re-audit → cross-doc → delta tasks → human approval.
See spec.md §10 (Re-Entry Protocol).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from planner.reentry.reconciler import scan_codebase, map_files_to_tasks, produce_status
from planner.reentry.impact import build_graph, compute_impact
from planner.reentry.patcher import patch_spec
from planner.reentry.reaudit import selective_reaudit
from planner.reentry.delta_tasks import generate_delta_tasks

logger = logging.getLogger(__name__)


@dataclass
class PlanFixResult:
    """Result of a /plan-fix flow."""
    reconciliation_summary: str = ""
    impact_summary: str = ""
    void_tasks: list[str] = field(default_factory=list)
    needs_review_tasks: list[str] = field(default_factory=list)
    patched_spec: str = ""
    reaudit_passed: bool = False
    delta_tasks: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


def run_plan_fix(
    project_root: str,
    tasks_content: str,
    spec_content: str,
    blocker_task: str,
    blocker_description: str,
    gateway: Any,
) -> PlanFixResult:
    """Execute the full /plan-fix re-entry flow.

    Args:
        project_root: Project root path.
        tasks_content: Current tasks.md content.
        spec_content: Current spec.md content.
        blocker_task: Task ID that is blocked.
        blocker_description: Description of the blocker.
        gateway: ModelGateway instance.

    Returns:
        PlanFixResult with all outputs.
    """
    result = PlanFixResult()

    # Step 1: Codebase reconciliation
    try:
        scan = scan_codebase(project_root)
        file_mapping = map_files_to_tasks(scan["file_tree"], tasks_content)
        recon = produce_status(file_mapping, tasks_content)
        result.reconciliation_summary = recon.summary
    except Exception as e:
        result.errors.append(f"Reconciliation failed: {e}")
        logger.error(f"Reconciliation failed: {e}")
        return result

    # Step 2: Impact analysis
    try:
        graph = build_graph(tasks_content)
        impact = compute_impact(graph, blocker_task)
        result.void_tasks = impact.void_tasks
        result.needs_review_tasks = impact.needs_review_tasks
        result.impact_summary = (
            f"{len(impact.void_tasks)} VOID, "
            f"{len(impact.needs_review_tasks)} NEEDS_REVIEW, "
            f"{len(impact.valid_tasks)} VALID"
        )
    except Exception as e:
        result.errors.append(f"Impact analysis failed: {e}")
        logger.error(f"Impact analysis failed: {e}")
        return result

    # Step 3: Spec patch
    try:
        result.patched_spec = patch_spec(
            spec_content, blocker_description, [], gateway, document="spec.md",
        )
    except Exception as e:
        result.errors.append(f"Spec patch failed: {e}")
        logger.error(f"Spec patch failed: {e}")
        return result

    # Step 4: Selective re-audit
    try:
        reaudit = selective_reaudit(
            result.patched_spec, [], gateway, document="spec.md",
        )
        result.reaudit_passed = reaudit["passed"]
    except Exception as e:
        result.errors.append(f"Re-audit failed: {e}")
        logger.error(f"Re-audit failed: {e}")

    # Step 5: Delta tasks
    if result.void_tasks:
        try:
            result.delta_tasks = generate_delta_tasks(
                impact, result.patched_spec, recon.summary, gateway,
            )
        except Exception as e:
            result.errors.append(f"Delta tasks failed: {e}")
            logger.error(f"Delta tasks failed: {e}")

    return result
