#!/usr/bin/env python3
"""Sanitize a markdown report into a speakable TTS script.

Goals:
- Remove markdown/code/backticks/paths/URLs
- Replace emojis and bullet glyphs with simple spoken structure
- Avoid reading punctuation like underscores, brackets, slashes

Usage:
  python3 sanitize_tts.py <in_md> <out_txt>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

EMOJI_MAP = {
    "🔧": "Sección uno:",
    "🤖": "Sección dos:",
    "📈": "Sección tres:",
    "💰": "Sección cuatro:",
    "🏭": "Sección cinco:",
    "🔴": "Urgencia alta",
    "🟡": "Urgencia media",
    "🟢": "Urgencia baja",
}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: sanitize_tts.py <in_md> <out_txt>", file=sys.stderr)
        return 2

    in_md, out_txt = sys.argv[1], sys.argv[2]
    text = Path(in_md).read_text(encoding="utf-8")

    # Drop code blocks
    text = re.sub(r"```.*?```", " ", text, flags=re.S)

    # Replace emojis
    for k, v in EMOJI_MAP.items():
        text = text.replace(k, v)

    # Remove markdown headings and emphasis
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)

    # Remove inline code/backticks
    text = text.replace("`", "")

    # Remove bracketed paths and code-ish fragments
    # URLs
    text = re.sub(r"https?://\S+", "", text)
    # Unix-ish file paths
    text = re.sub(r"/home/\S+", "", text)
    text = re.sub(r"\b/\S+", "", text)

    # Replace common punctuation that sounds bad
    text = text.replace("/", " ")
    text = text.replace("_", " ")
    text = text.replace("[", " ").replace("]", " ")
    text = text.replace("(", " ").replace(")", " ")
    text = text.replace("{", " ").replace("}", " ")
    text = text.replace("|", " ")

    # Normalize bullets
    text = re.sub(r"^[\-•]\s*", "", text, flags=re.M)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Keep it reasonably short
    text = text.strip()
    if len(text) > 8000:
        text = text[:8000]

    Path(out_txt).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
