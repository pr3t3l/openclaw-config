#!/bin/bash
# Usage: bash run_full_plan.sh <slug> "<idea>"
# Runs the ENTIRE planner pipeline: init → A → Gate #1 → B → Gate #2 → C → Gate #3
# Pauses at each gate for human approval.

set -euo pipefail

SLUG="$1"
IDEA="$2"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
SCRIPTS="$WORKSPACE/scripts"

echo "============================================"
echo "  META-WORKFLOW PLANNER — Full Run"
echo "  Slug: $SLUG"
echo "============================================"
echo ""

# Init
bash "$SCRIPTS/start_plan.sh" "$SLUG" "$IDEA"
echo ""

# Fase A
bash "$SCRIPTS/run_phase_a.sh" "$SLUG"
echo ""

# Gate #1
echo "============================================"
echo "  🚧 GATE #1: Review Fase A artifacts"
echo "============================================"
echo ""
bash "$SCRIPTS/resume_plan.sh" "$SLUG"
echo ""
read -p "Approve Gate #1? (yes/no): " APPROVE1
if [ "$APPROVE1" != "yes" ]; then
  echo "Gate #1 not approved. Stopping."
  exit 0
fi

python3 -c "
import json
from datetime import datetime, timezone
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    m = json.load(f)
m['gates']['gate_1'] = {'status': 'approved', 'approved_by': 'Alfredo', 'timestamp': datetime.now(timezone.utc).isoformat(), 'comment': 'Approved via run_full_plan.sh'}
with open('$WORKSPACE/runs/$SLUG/manifest.json', 'w') as f:
    json.dump(m, f, indent=2)
print('Gate #1 approved')
"
echo ""

# Fase B
bash "$SCRIPTS/run_phase_b.sh" "$SLUG"
echo ""

# Gate #2
echo "============================================"
echo "  🚧 GATE #2: Review Fase B artifacts"
echo "============================================"
echo ""
bash "$SCRIPTS/resume_plan.sh" "$SLUG"
echo ""
read -p "Approve Gate #2? (yes/no): " APPROVE2
if [ "$APPROVE2" != "yes" ]; then
  echo "Gate #2 not approved. Stopping."
  exit 0
fi

python3 -c "
import json
from datetime import datetime, timezone
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    m = json.load(f)
m['gates']['gate_2'] = {'status': 'approved', 'approved_by': 'Alfredo', 'timestamp': datetime.now(timezone.utc).isoformat(), 'comment': 'Approved via run_full_plan.sh'}
with open('$WORKSPACE/runs/$SLUG/manifest.json', 'w') as f:
    json.dump(m, f, indent=2)
print('Gate #2 approved')
"
echo ""

# Fase C
bash "$SCRIPTS/run_phase_c.sh" "$SLUG"
echo ""

# Gate #3
echo "============================================"
echo "  🚧 GATE #3: Final Review"
echo "============================================"
echo ""
bash "$SCRIPTS/resume_plan.sh" "$SLUG"
echo ""
echo "Review 08_plan_review.json for the full assessment."
read -p "Approve Gate #3 (GO to build)? (yes/no): " APPROVE3
if [ "$APPROVE3" = "yes" ]; then
  python3 -c "
import json
from datetime import datetime, timezone
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    m = json.load(f)
m['gates']['gate_3'] = {'status': 'approved', 'approved_by': 'Alfredo', 'timestamp': datetime.now(timezone.utc).isoformat(), 'comment': 'GO — approved via run_full_plan.sh'}
with open('$WORKSPACE/runs/$SLUG/manifest.json', 'w') as f:
    json.dump(m, f, indent=2)
print('Gate #3 approved — PLAN IS GO')
"
else
  echo "Gate #3 not approved. Plan needs revision."
fi
