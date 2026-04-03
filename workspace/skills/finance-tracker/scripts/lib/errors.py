"""Typed error system for Finance Tracker v2.

Every error has a code, message, and optional context dict.
CLI returns these as JSON so the LLM layer never guesses.
"""

from enum import Enum


class ErrorCode(str, Enum):
    # Setup errors
    SETUP_INCOMPLETE = "SETUP_INCOMPLETE"
    SETUP_STATE_CORRUPT = "SETUP_STATE_CORRUPT"
    SETUP_INVALID_INPUT = "SETUP_INVALID_INPUT"
    SETUP_ALREADY_COMPLETE = "SETUP_ALREADY_COMPLETE"

    # Config errors
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    CONFIG_CORRUPT = "CONFIG_CORRUPT"
    CONFIG_WRITE_FAILED = "CONFIG_WRITE_FAILED"

    # Schema errors
    SCHEMA_NOT_FOUND = "SCHEMA_NOT_FOUND"
    SCHEMA_VALIDATION = "SCHEMA_VALIDATION"

    # Auth / dependency errors
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    GOG_AUTH_MISSING = "GOG_AUTH_MISSING"
    SHEETS_ERROR = "SHEETS_ERROR"

    # AI errors
    AI_TIMEOUT = "AI_TIMEOUT"
    AI_INVALID_RESPONSE = "AI_INVALID_RESPONSE"
    AI_NO_KEY = "AI_NO_KEY"

    # Command errors
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    INVALID_ARGS = "INVALID_ARGS"

    # General
    INTERNAL = "INTERNAL"


class FinanceError(Exception):
    """Structured error that serializes to JSON for CLI output."""

    def __init__(self, code: ErrorCode, message: str, context: dict | None = None):
        self.code = code
        self.message = message
        self.context = context or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "context": self.context,
        }


# Convenience constructors for common errors

def setup_incomplete(state: str = "") -> FinanceError:
    return FinanceError(
        ErrorCode.SETUP_INCOMPLETE,
        "Setup not complete. Run: finance.py setup-next \"start\"",
        {"current_state": state} if state else {},
    )


def invalid_input(field: str, reason: str) -> FinanceError:
    return FinanceError(
        ErrorCode.SETUP_INVALID_INPUT,
        f"Invalid {field}: {reason}",
        {"field": field},
    )


def missing_dependency(name: str, install_hint: str = "") -> FinanceError:
    return FinanceError(
        ErrorCode.MISSING_DEPENDENCY,
        f"Missing dependency: {name}",
        {"dependency": name, "install_hint": install_hint},
    )
