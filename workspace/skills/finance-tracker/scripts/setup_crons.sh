#!/usr/bin/env bash
# setup_crons.sh — Install all finance tracker cron jobs.
# Run once: bash setup_crons.sh
# To remove: bash setup_crons.sh --remove

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNNER="$SCRIPT_DIR/cron_runner.sh"
TAG="# finance-tracker"

# All times in EST (America/New_York)
# cron uses system TZ; set CRON_TZ or use TZ env in the line
CRON_JOBS=(
    # Daily Cashflow: Mon-Fri 7:30 AM EST
    "30 7 * * 1-5  CRON_TZ=America/New_York bash $RUNNER cashflow cashflow $TAG"
    # Payment Reminder: Daily 9:00 AM EST
    "0 9 * * *     CRON_TZ=America/New_York bash $RUNNER payment-check payment-check $TAG"
    # Weekly Summary: Sundays 8:00 AM EST
    "0 8 * * 0     CRON_TZ=America/New_York bash $RUNNER weekly-summary weekly-summary $TAG"
    # Monthly Report: 1st of month 8:00 AM EST
    "0 8 1 * *     CRON_TZ=America/New_York bash $RUNNER monthly-report monthly-report $TAG"
)

if [ "${1:-}" = "--remove" ]; then
    echo "Removing finance-tracker cron jobs..."
    crontab -l 2>/dev/null | grep -v "$TAG" | crontab -
    echo "Done. Remaining crontab:"
    crontab -l 2>/dev/null || echo "(empty)"
    exit 0
fi

echo "Installing finance-tracker cron jobs..."

# Get existing crontab (minus any old finance-tracker lines)
EXISTING=$(crontab -l 2>/dev/null | grep -v "$TAG" || true)

# Build new crontab
{
    echo "$EXISTING"
    echo ""
    echo "# === Finance Tracker Crons ==="
    for job in "${CRON_JOBS[@]}"; do
        echo "$job"
    done
} | crontab -

echo "Installed. Current crontab:"
crontab -l
