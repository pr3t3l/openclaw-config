#!/usr/bin/env bash
# cron_runner.sh — Execute a finance.py subcommand, send output to Telegram, log result.
#
# Usage: cron_runner.sh <job_name> <subcommand> [args...]
# Example: cron_runner.sh cashflow cashflow
#          cron_runner.sh payment-check payment-check
#          cron_runner.sh weekly-summary weekly-summary
#          cron_runner.sh monthly-report monthly-report

set -uo pipefail

JOB_NAME="${1:?Usage: cron_runner.sh <job_name> <subcommand> [args...]}"
shift
SUBCMD=("$@")

# Paths — derived from script location, no hardcoded usernames
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"
FINANCE="$SCRIPT_DIR/finance.py"
LOG_DIR="$SKILL_DIR/logs"
LOG_FILE="${LOG_DIR}/${JOB_NAME}.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Pre-flight checks — catch missing files/config before they fail silently
preflight_fail() {
    local msg="$1"
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] PREFLIGHT FAIL ($JOB_NAME): $msg" >> "$LOG_FILE"
    # Try to alert via Telegram if possible
    if [ -n "${BOT_TOKEN:-}" ] && [ -n "${CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
            -d chat_id="$CHAT_ID" \
            -d text="🚨 Finance cron PREFLIGHT FAIL [$JOB_NAME]: $msg" \
            --max-time 10 > /dev/null 2>&1 || true
    fi
    exit 1
}

# Check finance.py exists
if [ ! -f "$FINANCE" ]; then
    preflight_fail "finance.py not found at $FINANCE — skill may have been deleted or moved"
fi

# Check python available
if ! command -v "$PYTHON" &> /dev/null; then
    preflight_fail "Python ($PYTHON) not found in PATH"
fi

# Read Telegram config from tracker_config.json (product config, not system .env)
TRACKER_CONFIG="$SKILL_DIR/config/tracker_config.json"
if [ ! -f "$TRACKER_CONFIG" ]; then
    preflight_fail "tracker_config.json not found — run: finance.py setup"
fi

BOT_TOKEN=$("$PYTHON" -c "import json; d=json.load(open('$TRACKER_CONFIG')); print(d.get('telegram',{}).get('bot_token',''))" 2>/dev/null)
CHAT_ID=$("$PYTHON" -c "import json; d=json.load(open('$TRACKER_CONFIG')); print(d.get('telegram',{}).get('chat_id',''))" 2>/dev/null)

if [ -z "$BOT_TOKEN" ]; then
    preflight_fail "Telegram bot_token not configured — run: finance.py setup-telegram"
fi
if [ -z "$CHAT_ID" ]; then
    preflight_fail "Telegram chat_id not configured — run: finance.py setup-telegram"
fi

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
    if [ -n "$OUTPUT" ] && [ "$OUTPUT" != "No hay alertas de pago hoy." ] && [ "$OUTPUT" != "No payment alerts today." ]; then
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
