"""Telegram inline keyboards for approvals and structured input.

See spec.md §7.3: inline keyboard buttons for structured approvals.
Free-text fallback for conflict resolution ("Something else").
"""

from typing import Any, Callable, Optional


# Callback data format: {action}:{run_id}:{gate_id}:{choice}
CALLBACK_SEP = ":"


def build_approval_keyboard(run_id: str, gate_id: str) -> list[list[dict]]:
    """Build an inline keyboard for document approval.

    Returns Telegram InlineKeyboardMarkup format:
    [[{"text": "...", "callback_data": "..."}]]
    """
    return [
        [
            {"text": "✅ Approve", "callback_data": f"approve:{run_id}:{gate_id}:yes"},
            {"text": "🔄 Another round", "callback_data": f"approve:{run_id}:{gate_id}:revise"},
            {"text": "❌ Start over", "callback_data": f"approve:{run_id}:{gate_id}:restart"},
        ]
    ]


def build_confirm_keyboard(run_id: str, gate_id: str) -> list[list[dict]]:
    """Build a simple yes/no confirmation keyboard."""
    return [
        [
            {"text": "✅ Yes", "callback_data": f"confirm:{run_id}:{gate_id}:yes"},
            {"text": "❌ No", "callback_data": f"confirm:{run_id}:{gate_id}:no"},
        ]
    ]


def build_conflict_keyboard(run_id: str, gate_id: str) -> list[list[dict]]:
    """Build keyboard for audit conflict resolution."""
    return [
        [
            {"text": "A) Side with GPT", "callback_data": f"conflict:{run_id}:{gate_id}:gpt"},
            {"text": "B) Side with Gemini", "callback_data": f"conflict:{run_id}:{gate_id}:gemini"},
        ],
        [
            {"text": "C) Something else", "callback_data": f"conflict:{run_id}:{gate_id}:other"},
        ],
    ]


def build_continue_keyboard(run_id: str) -> list[list[dict]]:
    """Build keyboard for continue/stop decision."""
    return [
        [
            {"text": "▶️ Continue", "callback_data": f"continue:{run_id}::yes"},
            {"text": "⏸️ Pause", "callback_data": f"continue:{run_id}::pause"},
        ]
    ]


def parse_callback(callback_data: str) -> dict:
    """Parse a callback_data string into components.

    Format: {action}:{run_id}:{gate_id}:{choice}

    Returns:
        Dict with action, run_id, gate_id, choice.
    """
    parts = callback_data.split(CALLBACK_SEP, 3)
    return {
        "action": parts[0] if len(parts) > 0 else "",
        "run_id": parts[1] if len(parts) > 1 else "",
        "gate_id": parts[2] if len(parts) > 2 else "",
        "choice": parts[3] if len(parts) > 3 else "",
    }


def is_approval(callback: dict) -> bool:
    """Check if callback is an approval action."""
    return callback.get("action") == "approve" and callback.get("choice") == "yes"


def is_rejection(callback: dict) -> bool:
    """Check if callback is a rejection/restart."""
    return callback.get("action") == "approve" and callback.get("choice") == "restart"


def is_free_text_needed(callback: dict) -> bool:
    """Check if callback requires follow-up free text (e.g., 'Something else')."""
    return callback.get("choice") == "other"
