"""E2E tests — validate full system across multiple scenarios (TASK-040).

Scenarios:
1. New project: /plan → full run, all modules work together
2. Existing project module: context loading + spec only
3. Monolith extraction: parse → map → confidence → review
4. PII hit: scanner catches secrets, blocks
5. Audit conflict: disagreement between models
6. Re-entry: reconcile → impact → patch → delta tasks
"""

import json
import pytest
from pathlib import Path

from planner import state_manager
from planner.cost_tracker import log_call, get_summary
from planner.filter_for_agent import filter_for_agent
from planner.model_gateway import ModelGateway
from planner.validators.document_validator import validate as validate_doc
from planner.orchestrator.dispatcher import Dispatcher
from planner.orchestrator.gates import GateEngine
from planner.orchestrator.checkpoint import CheckpointManager
from planner.phases.phase_0_setup import run_phase_0, FOUNDATION_DOCS
from planner.phases.phase_1_intake import IntakeSession
from planner.template_loader import TemplateSection, extract_sections
from planner.phases.phase_1_5_ideation import ideate, should_skip
from planner.phases.phase_2_draft import draft_document
from planner.phases.phase_2_5_preaudit import check_against_af, AFEntry
from planner.phases.phase_3_audit import run_audit
from planner.audit_triage import triage
from planner.delta_audit import classify_change, should_full_reaudit
from planner.phases.phase_4_lessons import check_lessons
from planner.phases.phase_5_finalize import present_for_approval, remove_af_markers
from planner.decision_log import archive_history, build_log
from planner.entity_map import extract_entities
from planner.phases.phase_6_5_crossdoc import validate_entities
from planner.phases.phase_7_plan import generate_plan
from planner.phases.phase_7_tasks import generate_tasks
from planner.task_validator import validate_tasks
from planner.pii_scanner import scan as pii_scan
from planner.monolith.parser import parse_document
from planner.monolith.mapper import map_blocks
from planner.monolith.confidence import score_all, get_review_needed
from planner.reentry.impact import build_graph, compute_impact
from planner.reentry.coordinator import run_plan_fix
from planner.telegram.handler import TelegramHandler


def _mock_gateway_fn(model, messages, max_tokens, temperature):
    return {"content": "Mock response. No issues found. Correct.", "tokens_in": 100, "tokens_out": 50}


VALID_TASKS = """# tasks.md
### TASK-001: Setup
- Objective: Create dirs
- Inputs: spec §1
- Outputs: Dir tree
- Files touched: src/__init__.py
- Done when: dirs exist
- depends_on: []
- if_blocked: MINOR: fix
- Estimated: 15 min
"""


class TestE2E_NewProject:
    """Scenario 1: /plan 'build a CLI todo app' → full run."""

    def test_full_new_project_flow(self, tmp_path):
        project_root = str(tmp_path)

        # Phase 0: Setup
        setup = run_phase_0(project_root, doc_type="MODULE_SPEC")
        assert setup.mode == "new_project"
        assert len(setup.documents_pending) > 0

        # Create run
        state = state_manager.create_run(
            project_root, "todo-app", setup.documents_pending,
        )
        assert state["run_status"] == "active"

        # Phase 1: Intake (simulated — one section)
        sections = [TemplateSection(2, "Purpose", "Describe purpose")]
        session = IntakeSession("MODULE_SPEC", sections)
        session.get_next_prompt()
        session.record_answer("Build a CLI todo app for personal task management")
        result = session.confirm_section(True)
        assert session.is_complete
        assert len(session.answers) == 1

        # Phase 2: Draft
        gw = ModelGateway(state, call_fn=lambda *a: {
            "content": "# MODULE_SPEC — Todo CLI\n\nPersonal task management app.\n\n## 1. Purpose\nBuild a CLI todo app.\n\n## 2. Stack\nPython, SQLite.",
            "tokens_in": 200, "tokens_out": 500,
        })
        draft = draft_document("MODULE_SPEC", "## 1. Purpose\n## 2. Stack", session.answers, gw)
        assert draft.validation_passed
        assert "todo" in draft.content.lower()

        # Phase 3: Audit (4 calls)
        audit_result = run_audit(
            draft.content, "MODULE_SPEC", {
                "current_document": {"content": draft.content, "type": "MODULE_SPEC"},
                "constitution": {"rules": []},
                "project_context": {"stack": {}, "integrations_summary": ""},
                "cross_references": [],
                "cost": state["cost"],
            },
            gw, state["run_id"], project_root, backoff=False,
        )
        assert len(audit_result.call_results) == 4

        # Phase 5: Finalize
        final = present_for_approval(draft.content, "spec.md", "Initial draft", 1.0, 2.0)
        assert "Approve" in final.summary

        # Phase 6: Records
        archive_path = archive_history(
            str(tmp_path / "planner_runs" / state["run_id"]),
            "spec.md", [{"role": "user", "content": "build todo app"}],
        )
        assert Path(archive_path).exists()

        # Entity map
        em = extract_entities(draft.content, "spec.md")
        assert em.document_name == "spec.md"

        # Cost tracked
        summary = get_summary(state)
        assert summary["total_usd"] > 0


