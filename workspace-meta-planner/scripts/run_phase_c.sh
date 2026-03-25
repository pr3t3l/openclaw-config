#!/bin/bash
# Usage: bash run_phase_c.sh <slug>
# Runs C1 → C2 → C3 in sequence.
# C2 is a Python script (not LLM).

set -euo pipefail

SLUG="$1"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
SCRIPTS="$WORKSPACE/scripts"

# Check Gate #2 is approved
GATE2=$(python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    m = json.load(f)
print(m.get('gates', {}).get('gate_2', {}).get('status', 'unknown'))
")

if [ "$GATE2" != "approved" ]; then
  echo "ERROR: Gate #2 is not approved (status: $GATE2). Cannot proceed to Fase C."
  echo "Run Fase B first and approve Gate #2."
  exit 1
fi

echo "=== FASE C: BUILDABILITY ==="
echo ""

echo "--- C1: Implementation Planner ---"
python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" implementation_planner
echo ""

echo "--- C2: Cost Estimator (script, no LLM) ---"
python3 "$SCRIPTS/cost_estimator.py" "$SLUG"
echo ""

echo "--- C3: Lessons Learned Validator ---"
python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" lessons_validator
echo ""

# Show verdict
VERDICT=$(python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/08_plan_review.json') as f:
    data = json.load(f)
print(data.get('verdict', 'UNKNOWN'))
")

echo "=== FASE C COMPLETE ==="
echo ""
echo "VERDICT: $VERDICT"
echo ""

if [ "$VERDICT" = "GO" ]; then
  echo "✅ The plan is ready to build!"
elif [ "$VERDICT" = "NEEDS_REVISION" ]; then
  echo "⚠️  The plan needs revision before building."
  echo "Check runs/$SLUG/08_plan_review.json for details."
else
  echo "❌ Do not build yet. See review for reasons."
fi

echo ""
echo "Artifacts in runs/$SLUG/:"
echo "  06_implementation_plan.json"
echo "  07_cost_estimate.json"
echo "  08_plan_review.json"
echo ""
echo "Gate #3 awaiting approval."
