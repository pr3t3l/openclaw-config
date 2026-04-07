"""Telegram file handling — send/receive .md file attachments.

See spec.md §7.3: documents >3500 chars sent as .md file + inline summary.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from planner.telegram.formatter import should_send_as_file, truncate_for_telegram

logger = logging.getLogger(__name__)


class TelegramFiles:
    """Handles sending .md files and receiving file attachments via Telegram."""

    def __init__(
        self,
        send_message_fn: Optional[Callable] = None,
        send_document_fn: Optional[Callable] = None,
        download_file_fn: Optional[Callable] = None,
    ) -> None:
        """
        Args:
            send_message_fn: Send text message. Signature: (chat_id, text, **kwargs) -> None
            send_document_fn: Send file. Signature: (chat_id, file_path, caption) -> None
            download_file_fn: Download file. Signature: (file_id, dest_path) -> str
        """
        self._send_message = send_message_fn or self._noop
        self._send_document = send_document_fn or self._noop
        self._download_file = download_file_fn or self._noop_download

    def send_document_smart(
        self,
        chat_id: int,
        content: str,
        filename: str,
        summary: str,
        **kwargs: Any,
    ) -> dict:
        """Send content as inline text or .md file based on length.

        If content > 3500 chars: sends summary inline + .md file attachment.
        Otherwise: sends content inline.

        Args:
            chat_id: Telegram chat ID.
            content: Full document content.
            filename: Filename for the attachment (e.g., "CONSTITUTION.md").
            summary: Short summary for inline display.

        Returns:
            Dict with delivery method used and details.
        """
        if should_send_as_file(content):
            # Send inline summary
            self._send_message(chat_id, summary, **kwargs)

            # Send .md file
            file_path = self._write_temp_file(content, filename)
            self._send_document(chat_id, file_path, f"📎 {filename}")

            return {
                "method": "file",
                "filename": filename,
                "file_path": file_path,
                "content_length": len(content),
            }
        else:
            # Send inline
            self._send_message(chat_id, content, **kwargs)
            return {
                "method": "inline",
                "content_length": len(content),
            }

    def receive_file(
        self,
        file_id: str,
        dest_dir: str,
        filename: Optional[str] = None,
    ) -> str:
        """Download a file from Telegram.

        Args:
            file_id: Telegram file_id.
            dest_dir: Directory to save the file.
            filename: Optional filename override.

        Returns:
            Path to the downloaded file.
        """
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
        if filename:
            dest_file = str(dest_path / filename)
        else:
            dest_file = str(dest_path / f"upload_{file_id}")
        return self._download_file(file_id, dest_file)

    def _write_temp_file(self, content: str, filename: str) -> str:
        """Write content to a temporary .md file."""
        tmp_dir = Path(tempfile.gettempdir()) / "planner_files"
        tmp_dir.mkdir(exist_ok=True)
        file_path = tmp_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return str(file_path)

    @staticmethod
    def _noop(*args: Any, **kwargs: Any) -> None:
        pass

    @staticmethod
    def _noop_download(file_id: str, dest: str) -> str:
        return dest
