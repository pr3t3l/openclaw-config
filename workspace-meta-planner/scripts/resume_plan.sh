#!/bin/bash
# Usage: bash resume_plan.sh <slug>
# Shows the current state of a plan run and suggests the next step.
# Does NOT execute anything — information only.

set -euo pipefail

SLUG="$1"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
RUN_DIR="$WORKSPACE/runs/$SLUG"
MANIFEST="$RUN_DIR/manifest.json"

if [ ! -d "$RUN_DIR" ]; then
  echo "ERROR: Run '$SLUG' not found at $RUN_DIR"
  exit 1
fi

if [ ! -f "$MANIFEST" ]; then
  echo "ERROR: manifest.json not found in $RUN_DIR"
  exit 1
fi

echo "=== Plan Status: $SLUG ==="
echo ""

# Show basic info
echo "Plan ID:       $(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['plan_id'])")"
echo "Created:       $(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['created_at'])")"
echo "Last Modified: $(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['last_modified'])")"
echo "Debate Level:  $(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m.get('debate_level') or 'not set')")"
echo "Total Cost:    \$$(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['total_cost_usd'])")"
echo ""

# Show artifact status
echo "=== Artifacts ==="
python3 -c "
import json

with open('$MANIFEST') as f:
    manifest = json.load(f)

artifacts = manifest['artifacts']
artifact_order = [
    '00_intake_summary', '01_gap_analysis', '02_scope_decision',
    '03_data_flow_map', '04_contracts', '05_architecture_decision',
    '06_implementation_plan', '07_cost_estimate', '08_plan_review'
]

phases = {
    '00_intake_summary': 'A1',
    '01_gap_analysis': 'A2',
    '02_scope_decision': 'A3',
    '03_data_flow_map': 'B1',
    '04_contracts': 'B2',
    '05_architecture_decision': 'B3',
    '06_implementation_plan': 'C1',
    '07_cost_estimate': 'C2',
    '08_plan_review': 'C3',
}

for name in artifact_order:
    info = artifacts[name]
    status = info['status']
    icon = {'fresh': '✅', 'stale': '🔄', 'missing': '⬜'}.get(status, '❓')
    cost = '${0:.4f}'.format(info['cost_usd']) if info.get('cost_usd') else '-'
    print(f'  {icon} [{phases[name]}] {name}: {status} (cost: {cost})')
"
echo ""

# Show gate status
echo "=== Gates ==="
python3 -c "
import json

with open('$MANIFEST') as f:
    manifest = json.load(f)

gates = manifest['gates']
gate_info = {
    'gate_1': ('Gate #1', 'After Fase A (Clarify)', ['00_intake_summary', '01_gap_analysis', '02_scope_decision']),
    'gate_2': ('Gate #2', 'After Fase B (Design)', ['03_data_flow_map', '04_contracts', '05_architecture_decision']),
    'gate_3': ('Gate #3', 'After Fase C (Buildability)', ['06_implementation_plan', '07_cost_estimate', '08_plan_review']),
}

for gate_id, (label, desc, _) in gate_info.items():
    info = gates[gate_id]
    status = info['status']
    icon = {'approved': '✅', 'pending': '⏳', 'rejected': '❌'}.get(status, '❓')
    extra = ''
    if info.get('approved_by'):
        extra = f\" by {info['approved_by']} at {info.get('timestamp', '?')}\"
    if info.get('comment'):
        extra += f\" — {info['comment']}\"
    print(f'  {icon} {label} ({desc}): {status}{extra}')
"
echo ""

# Determine next step
echo "=== Next Step ==="
python3 -c "
import json

with open('$MANIFEST') as f:
    manifest = json.load(f)

artifacts = manifest['artifacts']
gates = manifest['gates']

artifact_order = [
    '00_intake_summary', '01_gap_analysis', '02_scope_decision',
    '03_data_flow_map', '04_contracts', '05_architecture_decision',
    '06_implementation_plan', '07_cost_estimate', '08_plan_review'
]

agent_names = {
    '00_intake_summary': 'intake_analyst',
    '01_gap_analysis': 'gap_finder',
    '02_scope_decision': 'scope_framer',
    '03_data_flow_map': 'data_flow_mapper',
    '04_contracts': 'contract_designer',
    '05_architecture_decision': 'architecture_planner',
    '06_implementation_plan': 'implementation_planner',
    '07_cost_estimate': 'cost_estimator (script)',
    '08_plan_review': 'lessons_validator',
}

gate_after = {
    '02_scope_decision': 'gate_1',
    '05_architecture_decision': 'gate_2',
    '08_plan_review': 'gate_3',
}

# Find first missing or stale artifact
for name in artifact_order:
    status = artifacts[name]['status']
    if status in ('missing', 'stale'):
        # Check if we need a gate approval first
        prev_idx = artifact_order.index(name) - 1
        if prev_idx >= 0:
            prev_name = artifact_order[prev_idx]
            if prev_name in gate_after:
                gate_id = gate_after[prev_name]
                if gates[gate_id]['status'] != 'approved':
                    print(f'  ⏳ Waiting for {gate_id} approval before proceeding.')
                    print(f'     All Fase artifacts before this gate must be fresh.')
                    break
        agent = agent_names[name]
        print(f'  → Run: {agent} to produce {name}')
        break
else:
    # All artifacts fresh
    if gates['gate_3']['status'] == 'approved':
        print('  🎉 Plan is complete! All artifacts fresh, all gates approved.')
    else:
        print('  ⏳ All artifacts produced. Awaiting final gate approval (gate_3).')
"
