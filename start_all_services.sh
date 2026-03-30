#!/bin/bash
# OpenClaw — Start all services (idempotent, safe to run multiple times)
# Usage: bash ~/.openclaw/start_all_services.sh

LOG_DIR="$HOME/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/startup.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGFILE"; }

log "=== Starting OpenClaw stack ==="

# ── 1. PostgreSQL ──────────────────────────────────────────────
if pg_isready -q 2>/dev/null; then
    log "PostgreSQL already running"
else
    sudo service postgresql start >> "$LOGFILE" 2>&1
    sleep 2
    pg_isready -q && log "PostgreSQL started" || log "PostgreSQL FAILED — check $LOGFILE"
fi

# ── 2. LiteLLM ────────────────────────────────────────────────
if curl -s http://127.0.0.1:4000/health > /dev/null 2>&1; then
    log "LiteLLM already running"
else
    source /home/robotin/litellm-venv/bin/activate
    cd /home/robotin/.config/litellm
    set -a; source litellm.env 2>/dev/null; set +a
    nohup litellm --config config.yaml --host 127.0.0.1 --port 4000 \
        > "$LOG_DIR/litellm.log" 2>&1 &
    LITELLM_PID=$!
    log "LiteLLM starting (PID: $LITELLM_PID)..."
    sleep 10
    curl -s http://127.0.0.1:4000/health > /dev/null 2>&1 \
        && log "LiteLLM running" \
        || log "LiteLLM FAILED — check $LOG_DIR/litellm.log"
fi

# ── 3. OpenClaw Gateway ────────────────────────────────────────
if curl -s http://127.0.0.1:18789 > /dev/null 2>&1; then
    log "OpenClaw Gateway already running"
else
    set -a; source /home/robotin/.openclaw/.env; set +a
    cd /home/robotin/.openclaw
    nohup /home/robotin/.npm-global/bin/openclaw gateway \
        > "$LOG_DIR/openclaw-gateway.log" 2>&1 &
    GW_PID=$!
    log "OpenClaw Gateway starting (PID: $GW_PID)..."
    sleep 8
    curl -s http://127.0.0.1:18789 > /dev/null 2>&1 \
        && log "OpenClaw Gateway running" \
        || log "OpenClaw Gateway FAILED — check $LOG_DIR/openclaw-gateway.log"
fi

# ── Final status ───────────────────────────────────────────────
log ""
log "=== FINAL STATUS ==="
pg_isready -q 2>/dev/null                             && log "PostgreSQL :5432  — OK" || log "PostgreSQL :5432  — OFFLINE"
curl -s http://127.0.0.1:4000/health > /dev/null 2>&1 && log "LiteLLM :4000    — OK" || log "LiteLLM :4000    — OFFLINE"
curl -s http://127.0.0.1:18789 > /dev/null 2>&1       && log "Gateway :18789   — OK" || log "Gateway :18789   — OFFLINE"
