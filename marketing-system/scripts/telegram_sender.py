"""Shared Telegram sender for the marketing system."""

import json
import os
import subprocess
from pathlib import Path

CONFIG_PATH = Path("/home/robotin/.openclaw/marketing-system/config/telegram_security.json")
ENV_PATH = Path("/home/robotin/.openclaw/.env")


def _load_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        return token
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("TELEGRAM_BOT_TOKEN not found")


def _load_chat_id() -> str:
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
        ids = config.get("allowed_user_ids", [])
        if ids:
            return ids[0]
    return "8024871665"


def send_message(text: str, parse_mode: str = None) -> bool:
    """Send a message to Telegram. Returns True on success."""
    token = _load_bot_token()
    chat_id = _load_chat_id()
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Truncate if needed
    if len(text) > 4000:
        text = text[:3990] + "\n…(truncado)"

    cmd = ["curl", "-s", "-X", "POST", url,
           "-d", f"chat_id={chat_id}",
           "-d", f"text={text}",
           "--max-time", "15"]
    if parse_mode:
        cmd += ["-d", f"parse_mode={parse_mode}"]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    try:
        resp = json.loads(result.stdout)
        return resp.get("ok", False)
    except Exception:
        return False


def send_gate(product_id: str, gate_name: str, summary: str, actions: list[str]) -> bool:
    """Send a gate decision message to Telegram."""
    action_lines = "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions))
    msg = f"{summary}\n\n{action_lines}"
    return send_message(msg)
