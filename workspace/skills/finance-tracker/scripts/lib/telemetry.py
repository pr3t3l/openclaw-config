"""Anonymous telemetry for the finance tracker.

Sends anonymous usage data to help improve the product.
- No personal data is ever collected (no names, amounts, merchants, API keys)
- Only system config shape, command names, and error types
- User can disable: finance.py telemetry off
- All sends are fire-and-forget (never blocks the main flow)
"""

import json
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path
from threading import Thread

from . import config as C

SUPABASE_URL = "https://oetfiiatbzfydbtzozlz.supabase.co/rest/v1/telemetry"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ldGZpaWF0YnpmeWRidHpvemx6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNzY5MjUsImV4cCI6MjA5MDY1MjkyNX0.SQ6oN4WpO8x6NKYzNMPinS0_gNO5aCe-bljrzp5g96s"
VERSION = "1.0.10"


def _get_install_id() -> str:
    """Get or create an anonymous install ID (UUID, no relation to user)."""
    cfg = C._load_tracker_config()
    iid = cfg.get("telemetry", {}).get("install_id")
    if iid:
        return iid
    iid = str(uuid.uuid4())
    cfg.setdefault("telemetry", {})["install_id"] = iid
    cfg["telemetry"].setdefault("enabled", True)
    C.save_tracker_config(cfg)
    C.invalidate_config_cache()
    return iid


def is_enabled() -> bool:
    """Check if telemetry is enabled."""
    cfg = C._load_tracker_config()
    return cfg.get("telemetry", {}).get("enabled", True)


def set_enabled(enabled: bool):
    """Enable or disable telemetry."""
    cfg = C._load_tracker_config()
    cfg.setdefault("telemetry", {})["enabled"] = enabled
    if enabled and "install_id" not in cfg["telemetry"]:
        cfg["telemetry"]["install_id"] = str(uuid.uuid4())
    C.save_tracker_config(cfg)
    C.invalidate_config_cache()


def _send(install_id: str, event: str, data: dict):
    """Send a telemetry event via curl (fire-and-forget)."""
    payload = json.dumps({
        "install_id": install_id,
        "event": event,
        "data": data,
    })
    try:
        subprocess.run(
            ["curl", "-s", "--max-time", "5",
             "-X", "POST", SUPABASE_URL,
             "-H", f"apikey: {SUPABASE_KEY}",
             "-H", f"Authorization: Bearer {SUPABASE_KEY}",
             "-H", "Content-Type: application/json",
             "-H", "Prefer: return=minimal",
             "-d", payload],
            capture_output=True, timeout=7,
        )
    except Exception:
        pass  # Never fail


def track_event(event: str, data: dict | None = None):
    """Track an anonymous event. Non-blocking (runs in background thread)."""
    if not is_enabled():
        return
    install_id = _get_install_id()
    safe_data = data or {}
    safe_data["v"] = VERSION
    Thread(target=_send, args=(install_id, event, safe_data), daemon=True).start()


def track_install():
    """Track installation event with system info."""
    gog_available = Path.home().joinpath(".config", "gogcli", "credentials.json").exists()
    track_event("install", {
        "os": platform.system(),
        "os_version": platform.release()[:30],
        "python": platform.python_version(),
        "gog_available": gog_available,
        "ai_provider": "auto" if C._AI_CONFIG else "manual",
        "ai_url_type": _classify_url(C.LITELLM_URL),
    })


def track_setup_complete():
    """Track setup wizard completion."""
    cfg = C._load_tracker_config()
    tax = cfg.get("tax", {})
    track_event("setup_complete", {
        "language": cfg.get("user", {}).get("language", "?"),
        "currency": cfg.get("user", {}).get("currency", "?"),
        "tax_enabled": tax.get("enabled", False),
        "tax_generated_by": tax.get("generated_by", "none"),
        "categories_count": len(cfg.get("categories", {})),
        "cards_count": len(cfg.get("user", {}).get("cards", [])),
    })


def track_command(command: str, duration_ms: int = 0):
    """Track a command execution."""
    track_event("command", {
        "name": command,
        "duration_ms": duration_ms,
    })


def track_error(command: str, error_type: str):
    """Track an error (type only, never the message)."""
    track_event("error", {
        "command": command,
        "type": error_type,
    })


def track_reconcile(bank: str, tx_count: int, matched: int, ai_rules: int):
    """Track reconciliation stats."""
    track_event("reconcile", {
        "bank": bank,
        "transaction_count": tx_count,
        "matched_count": matched,
        "ai_rules_created": ai_rules,
    })


def _classify_url(url: str) -> str:
    """Classify AI endpoint type without exposing the full URL."""
    if "127.0.0.1" in url or "localhost" in url:
        return "local_proxy"
    if "openai.com" in url:
        return "openai_direct"
    if "openrouter.ai" in url:
        return "openrouter"
    if "anthropic.com" in url:
        return "anthropic_direct"
    return "custom"


def get_info_text() -> str:
    """Return human-readable description of what telemetry collects."""
    return """Anonymous Telemetry — What We Collect

We collect anonymous usage data to improve the finance tracker.
Your privacy is protected: NO personal data is ever sent.

COLLECTED (anonymous):
  • System info: OS type, Python version
  • Config shape: language, currency, number of categories/cards
  • Command names: which features you use (e.g., "parse-text", "cashflow")
  • Error types: what kind of errors occur (e.g., "JSONDecodeError")
  • Reconciliation stats: bank name, transaction count, match rate
  • AI provider type: local_proxy, openai_direct, openrouter, etc.

NEVER COLLECTED:
  • Your name, email, or any personal info
  • Transaction amounts, merchants, or financial data
  • API keys, tokens, or credentials
  • Message content or AI prompts
  • Google Sheets data

Your install has a random ID (UUID) with no connection to your identity.
Disable anytime: finance.py telemetry off"""
