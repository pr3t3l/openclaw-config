"""Tests for telegram/files.py and telegram/keyboards.py — TASK-012."""

import pytest
from pathlib import Path

from planner.telegram.files import TelegramFiles
from planner.telegram.keyboards import (
    build_approval_keyboard,
    build_confirm_keyboard,
    build_conflict_keyboard,
    build_continue_keyboard,
    is_approval,
    is_free_text_needed,
    is_rejection,
    parse_callback,
)


RUN_ID = "RUN-20260406-001"


class TestTelegramFilesSendSmart:
    def test_short_content_inline(self):
        sent = []
        def send_msg(chat_id, text, **kw):
            sent.append(("msg", chat_id, text))

        tf = TelegramFiles(send_message_fn=send_msg)
        result = tf.send_document_smart(123, "Short content", "doc.md", "Summary")
        assert result["method"] == "inline"
        assert len(sent) == 1
        assert sent[0][2] == "Short content"

    def test_long_content_as_file(self):
        sent_msgs = []
        sent_docs = []
        def send_msg(chat_id, text, **kw):
            sent_msgs.append(text)
        def send_doc(chat_id, file_path, caption):
            sent_docs.append((file_path, caption))

        tf = TelegramFiles(send_message_fn=send_msg, send_document_fn=send_doc)
        long_content = "x" * 4000
        result = tf.send_document_smart(123, long_content, "BIG.md", "Summary here")
        assert result["method"] == "file"
        assert result["filename"] == "BIG.md"
        # Summary sent as message
        assert sent_msgs[0] == "Summary here"
        # File sent as document
        assert len(sent_docs) == 1
        assert "BIG.md" in sent_docs[0][1]

    def test_file_written_to_disk(self):
        tf = TelegramFiles()
        result = tf.send_document_smart(123, "x" * 4000, "test.md", "Summary")
        assert Path(result["file_path"]).exists()
        assert Path(result["file_path"]).read_text() == "x" * 4000


class TestTelegramFilesReceive:
    def test_receive_file(self, tmp_path):
        def download(file_id, dest):
            Path(dest).write_text("file content")
            return dest

        tf = TelegramFiles(download_file_fn=download)
        path = tf.receive_file("abc123", str(tmp_path), "uploaded.md")
        assert Path(path).exists()
        assert Path(path).read_text() == "file content"

    def test_receive_creates_dir(self, tmp_path):
        dest = str(tmp_path / "new_subdir")
        tf = TelegramFiles()
        path = tf.receive_file("abc", dest, "file.md")
        assert Path(dest).exists()


class TestApprovalKeyboard:
    def test_has_three_buttons(self):
        kb = build_approval_keyboard(RUN_ID, "G5")
        assert len(kb[0]) == 3

    def test_button_text(self):
        kb = build_approval_keyboard(RUN_ID, "G5")
        texts = [b["text"] for b in kb[0]]
        assert "✅ Approve" in texts
        assert "🔄 Another round" in texts
        assert "❌ Start over" in texts

    def test_callback_data_format(self):
        kb = build_approval_keyboard(RUN_ID, "G5")
        for btn in kb[0]:
            assert RUN_ID in btn["callback_data"]
            assert "G5" in btn["callback_data"]


class TestConfirmKeyboard:
    def test_has_two_buttons(self):
        kb = build_confirm_keyboard(RUN_ID, "G0")
        assert len(kb[0]) == 2


class TestConflictKeyboard:
    def test_has_three_options(self):
        kb = build_conflict_keyboard(RUN_ID, "G3")
        all_buttons = [b for row in kb for b in row]
        assert len(all_buttons) == 3
        texts = [b["text"] for b in all_buttons]
        assert any("GPT" in t for t in texts)
        assert any("Gemini" in t for t in texts)
        assert any("Something else" in t for t in texts)


class TestContinueKeyboard:
    def test_has_two_buttons(self):
        kb = build_continue_keyboard(RUN_ID)
        assert len(kb[0]) == 2


class TestParseCallback:
    def test_parse_approval(self):
        cb = parse_callback(f"approve:{RUN_ID}:G5:yes")
        assert cb["action"] == "approve"
        assert cb["run_id"] == RUN_ID
        assert cb["gate_id"] == "G5"
        assert cb["choice"] == "yes"

    def test_parse_conflict(self):
        cb = parse_callback(f"conflict:{RUN_ID}:G3:gpt")
        assert cb["action"] == "conflict"
        assert cb["choice"] == "gpt"

    def test_parse_minimal(self):
        cb = parse_callback("action")
        assert cb["action"] == "action"
        assert cb["run_id"] == ""


class TestCallbackHelpers:
    def test_is_approval(self):
        assert is_approval({"action": "approve", "choice": "yes"})
        assert not is_approval({"action": "approve", "choice": "revise"})
        assert not is_approval({"action": "confirm", "choice": "yes"})

    def test_is_rejection(self):
        assert is_rejection({"action": "approve", "choice": "restart"})
        assert not is_rejection({"action": "approve", "choice": "yes"})

    def test_is_free_text_needed(self):
        assert is_free_text_needed({"choice": "other"})
        assert not is_free_text_needed({"choice": "gpt"})
