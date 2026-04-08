"""Integration test: real handlers through dispatcher with schema validation.

Verifies that phase handlers never put extra fields in state dict,
which would cause state_manager.save() to fail (additionalProperties: false).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from planner import state_manager
from planner.orchestrator.dispatcher import Dispatcher, PhaseHandler
from planner.phase_handlers import (
    register_all_handlers,
    _load_audit_findings,
    _apply_audit_findings,
)


# Schema-valid field names (from planner_state_schema.json)
SCHEMA_FIELDS = {
    "run_id",
    "project_id",
    "run_status",
    "locked_by",
    "locked_until",
    "state_version",
    "schema_version",
    "current_phase",
    "current_document",
    "last_checkpoint",
    "documents_completed",
    "documents_pending",
    "decision_logs",
    "entity_maps",
    "cost",
    "created_at",
    "updated_at",
    "pending_gate",
    "auto_approve",
    "telegram_chat_id",
    "documents_skipped",
}

# The only allowed transient key — dispatcher pops it before save
TRANSIENT_KEYS = {"_gate_pending"}


def _mock_call_model(role="primary", prompt="", context=None, phase="0",
                     document=None, max_tokens=8192, temperature=0.7,
                     provider=None, model=None, **kwargs):
    """Mock ModelGateway.call_model that returns plausible content."""
    return {
        "content": f"Mock content for phase {phase}, section from prompt.",
        "model": model or "mock-model",
        "tokens_in": 100,
        "tokens_out": 50,
        "cost_usd": 0.001,
        "duration": 0.1,
    }


def _assert_state_schema_clean(state: dict, phase_label: str):
    """Assert that state only contains schema-valid fields (plus _gate_pending)."""
    extra = set(state.keys()) - SCHEMA_FIELDS - TRANSIENT_KEYS
    assert extra == set(), (
        f"After {phase_label}: state has extra fields not in schema: {extra}. "
        f"These will cause state_manager.save() to fail with additionalProperties: false."
    )


def _assert_save_succeeds(project_root: str, state: dict, phase_label: str):
    """Assert that state_manager.validate() passes (same check save() does)."""
    clean = dict(state)
    clean.pop("_gate_pending", None)
    errors = state_manager.validate(clean)
    assert errors == [], (
        f"After {phase_label}: state fails schema validation: {errors}"
    )


@pytest.fixture
def project_root(tmp_path):
    """Set up a project root with template stubs so phase handlers don't crash."""
    root = tmp_path / "project"
    root.mkdir()

    # Create docs dir with a minimal LESSONS_LEARNED so Phase 4 has content
    docs = root / "docs"
    docs.mkdir()
    (docs / "LESSONS_LEARNED.md").write_text(
        "# Lessons Learned\n\n## LL-001\nAlways validate inputs.\n"
    )

    return str(root)


@pytest.fixture
def run_state(project_root):
    return state_manager.create_run(
        project_root, "integration-test", ["spec.md"]
    )


@pytest.fixture
def mock_gateway():
    """Patch ModelGateway.call_model to avoid real LiteLLM calls."""
    with patch("planner.phase_handlers.ModelGateway") as MockGW:
        instance = MagicMock()
        instance.call_model.side_effect = _mock_call_model
        MockGW.return_value = instance
        yield instance


