#!/usr/bin/env bash
# test_crons.sh — Run each finance cron job manually and show results.
# Usage: bash test_crons.sh [job_name]
#   bash test_crons.sh              # run all
#   bash test_crons.sh cashflow     # run one

set -euo pipefail

RUNNER="/home/robotin/.openclaw/workspace/skills/finance-tracker/scripts/cron_runner.sh"

run_test() {
    local name="$1"
    shift
    echo ""
    echo "━━━ Testing: $name ━━━"
    bash "$RUNNER" "$name" "$@"
    echo "━━━ Done: $name (check Telegram + logs) ━━━"
}

if [ -n "${1:-}" ]; then
    case "$1" in
        cashflow)       run_test cashflow cashflow ;;
        payment-check)  run_test payment-check payment-check ;;
        weekly-summary) run_test weekly-summary weekly-summary ;;
        monthly-report) run_test monthly-report monthly-report ;;
        *)              echo "Unknown job: $1. Options: cashflow, payment-check, weekly-summary, monthly-report" ;;
    esac
else
    run_test cashflow cashflow
    run_test payment-check payment-check
    run_test weekly-summary weekly-summary
    run_test monthly-report monthly-report
    echo ""
    echo "All tests complete. Check Telegram for messages and logs at:"
    echo "  ~/.openclaw/workspace/skills/finance-tracker/logs/"
fi
