#!/usr/bin/env python3
"""Finance Tracker v2 — CLI entry point.

Every command returns JSON to stdout. The LLM never controls flow.

Usage:
  python3 finance.py install-check
  python3 finance.py preflight
  python3 finance.py setup-next "<user_input>"
  python3 finance.py setup-next "start" --mode quick
  python3 finance.py setup-status
  python3 finance.py setup-reset
"""

import json
import sys
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from lib import config as C
from lib.errors import FinanceError, ErrorCode
from lib.state_machine import (
    SetupStateMachine, install_check, preflight, setup_status, check_onboarding,
)


def _out(data: dict) -> None:
    """Print JSON to stdout and exit 0."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _err(e: FinanceError) -> None:
    """Print error JSON to stdout and exit 1."""
    print(json.dumps(e.to_dict(), indent=2, ensure_ascii=False))
    sys.exit(1)


def cmd_install_check():
    _out(install_check())


def cmd_preflight():
    _out(preflight())


def cmd_setup_next(user_input: str, mode: str = "full"):
    try:
        sm = SetupStateMachine(mode=mode)
        result = sm.process(user_input)
        _out(result)
    except FinanceError as e:
        _err(e)


def cmd_setup_status():
    _out(setup_status())


def cmd_onboarding_check(command: str):
    result = check_onboarding(command)
    if result:
        _out(result)
    else:
        _out({"onboarding_message": None})


def cmd_setup_reset():
    C.clear_setup_state()
    C.invalidate_config_cache()
    # Remove tracker_config if it exists and setup wasn't complete
    config_path = C.get_config_dir() / "tracker_config.json"
    if config_path.exists():
        cfg = C.load_json(config_path)
        if not cfg.get("user", {}).get("setup_complete", False):
            config_path.unlink()
    _out({"reset": True, "message": "Setup state cleared."})


def main():
    if len(sys.argv) < 2:
        _err(FinanceError(ErrorCode.INVALID_ARGS, "Usage: finance.py <command> [args]"))

    cmd = sys.argv[1]

    commands = {
        "install-check": cmd_install_check,
        "preflight": cmd_preflight,
        "setup-status": cmd_setup_status,
        "setup-reset": cmd_setup_reset,
    }

    if cmd == "onboarding-check":
        command_name = sys.argv[2] if len(sys.argv) > 2 else ""
        cmd_onboarding_check(command_name)
        return

    if cmd == "setup-next":
        user_input = sys.argv[2] if len(sys.argv) > 2 else ""
        mode = "full"
        if "--mode" in sys.argv:
            idx = sys.argv.index("--mode")
            if idx + 1 < len(sys.argv):
                mode = sys.argv[idx + 1]
        cmd_setup_next(user_input, mode)
        return

    if cmd in commands:
        commands[cmd]()
        return

    _err(FinanceError(ErrorCode.UNKNOWN_COMMAND, f"Unknown command: {cmd}",
                      {"available": list(commands.keys()) + ["setup-next"]}))


if __name__ == "__main__":
    main()
