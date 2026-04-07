"""Tests for telegram/handler.py — TASK-010."""

import pytest

from planner import state_manager
from planner.telegram.handler import TelegramHandler, HELP_TEXT


@pytest.fixture
def project_root(tmp_path):
    return str(tmp_path)


@pytest.fixture
def sent_messages():
    messages = []
    def send_fn(chat_id, text, **kwargs):
        messages.append({"chat_id": chat_id, "text": text, **kwargs})
    return messages, send_fn


@pytest.fixture
def handler(project_root, sent_messages):
    messages, send_fn = sent_messages
    return TelegramHandler(project_root=project_root, send_fn=send_fn), messages


class TestCommandRouting:
    def test_plan_command(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan Build a todo CLI app")
        assert result["action"] == "plan_started"
        assert "run_id" in result

    def test_plan_no_description(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan")
        assert result["action"] == "error"
        assert any("Usage" in m["text"] for m in msgs)

    def test_plan_from_docs(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan-from-docs", attachments=["file1.md"])
        assert result["action"] == "plan_from_docs_started"
        assert result["files"] == 1

    def test_plan_from_docs_no_attachments(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan-from-docs")
        assert result["action"] == "error"
        assert any("attach" in m["text"].lower() for m in msgs)

    def test_plan_status_no_runs(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan-status")
        assert result["action"] == "status"

    def test_plan_status_specific_run(self, handler, project_root):
        h, msgs = handler
        state = state_manager.create_run(project_root, "test", ["DOC.md"])
        result = h.handle_message(123, f"/plan-status {state['run_id']}")
        assert result["action"] == "status"
        assert "info" in result

    def test_plan_resume_no_runs(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan-resume")
        assert result["action"] == "error"

    def test_plan_fix_missing_args(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan-fix")
        assert result["action"] == "error"
        assert any("Usage" in m["text"] for m in msgs)

    def test_plan_fix_with_args(self, handler, project_root):
        h, msgs = handler
        state = state_manager.create_run(project_root, "fix-test", ["DOC.md"])
        result = h.handle_message(123, f"/plan-fix {state['run_id']} TASK-007")
        assert result["action"] == "plan_fix_started"
        assert result["task_id"] == "TASK-007"

    def test_plan_af_approve(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan-af-approve AF-001")
        assert result["action"] == "af_approved"
        assert result["af_id"] == "AF-001"

    def test_plan_af_approve_no_id(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/plan-af-approve")
        assert result["action"] == "error"

    def test_unknown_command_sends_help(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "/unknown")
        assert result["action"] == "help"
        assert len(msgs) > 0

    def test_plain_text_sends_help(self, handler):
        h, msgs = handler
        result = h.handle_message(123, "hello there")
        assert result["action"] == "help"


class TestPlanCommand:
    def test_creates_run(self, handler, project_root):
        h, msgs = handler
        result = h.handle_message(123, "/plan Build a weather app")
        run_id = result["run_id"]
        runs = state_manager.list_runs(project_root)
        assert any(r["run_id"] == run_id for r in runs)

    def test_blocks_duplicate_project(self, handler):
        h, msgs = handler
        h.handle_message(123, "/plan First project")
        result = h.handle_message(123, "/plan Second project")
        assert result["action"] == "error"
        assert any("active run" in m["text"].lower() for m in msgs)

    def test_saves_input(self, handler, project_root):
        h, msgs = handler
        result = h.handle_message(123, "/plan Build a CLI tool")
        from pathlib import Path
        input_file = Path(project_root) / "planner_runs" / result["run_id"] / "input.txt"
        assert input_file.exists()
        assert "CLI tool" in input_file.read_text()


class TestPlanResume:
    def test_resume_latest(self, handler, project_root):
        h, msgs = handler
        state = state_manager.create_run(project_root, "resume-proj", ["DOC.md"])
        # Release any lock so resume can acquire
        if state["locked_by"]:
            state_manager.release_lock(project_root, state)
        result = h.handle_message(999, "/plan-resume")
        assert result["action"] == "plan_resumed"

    def test_resume_specific(self, handler, project_root):
        h, msgs = handler
        state = state_manager.create_run(project_root, "resume-proj2", ["DOC.md"])
        result = h.handle_message(999, f"/plan-resume {state['run_id']}")
        assert result["action"] == "plan_resumed"
        assert result["run_id"] == state["run_id"]


class TestPlanStatus:
    def test_status_lists_all(self, handler, project_root):
        h, msgs = handler
        state_manager.create_run(project_root, "proj-a", [])
        state_manager.create_run(project_root, "proj-b", [])
        result = h.handle_message(123, "/plan-status")
        assert len(result["runs"]) == 2

    def test_status_with_cost(self, handler, project_root):
        h, msgs = handler
        state = state_manager.create_run(project_root, "cost-proj", [])
        state["cost"]["total_usd"] = 5.50
        state_manager.save(project_root, state)
        result = h.handle_message(123, f"/plan-status {state['run_id']}")
        assert result["info"]["cost_total"] == 5.50
