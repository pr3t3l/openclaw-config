#!/usr/bin/env bash
# add_category.sh — Add a new spending category to the finance tracker
# Usage: bash add_category.sh "CategoryName" 50 0.80
#   $1 = Category name (e.g., "Pets")
#   $2 = Monthly budget (e.g., 50)
#   $3 = Alert threshold (e.g., 0.80) — optional, defaults to 0.80

set -euo pipefail

CATEGORY="${1:?Usage: add_category.sh <CategoryName> <monthly_budget> [threshold]}"
BUDGET="${2:?Usage: add_category.sh <CategoryName> <monthly_budget> [threshold]}"
THRESHOLD="${3:-0.80}"

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$SKILL_DIR/scripts"
CONFIG_FILE="$SKILL_DIR/config/tracker_config.json"
PYTHON="${PYTHON:-python3}"

echo "=== Adding category: $CATEGORY (budget: \$$BUDGET, threshold: $THRESHOLD) ==="

# 1. Update tracker_config.json
echo "[1/2] Updating tracker_config.json..."
$PYTHON -c "
import json
with open('$CONFIG_FILE') as f:
    data = json.load(f)

if '$CATEGORY' in data.get('categories', {}):
    print('  Category already exists in tracker_config.json — updating values')

data.setdefault('categories', {})['$CATEGORY'] = {
    'monthly': $BUDGET,
    'threshold': $THRESHOLD if $THRESHOLD != 'null' else None
}

with open('$CONFIG_FILE', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print('  Done: $CATEGORY added to tracker_config.json')
"

# 2. Verify
echo "[2/2] Verifying..."
$PYTHON -c "
import json
with open('$CONFIG_FILE') as f:
    data = json.load(f)

cat = data.get('categories', {}).get('$CATEGORY')
if cat:
    print(f'  tracker_config.json: $CATEGORY = \${cat[\"monthly\"]}/mo, threshold: {cat[\"threshold\"]}')
else:
    print('  ERROR: Category not found in tracker_config.json')
"

echo ""
echo "=== Done. Category '$CATEGORY' is now available. ==="
echo "✅ Category '$CATEGORY' added. The tracker can now categorize transactions in this category."
