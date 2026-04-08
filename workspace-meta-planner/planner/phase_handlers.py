"""Phase handlers — PhaseHandler subclasses that wrap existing phase functions.

Each handler calls the real phase function, updates state with results,
and sets state["_gate_pending"] for human gates.

Transient data between phases (intake answers, draft content, etc.) is stored
as files in the run directory, NOT in state dict (which has additionalProperties: false).

See spec.md §3 for the full phase/gate mapping.
"""

import json
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


def _run_dir(project_root: str, run_id: str) -> Path:
    return Path(project_root) / "planner_runs" / run_id


def _save_transient(run_dir: Path, filename: str, data: Any) -> None:
    """Save transient phase data as a JSON file in the run directory."""
    path = run_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_transient(run_dir: Path, filename: str, default: Any = None) -> Any:
    """Load transient phase data from a file in the run directory."""
    path = run_dir / filename
    if not path.exists():
        return default
    content = path.read_text(encoding="utf-8")
    if filename.endswith(".json"):
        return json.loads(content)
    return content


def _load_audit_findings(run_dir: Path, doc_name: str) -> tuple[str, int]:
    """Load CRITICAL and IMPORTANT findings from Phase 3 audit files.

    Returns:
        Tuple of (concatenated findings text, count of findings).
    """
    audits_dir = run_dir / "audits"
    if not audits_dir.exists():
        return "", 0

    doc_safe = doc_name.replace(".", "_").replace("/", "_")
    findings_parts = []
    total_count = 0

    for audit_file in sorted(audits_dir.glob(f"{doc_safe}_*.json")):
        try:
            data = json.loads(audit_file.read_text(encoding="utf-8"))
            content = data.get("content", "")
            if not content:
                continue

            # Extract CRITICAL and IMPORTANT findings
            label = data.get("model_label", audit_file.stem)
            role = data.get("audit_role", "")
            relevant_lines = []

            for line in content.split("\n"):
                line_upper = line.upper()
                if "CRITICAL" in line_upper or "IMPORTANT" in line_upper:
                    relevant_lines.append(line.strip())
                elif relevant_lines and line.strip() and not line.strip().startswith("#"):
                    # Include continuation lines after a finding header
                    if line.strip().startswith("-") or line.strip().startswith("*"):
                        relevant_lines.append(line.strip())

            if relevant_lines:
                count = sum(1 for l in relevant_lines
                           if "CRITICAL" in l.upper() or "IMPORTANT" in l.upper())
                total_count += count
                findings_parts.append(
                    f"### {label} ({role})\n" + "\n".join(relevant_lines)
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read audit file {audit_file}: {e}")

    return "\n\n".join(findings_parts), total_count


def _apply_audit_findings(
    gateway: "ModelGateway",
    doc_content: str,
    findings_text: str,
    doc_name: str,
    phase: str = "5",
    document: str = "",
) -> str:
    """Call Opus to apply audit findings to the document.

    Returns:
        The revised document content with findings applied.
    """
    prompt = (
        f"Apply these audit findings to the document below. "
        f"For each CRITICAL and IMPORTANT finding, make the minimum change needed. "
        f"Do NOT rewrite sections that have no findings. "
        f"Return the complete updated document in Markdown.\n\n"
        f"## Audit Findings to Apply\n\n{findings_text}\n\n"
        f"## Document to Update\n\n{doc_content}"
    )

    system = (
        f"You are an SDD document editor. You apply audit findings to documents "
        f"with minimal, targeted changes. Preserve all existing content that is "
        f"not affected by the findings. Output ONLY the complete updated document "
        f"in Markdown — no commentary, no explanation."
    )

    response = gateway.call_model(
        role="primary",
        prompt=prompt,
        context=system,
        phase=phase,
        document=document,
        max_tokens=16384,
    )

    return response["content"]


class Phase0Handler(PhaseHandler):
    """Phase 0: Setup — detect mode, load context, determine doc list.

    Gate G0: human confirms mode + doc list + PII scan.
    """

    phase_id = "0"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_0_setup import run_phase_0

        project_root = context["project_root"]
        run_dir = _run_dir(project_root, state["run_id"])

        # Read transient config if set by cmd_start
        config = _load_transient(run_dir, "phase0_config.json", {})
        has_attachments = config.get("has_attachments", False)
        doc_type = config.get("doc_type")

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
    """Phase 1: Intake — generate content for each template section via Opus.

    Reads input.txt (the human's idea) and calls the model for each section
    of the template. Saves real answers to intake_answers.json.
    Gate G1 pauses for human confirmation.
    """

    phase_id = "1"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.template_loader import load_template

        project_root = context["project_root"]
        run_dir = _run_dir(project_root, state["run_id"])

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

        # Load the human's project idea from input.txt
        input_path = run_dir / "input.txt"
        idea = input_path.read_text(encoding="utf-8").strip() if input_path.exists() else ""

        # Load decision logs from previous docs for context
        decision_logs = state.get("decision_logs", {})
        decision_ctx = ""
        if decision_logs:
            decision_ctx = "\n\nDecisions from previous documents:\n" + "\n".join(
                f"- {doc_name}: {log[:200]}" for doc_name, log in decision_logs.items()
            )

        gateway = _gateway_from_state(state)
        answers: dict[str, str] = {}
        completed: list[str] = []

        system = (
            f"You are an SDD Planner intake agent. You generate content for "
            f"each section of a {doc_type} document based on the human's project idea.\n\n"
            f"Rules:\n"
            f"- Be specific and concrete — not 'consider using X' but 'X because...'\n"
            f"- No stubs: TBD, TODO, placeholder → FORBIDDEN\n"
            f"- If you're unsure, make a reasonable choice and mark it with "
            f"[ASSUMPTION — validate during implementation]\n"
            f"- Output ONLY the section content, no markdown headers"
        )

        for section in sections:
            # Skip level-1 headings (document title) — only fill content sections
            if section.level < 2:
                continue

            prompt = (
                f"Project idea: {idea}\n\n"
                f"Document type: {doc_type}\n"
                f"Section: {section.title}\n"
                f"Template guidance for this section:\n{section.content}\n"
                f"{decision_ctx}\n\n"
                f"Generate complete, specific content for the '{section.title}' section "
                f"of this {doc_type} based on the project idea above."
            )

            response = gateway.call_model(
                role="primary",
                prompt=prompt,
                context=system,
                phase="1",
                document=doc.get("name"),
                max_tokens=4096,
            )

            answers[section.title] = response["content"]
            completed.append(section.title)
            logger.info(f"Intake: section '{section.title}' completed")

        doc["phase_status"] = "intake_complete"
        doc["sections_completed"] = completed

        # Save intake answers to file (not state — schema disallows extra fields)
        _save_transient(run_dir, "intake_answers.json", answers)

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

        project_root = context["project_root"]
        run_dir = _run_dir(project_root, state["run_id"])

        doc = state["current_document"]
        if not doc:
            logger.warning("Phase 1.5: no current_document, skipping ideation")
            return state

        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        if should_skip(doc_type):
            return state

        gateway = _gateway_from_state(state)

        # Load intake answers from file
        intake_answers = _load_transient(run_dir, "intake_answers.json", {})
        intake_summary = "\n".join(
            f"- {k}: {v}" for k, v in intake_answers.items()
        )

        try:
            result = ideate(
                doc_type=doc_type,
                intake_summary=intake_summary,
                gateway=gateway,
                phase="1.5",
                document=doc.get("name"),
            )
        except Exception as e:
            # Ideation is optional — skip gracefully on failure
            logger.error(f"Phase 1.5 ideation failed, skipping: {e}")
            _save_transient(run_dir, "ideation_result.json", {
                "accepted": [],
                "skipped": True,
            })
            return state

        # Save ideation result to file
        _save_transient(run_dir, "ideation_result.json", {
            "accepted": result.accepted,
            "skipped": result.skipped,
        })

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
        run_dir = _run_dir(project_root, state["run_id"])
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

        # Load transient data from files
        intake_answers = _load_transient(run_dir, "intake_answers.json", {})
        ideation_result = _load_transient(run_dir, "ideation_result.json", {})
        ideation_accepted = ideation_result.get("accepted", [])

        # Inject project idea into intake context so drafter knows the project
        input_path = run_dir / "input.txt"
        if input_path.exists():
            idea = input_path.read_text(encoding="utf-8").strip()
            if idea and "Project Idea" not in intake_answers:
                intake_answers["Project Idea"] = idea

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
        doc_name = doc.get("name", "draft.md")
        draft_path = run_dir / "drafts" / doc_name
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(result.content, encoding="utf-8")

        # Save draft content as transient file for subsequent phases
        _save_transient(run_dir, "draft_content.md", result.content)

        doc["version"] = result.version
        doc["phase_status"] = "draft_complete"

        # G2 is auto-evaluated (no human), dispatcher handles it
        return state


class Phase2_5Handler(PhaseHandler):
    """Phase 2.5: Pre-audit — check draft against AUDIT_FINDINGS.md."""

    phase_id = "2.5"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_2_5_preaudit import load_audit_findings, check_against_af

        project_root = context["project_root"]
        run_dir = _run_dir(project_root, state["run_id"])
        doc = state["current_document"]
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        doc_content = _load_transient(run_dir, "draft_content.md", "")

        entries = load_audit_findings(project_root)
        result = check_against_af(doc_content, doc_type, entries)

        if result.safe_count > 0 or result.semantic_count > 0:
            # Update the draft content file with pre-audit fixes
            _save_transient(run_dir, "draft_content.md", result.content)
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
        run_dir = _run_dir(project_root, state["run_id"])
        doc = state["current_document"]
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        doc_content = _load_transient(run_dir, "draft_content.md", "")

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

        # Save audit result metadata to file
        _save_transient(run_dir, "audit_result.json", {
            "call_count": len(result.call_results),
            "raw_paths": result.raw_saved_paths,
        })
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
        run_dir = _run_dir(project_root, state["run_id"])
        doc = state["current_document"]
        doc_type = doc.get("type", doc.get("template", "WORKFLOW_SPEC"))

        doc_content = _load_transient(run_dir, "draft_content.md", "")

        lessons_content = load_lessons(project_root)
        if not lessons_content:
            doc["phase_status"] = "lessons_complete"
            # Save empty lessons result for G4 gate evaluation
            _save_transient(run_dir, "lessons_check_result.json", {
                "violations": [], "recommendations": [],
            })
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

        lessons_data = {
            "violations": [
                {"id": v.lesson_id, "description": v.description}
                for v in result.violations
            ],
            "recommendations": [
                {"id": r.lesson_id, "description": r.description}
                for r in result.recommendations
            ],
        }

        # Save to file for reference
        _save_transient(run_dir, "lessons_check_result.json", lessons_data)

        doc["phase_status"] = "lessons_complete"

        # G4 is auto-evaluated (no human)
        return state


class Phase5Handler(PhaseHandler):
    """Phase 5: Finalize — apply audit findings, present to human for approval.

    Loads audit results from Phase 3, extracts CRITICAL + IMPORTANT findings,
    calls Opus to apply them to the draft, then presents for human approval.
    Saves the document to output/{doc_name}. Gate G5 pauses for approval.
    """

    phase_id = "5"

    def execute(self, state: dict, context: dict) -> dict:
        from planner.phases.phase_5_finalize import present_for_approval

        project_root = context["project_root"]
        run_dir = _run_dir(project_root, state["run_id"])
        doc = state["current_document"]
        doc_name = doc.get("name", "document.md")

        doc_content = _load_transient(run_dir, "draft_content.md", "")

        # ── Apply audit findings before finalizing ──
        findings_applied = 0
        findings_text, findings_applied = _load_audit_findings(run_dir, doc_name)

        if findings_text and doc_content:
            gateway = _gateway_from_state(state)
            try:
                revised = _apply_audit_findings(
                    gateway, doc_content, findings_text, doc_name,
                    phase="5", document=doc_name,
                )
                if revised and revised.strip() != doc_content.strip():
                    doc_content = revised
                    _save_transient(run_dir, "draft_content.md", doc_content)
                    logger.info(f"Phase 5: applied {findings_applied} audit findings to {doc_name}")
                else:
                    logger.info("Phase 5: Opus returned unchanged document")
                    findings_applied = 0
            except Exception as e:
                logger.error(f"Phase 5: failed to apply audit findings, using original draft: {e}")
                findings_applied = 0

        changes_desc = (
            f"Audit findings applied: {findings_applied}"
            if findings_applied > 0
            else "Draft ready for review (no audit findings to apply)"
        )

        result = present_for_approval(
            doc_content=doc_content,
            document_name=doc_name,
            changes_description=changes_desc,
            doc_cost=state["cost"].get("by_document", {}).get(doc_name, 0.0),
            total_cost=state["cost"]["total_usd"],
            audit_resolved_count=findings_applied,
        )

        # Save finalize result to file
        _save_transient(run_dir, "finalize_result.json", {
            "summary": result.summary,
            "clean_content": result.clean_content,
        })

        # Update draft content with finalized version (includes AF markers for review)
        _save_transient(run_dir, "draft_content.md", result.content)

        # Save document to output/ for human review (CLI mode — no Telegram attachment)
        output_path = run_dir / "output" / doc_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.content, encoding="utf-8")

        # Print summary to stdout so gate-reply output includes it
        print(f"\n{result.summary}")
        print(f"\nDocument saved: {output_path}")

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
        run_dir = _run_dir(project_root, state["run_id"])
        doc = state["current_document"]
        doc_name = doc.get("name", "document.md")

        doc_content = _load_transient(run_dir, "draft_content.md", "")

        gateway = _gateway_from_state(state)
        existing_af = load_audit_findings(project_root)

        result = update_all_records(
            run_dir=str(run_dir),
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
        finalize = _load_transient(run_dir, "finalize_result.json", {})
        clean_content = finalize.get("clean_content", doc_content)
        output_path = run_dir / "output" / doc_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(clean_content, encoding="utf-8")

        # Reset current_document for next doc (or None if done)
        state["current_document"] = None

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
            from planner.entity_map import EntityEntry
            for doc_name, map_dict in raw_maps.items():
                em = EntityMap(document_name=doc_name)
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
            output_dir = run_dir / "output"
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
        output_dir = run_dir / "output"
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
            spec_content = _load_transient(run_dir, "draft_content.md", "")

        # Generate plan
        plan_result = generate_plan(
            spec_content=spec_content,
            gateway=gateway,
            constitution_rules=constitution_rules,
            phase="7",
        )

        plan_path = run_dir / "output" / "plan.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(plan_result.content, encoding="utf-8")

        # Generate tasks
        tasks_result = generate_tasks(
            plan_content=plan_result.content,
            spec_content=spec_content,
            gateway=gateway,
            phase="7",
        )

        tasks_path = run_dir / "output" / "tasks.md"
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
