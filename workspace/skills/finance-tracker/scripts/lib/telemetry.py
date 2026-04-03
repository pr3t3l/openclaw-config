"""Anonymous telemetry for Finance Tracker v2.

Sends to Supabase table telemetry_v2. ZERO PII.
No user_id, no install_id, no session_id, no IP, no hashes.
Fire-and-forget via subprocess+curl (never blocks).
"""

import json
import subprocess
from threading import Thread
from pathlib import Path

from . import config as C

SUPABASE_URL = "https://oetfiiatbzfydbtzozlz.supabase.co/rest/v1/telemetry_v2"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ldGZpaWF0YnpmeWRidHpvemx6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNzY5MjUsImV4cCI6MjA5MDY1MjkyNX0.SQ6oN4WpO8x6NKYzNMPinS0_gNO5aCe-bljrzp5g96s"
VERSION = "2.0.0"


def is_enabled() -> bool:
    """Check if telemetry is enabled in config."""
    try:
        cfg = C._load_tracker_config()
        return cfg.get("telemetry", {}).get("enabled", False)
    except Exception:
        return False


def _duration_bucket(ms: int) -> str:
    if ms < 5000:
        return "0-5s"
    if ms < 15000:
        return "5-15s"
    if ms < 30000:
        return "15-30s"
    if ms < 60000:
        return "30-60s"
    return "60s+"


def _send(payload: dict):
    """Fire-and-forget send via curl."""
    try:
        subprocess.run(
            ["curl", "-s", "--max-time", "5",
             "-X", "POST", SUPABASE_URL,
             "-H", f"apikey: {SUPABASE_KEY}",
             "-H", f"Authorization: Bearer {SUPABASE_KEY}",
             "-H", "Content-Type: application/json",
             "-H", "Prefer: return=minimal",
             "-d", json.dumps(payload)],
            capture_output=True, timeout=7,
        )
    except Exception:
        pass


def send_event(event_type: str, **kwargs):
    """Send an anonymous telemetry event. Non-blocking.

    Usage:
        send_event("setup_stage_complete", stage="INCOME_COLLECT", result="ok")
        send_event("command_used", stage="add", result="ok", duration_bucket="0-5s")
        send_event("error_occurred", stage="add", error_code="SHEETS_ERROR")
    """
    if not is_enabled():
        return

    payload = {
        "event": event_type,
        "v": VERSION,
        "distribution": "github_zip",
    }

    # Map kwargs to schema fields
    for field in ("stage", "result", "duration_bucket", "error_code",
                  "setup_mode", "detected_language", "income_source_count",
                  "debt_count", "business_type_count", "custom_category_count",
                  "cron_job_count"):
        if field in kwargs:
            payload[field] = kwargs[field]

    if "rulepack_ids" in kwargs:
        payload["rulepack_ids"] = json.dumps(kwargs["rulepack_ids"])

    if "duration_ms" in kwargs:
        payload["duration_bucket"] = _duration_bucket(kwargs["duration_ms"])

    Thread(target=_send, args=(payload,), daemon=True).start()


# ── Setup-only convenience wrappers ───────────────────
# Telemetry fires ONLY during setup. No runtime tracking.

def track_setup_stage(stage: str, result: str = "ok", **kwargs):
    send_event("setup_stage_complete", stage=stage, result=result, **kwargs)

def track_setup_error(stage: str, error_code: str):
    send_event("setup_stage_error", stage=stage, result="error", error_code=error_code)

def track_setup_complete(mode: str, language: str, **kwargs):
    send_event("setup_complete", setup_mode=mode, detected_language=language,
               result="ok", **kwargs)

def track_preflight_failed(error_code: str):
    send_event("preflight_failed", stage="PREFLIGHT", result="error",
               error_code=error_code)
