#!/bin/bash
# Usage: bash start_plan_from_file.sh <slug> <idea_file> [regular|deep]
# Reads raw idea from file and writes it into manifest.raw_idea without passing inline bash payloads.

set -euo pipefail

SLUG="$1"
IDEA_FILE="$2"
ANALYSIS_LEVEL="${3:-regular}"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
RUN_DIR="$WORKSPACE/runs/$SLUG"

if [ ! -f "$IDEA_FILE" ]; then
  echo "ERROR: Idea file not found: $IDEA_FILE"
  exit 1
fi

if [ -d "$RUN_DIR" ]; then
  echo "ERROR: Run '$SLUG' already exists. Use resume_plan.sh to continue."
  exit 1
fi

mkdir -p "$RUN_DIR"

IDEA_JSON=$(python3 - "$IDEA_FILE" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
print(json.dumps(p.read_text(encoding='utf-8')))
PY
)

cat > "$RUN_DIR/manifest.json" << EOF
{
  "plan_id": "$SLUG",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_modified": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "raw_idea": $IDEA_JSON,
  "analysis_level": "$ANALYSIS_LEVEL",
  "debate_level": null,
  "scope_selected": null,
  "artifacts": {
    "00_intake_summary":        { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "01_gap_analysis":          { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "02_scope_decision":        { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "03_data_flow_map":         { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "04_contracts":             { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "05_architecture_decision": { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "06_implementation_plan":   { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "07_cost_estimate":         { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "08_plan_review":           { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null }
  },
  "gates": {
    "gate_1": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null },
    "gate_2": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null },
    "gate_3": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null }
  },
  "total_cost_usd": 0,
  "conditional_modules_activated": []
}
EOF

echo "✅ Plan initialized from file: $RUN_DIR"
echo "Idea source: $IDEA_FILE"
echo "Next: python3 $WORKSPACE/scripts/spawn_planner_agent.py $SLUG intake_analyst"