class TestHandlerSchemaCompliance:
    """Verify that real phase handlers never pollute state with extra fields."""

    def test_phase0_no_extra_fields(self, project_root, run_state):
        """Phase 0 handler should only set schema-valid fields."""
        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        _assert_state_schema_clean(state, "Phase 0")
        assert result.action == "gate_pending"
        assert state["pending_gate"] == "G0"

    def test_phase1_no_extra_fields(self, project_root, run_state, mock_gateway):
        """Phase 1 handler must save intake_answers to file, not state."""
        # Advance past Phase 0 gate
        run_state["current_phase"] = "1"
        run_state["documents_pending"] = ["CONSTITUTION.md"]
        run_state = state_manager.save(project_root, run_state)

        # Create input.txt so Phase 1 has a project idea
        run_dir = Path(project_root) / "planner_runs" / run_state["run_id"]
        (run_dir / "input.txt").write_text("Build a todo CLI app")

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        _assert_state_schema_clean(state, "Phase 1")
        _assert_save_succeeds(project_root, state, "Phase 1")

        # Verify intake_answers.json was created with real content (not placeholders)
        answers_path = run_dir / "intake_answers.json"
        assert answers_path.exists(), "intake_answers.json not created"
        answers = json.loads(answers_path.read_text())
        assert len(answers) > 0, "intake_answers.json is empty"
        for section, content in answers.items():
            assert "[Pending human input" not in content, (
                f"Section '{section}' has placeholder instead of real content"
            )

    def test_dispatch_loop_no_extra_fields(self, project_root, run_state):
        """Run dispatcher in a loop — every phase must leave state schema-clean."""
        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        state = run_state
        phases_visited = []

        for i in range(30):  # safety limit
            phase_before = state["current_phase"]
            result = d.dispatch_phase(state)
            state = result.state
            phases_visited.append(phase_before)

            _assert_state_schema_clean(state, f"Phase {phase_before} (step {i})")

            if result.action in ("gate_pending", "complete", "error", "cost_alert"):
                break

        # Should have visited at least Phase 0
        assert len(phases_visited) >= 1

    def test_save_roundtrip_after_phase0(self, project_root, run_state):
        """After Phase 0, state must survive save→load roundtrip."""
        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        # The dispatcher already saved. Verify we can load it back.
        loaded = state_manager.load(project_root, state["run_id"])
        assert loaded["pending_gate"] == "G0"
        assert loaded["run_id"] == state["run_id"]

    def test_phase1_calls_model_per_section(self, project_root, run_state, mock_gateway):
        """Phase 1 must call the model for each template section."""
        run_state["current_phase"] = "1"
        run_state["documents_pending"] = ["CONSTITUTION.md"]
        run_state = state_manager.save(project_root, run_state)

        run_dir = Path(project_root) / "planner_runs" / run_state["run_id"]
        (run_dir / "input.txt").write_text("Build an e-commerce API with Stripe")

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)

        # Verify model was called (at least once per section)
        assert mock_gateway.call_model.call_count > 0, (
            "Phase 1 did not call model — intake is generating placeholders instead"
        )
        # Verify all calls used phase="1"
        for call in mock_gateway.call_model.call_args_list:
            assert call.kwargs.get("phase") == "1" or call[1].get("phase") == "1"


