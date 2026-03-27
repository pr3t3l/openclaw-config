#!/bin/bash
# Usage: bash run_phase_a.sh <slug>
# Runs A1 → A2 → A3 in sequence, stopping on any failure.
# Respects analysis_level for A2/A3 routing.

set -euo pipefail

SLUG="$1"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
SCRIPTS="$WORKSPACE/scripts"

LEVEL=$(python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    print(json.load(f).get('analysis_level', 'regular'))
")

echo "=== FASE A: CLARIFY (level: $LEVEL) ==="
echo ""

echo "--- A1: Intake Analyst ---"
python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" intake_analyst
echo ""

# Check if intake needs clarification
STATUS=$(python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/00_intake_summary.json') as f:
    data = json.load(f)
print(data.get('status', 'UNKNOWN'))
")

if [ "$STATUS" = "NEEDS_CLARIFICATION" ]; then
  echo "⚠️  Intake returned NEEDS_CLARIFICATION."
  echo "Review runs/$SLUG/intake_pending_questions.json"
  echo "Save answers to runs/$SLUG/intake_answers.json"
  echo "Then re-run: python3 $SCRIPTS/spawn_planner_agent.py $SLUG intake_analyst"
  exit 0
fi

echo "--- A2: Gap Finder ---"
if [ "$LEVEL" = "deep" ]; then
  python3 "$SCRIPTS/spawn_debate.py" "$SLUG" --phase gap_finder
else
  python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" gap_finder
fi
echo ""

echo "--- A3: Scope Framer ---"
if [ "$LEVEL" = "deep" ]; then
  python3 "$SCRIPTS/spawn_debate.py" "$SLUG" --phase scope_framer
else
  python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" scope_framer
fi
echo ""

echo "=== FASE A COMPLETE ==="
echo "Review the artifacts in runs/$SLUG/:"
echo "  00_intake_summary.json"
echo "  01_gap_analysis.json"
echo "  02_scope_decision.json"
echo ""
echo "If approved → proceed to Fase B (Design)"
echo "If changes needed → edit intake and re-run affected agents"
