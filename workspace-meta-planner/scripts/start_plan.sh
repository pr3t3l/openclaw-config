#!/bin/bash
# Usage: bash start_plan.sh <slug> "<idea text>"
# Example: bash start_plan.sh personal-finance "Quiero un workflow que cuando envíe un gasto por Telegram..."

set -euo pipefail

SLUG="$1"
IDEA="$2"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
RUN_DIR="$WORKSPACE/runs/$SLUG"

if [ -d "$RUN_DIR" ]; then
  echo "ERROR: Run '$SLUG' already exists. Use resume_plan.sh to continue."
  exit 1
fi

mkdir -p "$RUN_DIR"

# Safely JSON-encode the idea text (micro-fix #2: pipe through stdin to avoid quote issues)
IDEA_JSON=$(printf '%s' "$IDEA" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

# Initialize manifest
cat > "$RUN_DIR/manifest.json" << EOF
{
  "plan_id": "$SLUG",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_modified": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "raw_idea": $IDEA_JSON,
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

echo "✅ Plan initialized: $RUN_DIR"
echo "Next: run Fase A (Clarify)"
echo "  python3 $WORKSPACE/scripts/spawn_planner_agent.py $SLUG intake_analyst"