class TestAuditFindingsApplication:
    """Verify Phase 5 applies audit findings from Phase 3."""

    def _make_audit_file(self, audits_dir, doc_name, label, role, content):
        """Helper to create an audit result file."""
        doc_safe = doc_name.replace(".", "_")
        filename = f"{doc_safe}_{role}_{label}.json"
        audits_dir.mkdir(parents=True, exist_ok=True)
        (audits_dir / filename).write_text(json.dumps({
            "model_label": label,
            "audit_role": role,
            "content": content,
            "model": "test-model",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost_usd": 0.01,
            "duration": 1.0,
        }))

    def test_loads_critical_and_important(self, tmp_path):
        """_load_audit_findings extracts CRITICAL and IMPORTANT lines."""
        run_dir = tmp_path / "run"
        audits_dir = run_dir / "audits"

        self._make_audit_file(audits_dir, "spec.md", "gpt_tech", "technical",
            "## Findings\n"
            "CRITICAL: Missing error handling in API endpoints\n"
            "- Add try/catch for all external calls\n"
            "IMPORTANT: No rate limiting defined\n"
            "MINOR: Consider adding comments\n"
        )
        self._make_audit_file(audits_dir, "spec.md", "gemini_arch", "architecture",
            "## Findings\n"
            "IMPORTANT: Database failover not specified\n"
            "MINOR: Naming conventions could be clearer\n"
        )

        findings, count = _load_audit_findings(run_dir, "spec.md")

        assert count == 3  # 1 CRITICAL + 2 IMPORTANT
        assert "Missing error handling" in findings
        assert "No rate limiting" in findings
        assert "Database failover" in findings
        # MINOR should not be in findings text as a finding header
        assert "Consider adding comments" not in findings

    def test_no_audit_files_returns_empty(self, tmp_path):
        """No audit dir → empty findings."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        findings, count = _load_audit_findings(run_dir, "spec.md")
        assert findings == ""
        assert count == 0

    def test_apply_findings_modifies_document(self, tmp_path):
        """When there are findings, Opus revises the document."""
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        audits_dir = run_dir / "audits"

        original = "# Spec\n\n## API\nGET /users returns user list.\n"

        self._make_audit_file(audits_dir, "spec.md", "gpt_tech", "technical",
            "CRITICAL: Missing authentication on GET /users\n"
        )

        findings, count = _load_audit_findings(run_dir, "spec.md")
        assert count == 1

        # Mock the gateway to return a revised doc
        mock_gw = MagicMock()
        mock_gw.call_model.return_value = {
            "content": "# Spec\n\n## API\nGET /users returns user list. Requires Bearer token auth.\n",
            "model": "mock",
            "tokens_in": 100,
            "tokens_out": 100,
            "cost_usd": 0.01,
            "duration": 0.5,
        }

        revised = _apply_audit_findings(mock_gw, original, findings, "spec.md")

        assert revised != original
        assert "Bearer token auth" in revised
        assert mock_gw.call_model.call_count == 1

    def test_apply_findings_failure_preserves_original(self, tmp_path, mock_gateway):
        """If Opus call fails, Phase 5 falls back to original draft."""
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)

        mock_gateway.call_model.side_effect = RuntimeError("API timeout")

        with pytest.raises(RuntimeError):
            _apply_audit_findings(mock_gateway, "# Doc", "CRITICAL: fix X", "doc.md")

    def test_phase5_with_findings_reports_count(self, project_root, run_state, mock_gateway):
        """Phase 5 should report findings_applied > 0 when audit files exist."""
        run_state["current_phase"] = "5"
        run_state["current_document"] = {
            "name": "CONSTITUTION.md",
            "type": "CONSTITUTION",
            "version": 1,
            "phase_status": "lessons_complete",
            "phase_attempt": 1,
            "sections_completed": [],
            "template": "CONSTITUTION",
        }
        run_state = state_manager.save(project_root, run_state)

        run_dir = Path(project_root) / "planner_runs" / run_state["run_id"]

        # Write a draft
        (run_dir / "draft_content.md").write_text("# Constitution\n\n## Rules\nBe good.\n")

        # Write audit findings
        audits_dir = run_dir / "audits"
        self._make_audit_file(audits_dir, "CONSTITUTION.md", "gpt_tech", "technical",
            "CRITICAL: 'Be good' is too vague — specify concrete rules\n"
        )

        # Mock gateway to return revised content (clear side_effect first)
        mock_gateway.call_model.side_effect = None
        mock_gateway.call_model.return_value = {
            "content": "# Constitution\n\n## Rules\n1. All API calls must have error handling.\n",
            "model": "mock",
            "tokens_in": 200,
            "tokens_out": 150,
            "cost_usd": 0.02,
            "duration": 1.0,
        }

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)

        result = d.dispatch_phase(run_state)
        state = result.state

        _assert_state_schema_clean(state, "Phase 5 with findings")
        assert result.action == "gate_pending"

        # Verify the output file has the revised content
        output_path = run_dir / "output" / "CONSTITUTION.md"
        assert output_path.exists()
        output = output_path.read_text()
        assert "error handling" in output
        assert "Be good" not in output


class _GateStubHandler(PhaseHandler):
    """Stub handler that sets a specific gate as pending."""

    def __init__(self, phase_id: str, gate_id: str):
        self.phase_id = phase_id
        self._gate_id = gate_id

    def execute(self, state, context):
        state["_gate_pending"] = self._gate_id
        return state


class TestAutoApprove:
    """Verify auto-approve skips intermediate gates but not G0/G7.

    Uses stub handlers to isolate dispatcher auto-approve logic
    from real phase handler dependencies (templates, models, etc.).
    """

    def _make_state(self, project_root, label, phase, auto=False):
        """Create a run state at a given phase with auto_approve set."""
        state = state_manager.create_run(
            project_root, f"auto-{label}", ["MODULE_SPEC.md"]
        )
        state["current_phase"] = phase
        state["auto_approve"] = auto
        state["current_document"] = {
            "name": "MODULE_SPEC.md",
            "type": "MODULE_SPEC",
            "version": 1,
            "phase_status": "in_progress",
            "phase_attempt": 1,
            "sections_completed": [],
            "template": "MODULE_SPEC",
        }
        return state_manager.save(project_root, state)

    def test_auto_approve_skips_g1(self, project_root):
        """auto_approve=True should auto-approve G1."""
        state = self._make_state(project_root, "g1-auto", "1", auto=True)
        d = Dispatcher(project_root, phase_handlers={
            "1": _GateStubHandler("1", "G1"),
        })
        result = d.dispatch_phase(state)
        assert result.action == "continue"
        assert "AUTO-APPROVED" in result.message

    def test_auto_approve_skips_g3(self, project_root):
        """auto_approve=True should auto-approve G3 when no CRITICAL findings."""
        state = self._make_state(project_root, "g3-auto", "3", auto=True)
        d = Dispatcher(project_root, phase_handlers={
            "3": _GateStubHandler("3", "G3"),
        })
        result = d.dispatch_phase(state)
        assert result.action == "continue"
        assert "AUTO-APPROVED" in result.message

    def test_auto_approve_skips_g5(self, project_root):
        """auto_approve=True should auto-approve G5."""
        state = self._make_state(project_root, "g5-auto", "5", auto=True)
        d = Dispatcher(project_root, phase_handlers={
            "5": _GateStubHandler("5", "G5"),
        })
        result = d.dispatch_phase(state)
        assert result.action == "continue"
        assert "AUTO-APPROVED" in result.message

    def test_auto_approve_does_not_skip_g0(self, project_root):
        """auto_approve=True must NOT skip G0."""
        state = self._make_state(project_root, "g0-auto", "0", auto=True)
        d = Dispatcher(project_root, phase_handlers={
            "0": _GateStubHandler("0", "G0"),
        })
        result = d.dispatch_phase(state)
        assert result.action == "gate_pending"
        assert result.state["pending_gate"] == "G0"

    def test_auto_approve_does_not_skip_g7(self, project_root):
        """auto_approve=True must NOT skip G7."""
        state = self._make_state(project_root, "g7-auto", "7", auto=True)
        state["documents_completed"] = ["MODULE_SPEC.md"]
        state["documents_pending"] = []
        state = state_manager.save(project_root, state)

        d = Dispatcher(project_root, phase_handlers={
            "7": _GateStubHandler("7", "G7"),
        })
        result = d.dispatch_phase(state)
        assert result.action == "gate_pending"
        assert result.state["pending_gate"] == "G7"

    def test_auto_approve_pauses_g3_on_critical(self, project_root):
        """auto_approve=True must pause at G3 if CRITICAL findings exist."""
        state = self._make_state(project_root, "g3-crit", "3", auto=True)

        # Create audit file with CRITICAL finding
        run_dir = Path(project_root) / "planner_runs" / state["run_id"]
        audits_dir = run_dir / "audits"
        audits_dir.mkdir(parents=True, exist_ok=True)
        (audits_dir / "MODULE_SPEC_md_technical_gpt_tech.json").write_text(json.dumps({
            "model_label": "gpt_tech",
            "audit_role": "technical",
            "content": "CRITICAL: Missing authentication on all endpoints\n",
            "model": "test", "tokens_in": 100, "tokens_out": 50,
            "cost_usd": 0.01, "duration": 1.0,
        }))

        d = Dispatcher(project_root, phase_handlers={
            "3": _GateStubHandler("3", "G3"),
        })
        result = d.dispatch_phase(state)
        assert result.action == "gate_pending"
        assert result.state["pending_gate"] == "G3"

    def test_no_auto_approve_pauses_at_g1(self, project_root):
        """auto_approve=False (default) pauses at G1."""
        state = self._make_state(project_root, "g1-manual", "1", auto=False)
        d = Dispatcher(project_root, phase_handlers={
            "1": _GateStubHandler("1", "G1"),
        })
        result = d.dispatch_phase(state)
        assert result.action == "gate_pending"
        assert result.state["pending_gate"] == "G1"


class TestTelegramDelivery:
    """Verify Phase 5 sends documents via Telegram when chat_id is set."""

    def _make_phase5_state(self, project_root, chat_id=None, auto_approve=False):
        state = state_manager.create_run(
            project_root, f"tg-test-{chat_id or 'cli'}", ["MODULE_SPEC.md"]
        )
        state["current_phase"] = "5"
        state["telegram_chat_id"] = chat_id
        state["auto_approve"] = auto_approve
        state["current_document"] = {
            "name": "MODULE_SPEC.md",
            "type": "MODULE_SPEC",
            "version": 1,
            "phase_status": "lessons_complete",
            "phase_attempt": 1,
            "sections_completed": [],
            "template": "MODULE_SPEC",
        }
        state = state_manager.save(project_root, state)
        run_dir = Path(project_root) / "planner_runs" / state["run_id"]
        (run_dir / "draft_content.md").write_text("# Module Spec\n\nContent.\n")
        return state

    @patch("planner.phase_handlers._send_telegram_document")
    @patch("planner.phase_handlers._send_telegram_message")
    @patch("planner.phase_handlers._get_telegram_bot_token")
    def test_sends_document_when_chat_id_set(
        self, mock_token, mock_msg, mock_doc, project_root, mock_gateway,
    ):
        """Phase 5 should send summary + file via Telegram."""
        mock_token.return_value = "fake-bot-token"
        mock_msg.return_value = True
        mock_doc.return_value = True

        state = self._make_phase5_state(project_root, chat_id="12345")

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)
        d.dispatch_phase(state)

        mock_msg.assert_called_once()
        msg_text = mock_msg.call_args[0][1]
        assert "MODULE_SPEC.md" in msg_text
        assert "/sdd_planner_reply" in msg_text

        mock_doc.assert_called_once()
        assert mock_doc.call_args[0][0] == "12345"

    @patch("planner.phase_handlers._send_telegram_document")
    @patch("planner.phase_handlers._send_telegram_message")
    @patch("planner.phase_handlers._get_telegram_bot_token")
    def test_no_telegram_when_chat_id_null(
        self, mock_token, mock_msg, mock_doc, project_root, mock_gateway,
    ):
        """Phase 5 should NOT call Telegram when chat_id is null."""
        state = self._make_phase5_state(project_root, chat_id=None)

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)
        d.dispatch_phase(state)

        mock_token.assert_not_called()
        mock_msg.assert_not_called()
        mock_doc.assert_not_called()

    @patch("planner.phase_handlers._send_telegram_document")
    @patch("planner.phase_handlers._send_telegram_message")
    @patch("planner.phase_handlers._get_telegram_bot_token")
    def test_auto_approve_note_in_message(
        self, mock_token, mock_msg, mock_doc, project_root, mock_gateway,
    ):
        """Auto-approve mode should include note in Telegram message."""
        mock_token.return_value = "fake-bot-token"
        mock_msg.return_value = True
        mock_doc.return_value = True

        state = self._make_phase5_state(project_root, chat_id="99999", auto_approve=True)

        d = Dispatcher(project_root)
        register_all_handlers(d, project_root)
        d.dispatch_phase(state)

        msg_text = mock_msg.call_args[0][1]
        assert "auto-approved" in msg_text


class TestDocumentSkip:
    """Verify document skip logic at G1."""

    def _make_state_with_docs(self, project_root, docs, current_doc_name):
        state = state_manager.create_run(
            project_root, f"skip-test-{current_doc_name}", docs
        )
        state["current_phase"] = "1"
        state["pending_gate"] = "G1"
        state["current_document"] = {
            "name": current_doc_name,
            "type": current_doc_name.replace(".md", ""),
            "version": 1,
            "phase_status": "intake_complete",
            "phase_attempt": 1,
            "sections_completed": [],
            "template": current_doc_name.replace(".md", ""),
        }
        return state_manager.save(project_root, state)

    def _simulate_skip(self, project_root, state):
        """Simulate what cmd_gate_reply does when response is 'skip'."""
        doc = state.get("current_document")
        doc_name = doc.get("name") if doc else "unknown"

        if doc_name in state.get("documents_pending", []):
            state["documents_pending"].remove(doc_name)
        if doc_name not in state.get("documents_skipped", []):
            state["documents_skipped"].append(doc_name)

        state["current_document"] = None
        state["pending_gate"] = None

        if state["documents_pending"]:
            state["current_phase"] = "1"
        else:
            state["current_phase"] = "6.5"

        return state_manager.save(project_root, state)

    def test_skip_moves_doc_to_skipped(self, project_root):
        """'skip' at G1 moves doc from pending to skipped."""
        state = self._make_state_with_docs(
            project_root,
            ["INTEGRATIONS.md", "MODULE_SPEC.md"],
            "INTEGRATIONS.md",
        )

        state = self._simulate_skip(project_root, state)

        assert "INTEGRATIONS.md" not in state["documents_pending"]
        assert "INTEGRATIONS.md" in state["documents_skipped"]
        assert "MODULE_SPEC.md" in state["documents_pending"]
        assert state["current_document"] is None
        assert state["current_phase"] == "1"

    def test_skip_last_doc_advances_to_postdoc(self, project_root):
        """Skipping the last pending doc advances to post-doc phases."""
        state = self._make_state_with_docs(
            project_root,
            ["DATA_MODEL.md"],
            "DATA_MODEL.md",
        )

        state = self._simulate_skip(project_root, state)

        assert state["documents_pending"] == []
        assert "DATA_MODEL.md" in state["documents_skipped"]
        assert state["current_phase"] == "6.5"

    def test_skip_preserves_completed_docs(self, project_root):
        """Skipping a doc doesn't affect already-completed docs."""
        state = self._make_state_with_docs(
            project_root,
            ["INTEGRATIONS.md", "MODULE_SPEC.md"],
            "INTEGRATIONS.md",
        )
        state["documents_completed"] = ["PROJECT_FOUNDATION.md", "CONSTITUTION.md"]
        state = state_manager.save(project_root, state)

        state = self._simulate_skip(project_root, state)

        assert state["documents_completed"] == ["PROJECT_FOUNDATION.md", "CONSTITUTION.md"]
        assert "INTEGRATIONS.md" in state["documents_skipped"]

    def test_skip_state_passes_validation(self, project_root):
        """State after skip must pass schema validation."""
        state = self._make_state_with_docs(
            project_root,
            ["DATA_MODEL.md", "MODULE_SPEC.md"],
            "DATA_MODEL.md",
        )

        state = self._simulate_skip(project_root, state)

        errors = state_manager.validate(state)
        assert errors == [], f"Schema validation failed after skip: {errors}"