class TestE2E_ExistingProject:
    """Scenario 2: Add module to existing project with context."""

    def test_existing_project_loads_context(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        for doc in FOUNDATION_DOCS:
            (docs / doc).write_text(f"# {doc}\nExisting content.")

        setup = run_phase_0(str(tmp_path), doc_type="MODULE_SPEC")
        assert setup.mode == "existing_project"
        assert len(setup.context_loaded) == len(FOUNDATION_DOCS)
        assert setup.documents_pending == ["MODULE_SPEC.md"]


class TestE2E_MonolithExtraction:
    """Scenario 3: Parse monolith → map → confidence → review."""

    def test_monolith_pipeline(self):
        monolith = """# Big Doc
## Database
Tables: users, orders. Foreign keys everywhere.
Schema with user_id UUID and indexes.

## API
POST /api/users, GET /api/orders.
Integration with Stripe webhook.

## Rules
Never retry without diagnosis. Must validate all input.
"""
        blocks = parse_document(monolith)
        assert len(blocks) >= 3

        mappings = map_blocks(blocks)
        assert len(mappings) == len(blocks)

        results = score_all(mappings)
        review_needed = get_review_needed(results)
        # Some blocks should be confident, some may need review
        assert len(results) == len(blocks)


class TestE2E_PIIHit:
    """Scenario 4: Scanner catches secrets, blocks."""

    def test_pii_blocks_content(self):
        content = """# My Doc
API key: sk-abc123def456ghi789jkl012mnopqrstuv
Password: super_secret_pass123456
Email: user@example.com
"""
        result = pii_scan(content)
        assert result.has_blockers
        assert len(result.high_confidence_hits) >= 1


class TestE2E_AuditConflict:
    """Scenario 5: Disagreement between models → conflict flag."""

    def test_conflict_detection(self):
        from planner.audit_triage import Finding, detect_conflicts
        findings = [
            Finding("CRITICAL", "§3", "Missing database connection pooling required", "Add pooling now", "gpt_tech"),
            Finding("MINOR", "§3", "Database connection pooling is optional at this scale", "Skip pooling", "gemini_tech"),
        ]
        conflicts = detect_conflicts(findings)
        assert len(conflicts) >= 1


class TestE2E_ReEntry:
    """Scenario 6: Re-entry from Code blocker."""

    def test_reentry_flow(self, tmp_path):
        tasks = """# tasks.md
### TASK-001: Setup
- depends_on: []
- Files touched: src/__init__.py

### TASK-002: Build API
- depends_on: [TASK-001]
- Files touched: src/api.py

### TASK-003: Tests
- depends_on: [TASK-002]
- Files touched: src/tests.py
"""
        spec = "# Spec\n## Purpose\nBuild API."

        # Create a file so reconciler finds something
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__init__.py").write_text("")

        gw_fn = lambda *a: {"content": "Patched. No issues. Correct. Delta tasks.", "tokens_in": 100, "tokens_out": 50}

        class SimpleGW:
            def call_model(self, **kw):
                return {"content": "Patched spec. No issues found. Correct.", "tokens_in": 100, "tokens_out": 50}

        result = run_plan_fix(str(tmp_path), tasks, spec, "TASK-001", "Auth broken", SimpleGW())
        assert len(result.impact_summary) > 0
        assert result.patched_spec


class TestE2E_TaskValidation:
    """Cross-cutting: task validator works on real-format tasks."""

    def test_validates_well_formed_tasks(self):
        result = validate_tasks(VALID_TASKS)
        assert result.passed
        assert result.total_tasks == 1


class TestE2E_CostTracking:
    """Cross-cutting: cost accumulates correctly across phases."""

    def test_cost_accumulates(self):
        state = {
            "cost": {"total_usd": 0.0, "by_model": {}, "by_phase": {}, "by_document": {}},
        }
        log_call(state, "claude-opus-4-6", 1000, 500, 2.0, "1", "doc.md")
        log_call(state, "gpt-5.4", 800, 400, 1.5, "3", "doc.md")
        log_call(state, "gemini-3.1-pro", 600, 300, 1.0, "3", "doc.md")
        summary = get_summary(state)
        assert summary["total_usd"] > 0
        assert len(summary["by_model"]) == 3
        assert len(summary["by_phase"]) == 2
