#!/bin/bash
# Usage: bash run_phase_b.sh <slug>
# Runs B1 → B2 → B3 in sequence.
# B3 always uses spawn_debate.py. B1 uses debate if deep.

set -euo pipefail

SLUG="$1"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
SCRIPTS="$WORKSPACE/scripts"

# Check Gate #1 is approved
GATE1=$(python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    m = json.load(f)
print(m.get('gates', {}).get('gate_1', {}).get('status', 'unknown'))
")

if [ "$GATE1" != "approved" ]; then
  echo "ERROR: Gate #1 is not approved (status: $GATE1). Cannot proceed to Fase B."
  echo "Run Fase A first and approve Gate #1."
  exit 1
fi

LEVEL=$(python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    print(json.load(f).get('analysis_level', 'regular'))
")

echo "=== FASE B: DESIGN (level: $LEVEL) ==="
echo ""

echo "--- B1: Data Flow Mapper ---"
if [ "$LEVEL" = "deep" ]; then
  python3 "$SCRIPTS/spawn_debate.py" "$SLUG" --phase data_flow_mapper
else
  python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" data_flow_mapper
fi
echo ""

# Check for orphan outputs (hard fail — L-01)
ORPHANS=$(python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/03_data_flow_map.json') as f:
    data = json.load(f)
orphans = data.get('orphan_outputs', [])
missing = data.get('missing_required_artifacts', [])
if orphans:
    print(f'ORPHAN OUTPUTS: {orphans}')
if missing:
    print(f'MISSING ARTIFACTS: {missing}')
if not orphans and not missing:
    print('OK')
")

if [ "$ORPHANS" != "OK" ]; then
  echo "⚠️  Data Flow has issues:"
  echo "$ORPHANS"
  echo "Fix the data flow before continuing."
  exit 1
fi

echo "--- B2: Contract Designer ---"
python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" contract_designer
echo ""

echo "--- B3: Architecture Planner (Debate) ---"
python3 "$SCRIPTS/spawn_debate.py" "$SLUG" --phase architecture_planner
echo ""

echo "=== FASE B COMPLETE ==="
echo "Review the artifacts in runs/$SLUG/:"
echo "  03_data_flow_map.json"
echo "  04_contracts.json"
echo "  05_architecture_decision.json"
echo "  debate_proposals/ (individual model proposals)"
echo ""
echo "If approved → Gate #2, then proceed to Fase C"
echo "If changes needed → edit and re-run affected agents"
