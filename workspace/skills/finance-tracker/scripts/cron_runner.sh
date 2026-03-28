#!/usr/bin/env bash
# cron_runner.sh — Execute a finance.py subcommand, send output to Telegram, log result.
#
# Usage: cron_runner.sh <job_name> <subcommand> [args...]
# Example: cron_runner.sh cashflow cashflow
#          cron_runner.sh payment-check payment-check
#          cron_runner.sh weekly-summary weekly-summary
#          cron_runner.sh monthly-report monthly-report

set -euo pipefail

JOB_NAME="${1:?Usage: cron_runner.sh <job_name> <subcommand> [args...]}"
shift
SUBCMD=("$@")

# Paths
PYTHON="/home/robotin/litellm-venv/bin/python"
FINANCE="/home/robotin/.openclaw/workspace/skills/finance-tracker/scripts/finance.py"
LOG_DIR="/home/robotin/.openclaw/workspace/skills/finance-tracker/logs"
LOG_FILE="${LOG_DIR}/${JOB_NAME}.log"

# Telegram config
source /home/robotin/.openclaw/.env
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="8024871665"
TG_API="https://api.telegram.org/bot${BOT_TOKEN}/sendMessage"

send_telegram() {
    local text="$1"
    # Telegram max message length is 4096; truncate if needed
    if [ ${#text} -gt 4000 ]; then
        text="${text:0:3990}…(truncado)"
    fi
    curl -s -X POST "$TG_API" \
        -d chat_id="$CHAT_ID" \
        -d text="$text" \
        -d parse_mode="Markdown" \
        --max-time 15 > /dev/null 2>&1 || \
    # Retry without markdown if it fails (special chars can break parsing)
    curl -s -X POST "$TG_API" \
        -d chat_id="$CHAT_ID" \
        -d text="$text" \
        --max-time 15 > /dev/null 2>&1
}

# Timestamp for log
TS=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TS] Running: $JOB_NAME (${SUBCMD[*]})" >> "$LOG_FILE"

# Execute the finance command
OUTPUT=$("$PYTHON" "$FINANCE" "${SUBCMD[@]}" 2>&1) && STATUS=0 || STATUS=$?

if [ $STATUS -eq 0 ]; then
    # Success — send output if non-empty
    if [ -n "$OUTPUT" ] && [ "$OUTPUT" != "No hay alertas de pago hoy." ]; then
        send_telegram "$OUTPUT"
        echo "[$TS] OK — sent to Telegram (${#OUTPUT} chars)" >> "$LOG_FILE"
    else
        echo "[$TS] OK — no output to send" >> "$LOG_FILE"
    fi
else
    # Failure — send error alert
    ERR_MSG="⚠️ Finance cron [$JOB_NAME] falló (exit $STATUS): ${OUTPUT:0:500}"
    send_telegram "$ERR_MSG"
    echo "[$TS] FAIL (exit $STATUS) — $OUTPUT" >> "$LOG_FILE"
fi
