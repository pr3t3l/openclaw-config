"""Phase handlers — PhaseHandler subclasses that wrap existing phase functions.

Each handler calls the real phase function, updates state with results,
and sets state["_gate_pending"] for human gates.

See spec.md §3 for the full phase/gate mapping.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from planner.model_gateway import ModelGateway
from planner.orchestrator.dispatcher import Dispatcher, PhaseHandler
from planner.orchestrator.gates import GATE_DEFINITIONS

logger = logging.getLogger(__name__)


def _gateway_from_state(state: dict) -> ModelGateway:
    """Create a ModelGateway bound to the current state for cost tracking."""
    return ModelGateway(state)


def _run_dir(project_root: str, run_id: str) -> str:
    return str(Path(project_root) / "planner_runs" / run_id)


class Phase0Handler(PhaseHandler):
    """Phase 0: Setup — detect mode, load context, determine doc list.

    Gate G0: human confirms mode + doc list + PII scan.
    """

    phase_id = "0"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_0_setup import run_phase_0

        project_root = context["project_root"]
        has_attachments = state.get("_has_attachments", False)
        doc_type = state.get("_doc_type")

        setup = run_phase_0(
            project_root,
            has_attachments=has_attachments,
            doc_type=doc_type,
        )

        state["documents_pending"] = setup.documents_pending
        logger.info(f"Phase 0: mode={setup.mode}, docs={setup.documents_pending}")

        # G0 requires human confirmation
        state["_gate_pending"] = "G0"
        return state


class Phase1Handler(PhaseHandler):
    """Phase 1: Intake — section-by-section Q&A.

    In command-dispatch mode (no conversation), we run a single-pass intake
    that auto-accepts all sections. Gate G1 pauses for human confirmation.
    """

    phase_id = "1"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_1_intake import IntakeSession
        from planner.template_loader import load_template

        doc = state["current_document"]
        if not doc:
            # First document — pop from pending
            if not state["documents_pending"]:
                return state
            doc_name = state["documents_pending"][0]
            doc_type = doc_name.replace(".md", "")
            state["current_document"] = {
                "name": doc_name,
                "type": doc_type,
                "version": 1,
                "phase_status": "intake_in_progress",
                "phase_attempt": 1,
                "sections_completed": [],
                "template": doc_type,
            }
            doc = state["current_document"]

        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        try:
            sections = load_template(doc_type)
        except (ValueError, FileNotFoundError):
            logger.warning(f"No template for {doc_type}, skipping intake")
            doc["phase_status"] = "intake_complete"
            return state

        gateway = _gateway_from_state(state)
        session = IntakeSession(
            doc_type=doc_type,
            sections=sections,
            decision_logs=state.get("decision_logs"),
        )

        # Single-pass: auto-complete all sections with placeholder answers
        # The real intake happens via Telegram conversation; here we bootstrap.
        while not session.is_complete:
            prompt_info = session.get_next_prompt(gateway=gateway)
            if prompt_info.get("action") == "complete":
                break
            section_title = prompt_info.get("section", "")
            session.record_answer(f"[Pending human input for: {section_title}]")
            if hasattr(session, 'confirm_section'):
                session.confirm_section(True)

        doc["phase_status"] = "intake_complete"
        doc["sections_completed"] = session.sections_completed
        state["_intake_answers"] = session.answers

        # G1: human confirms idea captured
        state["_gate_pending"] = "G1"
        return state


class Phase1_5Handler(PhaseHandler):
    """Phase 1.5: Ideation — multi-model feature suggestions.

    Gate G1.5: human accepts/rejects suggestions.
    Skipped for foundation doc types (handled by dispatcher._should_skip_phase).
    """

    phase_id = "1.5"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_1_5_ideation import ideate, should_skip

        doc = state["current_document"]
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        if should_skip(doc_type):
            return state

        gateway = _gateway_from_state(state)
        intake_summary = "\n".join(
            f"- {k}: {v}" for k, v in state.get("_intake_answers", {}).items()
        )

        result = ideate(
            doc_type=doc_type,
            intake_summary=intake_summary,
            gateway=gateway,
            phase="1.5",
            document=doc.get("name"),
        )

        state["_ideation_result"] = {
            "accepted": result.accepted,
            "skipped": result.skipped,
        }

        # G1.5: human reviews ideation suggestions
        state["_gate_pending"] = "G1.5"
        return state


class Phase2Handler(PhaseHandler):
    """Phase 2: Draft — populate SDD template with intake + ideation answers."""

    phase_id = "2"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_2_draft import draft_document
        from planner.template_loader import load_template

        project_root = context["project_root"]
        doc = state["current_document"]
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        gateway = _gateway_from_state(state)

        try:
            sections = load_template(doc_type)
            template_content = "\n".join(
                f"{'#' * s.level} {s.title}\n{s.content}" for s in sections
            )
        except (ValueError, FileNotFoundError):
            template_content = f"# {doc_type}\n\n(Template not available)"

        intake_answers = state.get("_intake_answers", {})
        ideation_accepted = state.get("_ideation_result", {}).get("accepted", [])

        # Load constitution rules if available
        constitution_path = Path(project_root) / "docs" / "CONSTITUTION.md"
        constitution_rules = ""
        if constitution_path.exists():
            constitution_rules = constitution_path.read_text(encoding="utf-8")

        result = draft_document(
            doc_type=doc_type,
            template_content=template_content,
            intake_answers=intake_answers,
            gateway=gateway,
            ideation_accepted=ideation_accepted,
            constitution_rules=constitution_rules,
            phase="2",
            document=doc.get("name"),
        )

        # Store draft content in run dir
        run_dir = _run_dir(project_root, state["run_id"])
        draft_path = Path(run_dir) / "drafts" / f"{doc.get('name', 'draft')}"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(result.content, encoding="utf-8")

        doc["version"] = result.version
        doc["phase_status"] = "draft_complete"

        state["_draft_content"] = result.content
        state["_draft_validation"] = {
            "passed": result.validation_passed,
            "errors": result.validation_errors,
        }

        # G2 is auto-evaluated (no human), dispatcher handles it
        return state


class Phase2_5Handler(PhaseHandler):
    """Phase 2.5: Pre-audit — check draft against AUDIT_FINDINGS.md."""

    phase_id = "2.5"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_2_5_preaudit import load_audit_findings, check_against_af

        project_root = context["project_root"]
        doc = state["current_document"]
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))
        doc_content = state.get("_draft_content", "")

        entries = load_audit_findings(project_root)
        result = check_against_af(doc_content, doc_type, entries)

        if result.safe_count > 0 or result.semantic_count > 0:
            state["_draft_content"] = result.content
            logger.info(
                f"Phase 2.5: {result.safe_count} safe fixes applied, "
                f"{result.semantic_count} semantic flags"
            )

        doc["phase_status"] = "preaudit_complete"

        # G2.5 is auto-evaluated (no human)
        return state


class Phase3Handler(PhaseHandler):
    """Phase 3: Audit — 4 sequential model calls (GPT+Gemini, tech+arch).

    Gate G3: human reviews audit triage (0 criticals required).
    """

    phase_id = "3"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_3_audit import run_audit

        project_root = context["project_root"]
        doc = state["current_document"]
        doc_content = state.get("_draft_content", "")
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        gateway = _gateway_from_state(state)

        result = run_audit(
            doc_content=doc_content,
            doc_type=doc_type,
            full_state=state,
            gateway=gateway,
            run_id=state["run_id"],
            project_root=project_root,
            document=doc.get("name"),
            phase="3",
        )

        state["_audit_result"] = {
            "call_count": len(result.call_results),
            "raw_paths": result.raw_saved_paths,
        }
        doc["phase_status"] = "audit_complete"

        # G3: human reviews audit triage
        state["_gate_pending"] = "G3"
        return state


class Phase4Handler(PhaseHandler):
    """Phase 4: Lessons check — verify against LESSONS_LEARNED.md."""

    phase_id = "4"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_4_lessons import load_lessons, check_lessons

        project_root = context["project_root"]
        doc = state["current_document"]
        doc_content = state.get("_draft_content", "")
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        lessons_content = load_lessons(project_root)
        if not lessons_content:
            doc["phase_status"] = "lessons_complete"
            state["lessons_check_result"] = {"violations": [], "recommendations": []}
            return state

        gateway = _gateway_from_state(state)

        result = check_lessons(
            doc_content=doc_content,
            doc_type=doc_type,
            lessons_content=lessons_content,
            gateway=gateway,
            phase="4",
            document=doc.get("name"),
        )

        state["lessons_check_result"] = {
            "violations": [
                {"id": v.lesson_id, "description": v.description}
                for v in result.violations
            ],
            "recommendations": [
                {"id": r.lesson_id, "description": r.description}
                for r in result.recommendations
            ],
        }
        doc["phase_status"] = "lessons_complete"

        # G4 is auto-evaluated (no human)
        return state


class Phase5Handler(PhaseHandler):
    """Phase 5: Finalize — apply fixes, present to human for approval.

    Gate G5: human approves document.
    """

    phase_id = "5"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_5_finalize import present_for_approval

        doc = state["current_document"]
        doc_content = state.get("_draft_content", "")
        doc_name = doc.get("name", "document.md")

        result = present_for_approval(
            doc_content=doc_content,
            document_name=doc_name,
            changes_description="Draft ready for review",
            doc_cost=state["cost"].get("by_document", {}).get(doc_name, 0.0),
            total_cost=state["cost"]["total_usd"],
        )

        state["_finalize_result"] = {
            "summary": result.summary,
            "clean_content": result.clean_content,
        }
        state["_draft_content"] = result.content
        doc["phase_status"] = "finalize_complete"

        # G5: human approves document
        state["_gate_pending"] = "G5"
        return state


class Phase6Handler(PhaseHandler):
    """Phase 6: Records — archive history, build decision log, entity map, AF entries."""

    phase_id = "6"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_6_records import update_all_records
        from planner.phases.phase_2_5_preaudit import load_audit_findings

        project_root = context["project_root"]
        doc = state["current_document"]
        doc_name = doc.get("name", "document.md")
        doc_content = state.get("_draft_content", "")
        run_dir = _run_dir(project_root, state["run_id"])

        gateway = _gateway_from_state(state)
        existing_af = load_audit_findings(project_root)

        result = update_all_records(
            run_dir=run_dir,
            document_name=doc_name,
            doc_content=doc_content,
            conversation_history=[],  # History managed by Telegram, not available here
            gateway=gateway,
            existing_af_entries=existing_af,
            run_id=state["run_id"],
        )

        if not result.fully_successful:
            logger.warning(f"Phase 6 partial failure: {result.errors}")
            state["run_status"] = "degraded"

        # Move document from pending to completed
        if doc_name in state["documents_pending"]:
            state["documents_pending"].remove(doc_name)
        if doc_name not in state["documents_completed"]:
            state["documents_completed"].append(doc_name)

        # Save final clean version
        finalize = state.get("_finalize_result", {})
        clean_content = finalize.get("clean_content", doc_content)
        output_path = Path(run_dir) / "output" / doc_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(clean_content, encoding="utf-8")

        # Reset current_document for next doc (or None if done)
        state["current_document"] = None
        doc_phase_status = "records_complete"

        logger.info(f"Phase 6 complete for {doc_name}")
        return state


class Phase6_5Handler(PhaseHandler):
    """Phase 6.5: Cross-document validation via Entity Maps.

    Gate G6.5: human reviews contradictions.
    """

    phase_id = "6.5"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_6_5_crossdoc import validate_entities
        from planner.entity_map import EntityMap, extract_entities

        project_root = context["project_root"]
        run_dir = _run_dir(project_root, state["run_id"])

        # Build EntityMap objects from stored entity_maps in state
        entity_maps: dict[str, EntityMap] = {}
        raw_maps = state.get("entity_maps", {})

        if raw_maps:
            # Reconstruct EntityMap objects from state dicts
            for doc_name, map_dict in raw_maps.items():
                em = EntityMap(document_name=doc_name)
                # If entries are stored, reconstruct them
                from planner.entity_map import EntityEntry
                for entry_data in map_dict.get("entries", []):
                    em.entries.append(EntityEntry(
                        name=entry_data.get("name", ""),
                        entity_type=entry_data.get("entity_type", ""),
                        heading_path=entry_data.get("heading_path", ""),
                        details=entry_data.get("details", ""),
                    ))
                entity_maps[doc_name] = em
        else:
            # Fallback: extract from output documents
            output_dir = Path(run_dir) / "output"
            if output_dir.exists():
                for doc_path in output_dir.glob("*.md"):
                    content = doc_path.read_text(encoding="utf-8")
                    em = extract_entities(content, doc_path.name)
                    entity_maps[doc_path.name] = em

        result = validate_entities(entity_maps)

        if result.passed:
            logger.info(f"Phase 6.5: 0 contradictions across {len(entity_maps)} docs")
        else:
            logger.warning(f"Phase 6.5: {result.contradiction_count} contradictions")
            # G6.5: human reviews contradictions
            state["_gate_pending"] = "G6.5"

        return state


class Phase7Handler(PhaseHandler):
    """Phase 7: Generate plan.md and tasks.md from approved spec.

    Gate G7: human approves plan + tasks.
    """

    phase_id = "7"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_7_plan import generate_plan
        from planner.phases.phase_7_tasks import generate_tasks

        project_root = context["project_root"]
        run_dir = _run_dir(project_root, state["run_id"])
        gateway = _gateway_from_state(state)

        # Load the approved spec content
        output_dir = Path(run_dir) / "output"
        spec_content = ""
        constitution_rules = ""

        # Find the main spec (MODULE_SPEC or WORKFLOW_SPEC)
        for doc_name in state.get("documents_completed", []):
            doc_path = output_dir / doc_name
            if doc_path.exists():
                content = doc_path.read_text(encoding="utf-8")
                if "SPEC" in doc_name.upper():
                    spec_content = content
                elif "CONSTITUTION" in doc_name.upper():
                    constitution_rules = content

        if not spec_content:
            logger.warning("Phase 7: No spec found in output, using draft content")
            spec_content = state.get("_draft_content", "")

        # Generate plan
        plan_result = generate_plan(
            spec_content=spec_content,
            gateway=gateway,
            constitution_rules=constitution_rules,
            phase="7",
        )

        plan_path = Path(run_dir) / "output" / "plan.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(plan_result.content, encoding="utf-8")

        # Generate tasks
        tasks_result = generate_tasks(
            plan_content=plan_result.content,
            spec_content=spec_content,
            gateway=gateway,
            phase="7",
        )

        tasks_path = Path(run_dir) / "output" / "tasks.md"
        tasks_path.write_text(tasks_result.content, encoding="utf-8")

        logger.info(
            f"Phase 7: plan ({plan_result.module_count} modules), "
            f"tasks ({tasks_result.total_tasks} tasks)"
        )

        # G7: human approves plan + tasks
        state["_gate_pending"] = "G7"
        return state


# ── Registration ──────────────────────────────────────────────────────

ALL_HANDLERS: dict[str, type[PhaseHandler]] = {
    "0": Phase0Handler,
    "1": Phase1Handler,
    "1.5": Phase1_5Handler,
    "2": Phase2Handler,
    "2.5": Phase2_5Handler,
    "3": Phase3Handler,
    "4": Phase4Handler,
    "5": Phase5Handler,
    "6": Phase6Handler,
    "6.5": Phase6_5Handler,
    "7": Phase7Handler,
}


def register_all_handlers(dispatcher: Dispatcher, project_root: str) -> None:
    """Instantiate and register all phase handlers in the dispatcher.

    Args:
        dispatcher: The Dispatcher instance to register handlers on.
        project_root: Project root path (used by handlers via context).
    """
    for phase_id, handler_cls in ALL_HANDLERS.items():
        dispatcher.register_handler(phase_id, handler_cls())
    logger.info(f"Registered {len(ALL_HANDLERS)} phase handlers")
