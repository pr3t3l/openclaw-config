#!/usr/bin/env python3
"""Render TTS using edge-tts with a fixed voice.

Usage:
  python3 render_alonso.py <text_file> <out_mp3>

Requires:
  /home/robotin/.openclaw/workspace/tmp/edge_tts_venv (created during setup)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Keep this path stable; cron runs in isolated env but same filesystem.
VENV_PY = "/home/robotin/.openclaw/workspace/tmp/edge_tts_venv/bin/python"

async def synth(text: str, out_mp3: str, voice: str = "es-US-AlonsoNeural"):
    import edge_tts
    c = edge_tts.Communicate(text, voice=voice)
    await c.save(out_mp3)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: render_alonso.py <text_file> <out_mp3>", file=sys.stderr)
        return 2

    text_file, out_mp3 = sys.argv[1], sys.argv[2]
    text = Path(text_file).read_text(encoding="utf-8")
    # Keep reasonable length for voice
    text = text.strip()[:8000]

    # Import edge_tts from the venv by executing inside it when called via that python.
    # If running under system python, we still attempt to import if available.
    try:
        import edge_tts  # noqa
    except Exception:
        # If user called system python by mistake, instruct.
        print(f"edge_tts not available. Use: {VENV_PY} {Path(__file__).name} <text_file> <out_mp3>", file=sys.stderr)
        return 3

    asyncio.run(synth(text, out_mp3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
