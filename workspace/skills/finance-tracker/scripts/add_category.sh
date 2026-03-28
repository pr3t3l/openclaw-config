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

SKILL_DIR="/home/robotin/.openclaw/workspace/skills/finance-tracker"
SCRIPTS_DIR="$SKILL_DIR/scripts"
BUDGETS_FILE="$SKILL_DIR/config/budgets.json"
PARSER_FILE="$SCRIPTS_DIR/lib/parser.py"
PYTHON="/home/robotin/litellm-venv/bin/python"

echo "=== Adding category: $CATEGORY (budget: \$$BUDGET, threshold: $THRESHOLD) ==="

# 1. Update budgets.json
echo "[1/4] Updating budgets.json..."
$PYTHON -c "
import json
with open('$BUDGETS_FILE') as f:
    data = json.load(f)

if '$CATEGORY' in data['categories']:
    print('  Category already exists in budgets.json — updating values')

data['categories']['$CATEGORY'] = {
    'monthly': $BUDGET,
    'threshold': $THRESHOLD if $THRESHOLD != 'null' else None
}

with open('$BUDGETS_FILE', 'w') as f:
    json.dump(data, f, indent=2)

print('  Done: $CATEGORY added to budgets.json')
"

# 2. Update parser.py system prompt — add category to the enum list
echo "[2/4] Updating parser.py system prompt..."
$PYTHON -c "
import re

with open('$PARSER_FILE') as f:
    content = f.read()

# Find the category list in the system prompt
# It looks like: category MUST be one of: Groceries, Restaurants, ... Other
pattern = r'(category MUST be one of: .+?)(?=\n)'
match = re.search(pattern, content)
if match:
    old_line = match.group(1)
    if '$CATEGORY' in old_line:
        print('  Category already in parser prompt')
    else:
        # Add before 'Other' (which should always be last)
        new_line = old_line.replace(', Other', ', $CATEGORY, Other')
        content = content.replace(old_line, new_line)
        with open('$PARSER_FILE', 'w') as f:
            f.write(content)
        print('  Done: $CATEGORY added to parser prompt')
else:
    print('  WARNING: Could not find category list in parser.py — add manually')
"

# 3. Update Google Sheets Budget tab
echo "[3/4] Updating Google Sheets Budget tab..."
$PYTHON -c "
import sys
sys.path.insert(0, '$SCRIPTS_DIR')
from lib import sheets
from lib import config as C

ws = sheets.get_sheet(C.TAB_BUDGET)
records = ws.get_all_records()

# Check if category already exists
existing = [r for r in records if r.get('category') == '$CATEGORY']
if existing:
    print('  Category already exists in Sheets — skipping')
else:
    row = ['$CATEGORY', $BUDGET, $THRESHOLD]
    ws.append_row(row, value_input_option='USER_ENTERED')
    print('  Done: $CATEGORY added to Budget tab in Google Sheets')
"

# 4. Verify
echo "[4/4] Verifying..."
$PYTHON -c "
import json
with open('$BUDGETS_FILE') as f:
    data = json.load(f)

cat = data['categories'].get('$CATEGORY')
if cat:
    print(f'  budgets.json: $CATEGORY = \${cat[\"monthly\"]}/mo, threshold: {cat[\"threshold\"]}')
else:
    print('  ERROR: Category not found in budgets.json')
"

echo ""
echo "=== Done. Category '$CATEGORY' is now available. ==="
echo "Robotin can now categorize transactions as '$CATEGORY'."
echo "To add rules for this category, add rows to the Rules tab in Google Sheets."
