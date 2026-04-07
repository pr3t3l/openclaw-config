#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/robotin/.openclaw/workspace/infra/morning_intelligence_report"

# Generate the script text
REPORT_TEXT="$(${BASE_DIR}/.venv/bin/python3 ${BASE_DIR}/morning_report.py)"

# Use OpenClaw TTS tool via the local CLI by printing to stdout is not available,
# so we call a tiny Python helper that uses OpenClaw's internal message tool is not exposed.
# Instead: write a file and rely on a separate OpenClaw agent trigger to TTS.
# For now, we just emit the report text; Robotin will wire TTS+Telegram delivery in OpenClaw layer.

echo "$REPORT_TEXT"
