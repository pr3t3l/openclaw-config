#!/bin/bash
# Cost tracker — logs every LiteLLM request cost to a CSV
# Usage: source this or call cost_query() after running requests through the proxy
# Data source: journalctl JSON logs from litellm.service

COST_LOG="/home/robotin/.openclaw/workspace/cost_log.csv"

# Initialize CSV if it doesn't exist
if [ ! -f "$COST_LOG" ]; then
    echo "timestamp,model,prompt_tokens,completion_tokens,total_tokens,cost_usd" > "$COST_LOG"
fi

# Parse a single LiteLLM response and append to log
# Usage: curl ... | cost_log_response <model_name>
cost_log_response() {
    local model="${1:-unknown}"
    local response=$(cat)
    local usage=$(echo "$response" | python3 -c "
import sys, json
d = json.load(sys.stdin)
u = d.get('usage', {})
print(f\"{u.get('prompt_tokens',0)},{u.get('completion_tokens',0)},{u.get('total_tokens',0)}\")
" 2>/dev/null)
    echo "$response"
}

# Query total spend from proxy (requires litellm key-spend tracking)
cost_summary() {
    echo "=== Cost Log Summary ==="
    if [ ! -f "$COST_LOG" ] || [ $(wc -l < "$COST_LOG") -le 1 ]; then
        echo "No data yet. Tracking started — check back in a few days."
        return
    fi
    python3 << 'PYEOF'
import csv
from collections import defaultdict
from datetime import datetime

costs = defaultdict(float)
total = 0.0
count = 0
first_ts = None
last_ts = None

with open("/home/robotin/.openclaw/workspace/cost_log.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cost = float(row.get("cost_usd", 0))
        model = row.get("model", "unknown")
        costs[model] += cost
        total += cost
        count += 1
        ts = row.get("timestamp", "")
        if not first_ts:
            first_ts = ts
        last_ts = ts

if count == 0:
    print("No data yet.")
else:
    print(f"Period: {first_ts} to {last_ts}")
    print(f"Total requests: {count}")
    print(f"Total cost: ${total:.4f}")
    print("\nBy model:")
    for model, cost in sorted(costs.items(), key=lambda x: -x[1]):
        print(f"  {model}: ${cost:.4f} ({count} reqs)")
PYEOF
}

echo "Cost tracker loaded. CSV: $COST_LOG"
echo "Run cost_summary to see totals."
