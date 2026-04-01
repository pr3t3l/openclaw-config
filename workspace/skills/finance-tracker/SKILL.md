---
name: finance-tracker
description: Personal finance tracker. Parses expenses (text/photo/CSV), logs to Google Sheets, monitors budgets, sends payment reminders, daily cashflow, and monthly reports. Configurable per user via setup wizard.
---

# Finance Tracker

Personal expense tracking skill for OpenClaw. All configuration is driven by `config/tracker_config.json` — no hardcoded personal data.

## Scripts Location

All scripts live at: `~/.openclaw/workspace/skills/finance-tracker/scripts/`

**Base command:**
```bash
python3 ~/.openclaw/workspace/skills/finance-tracker/scripts/finance.py <subcommand> [args]
```

## First Run — Installation & Setup

**IMPORTANT: Follow this sequence WITHOUT stopping. Only pause to ask the user the 3 required questions.**

### After setup.sh completes, do this immediately:

**Step 1:** Ask the user these 3 questions (all at once in a single message):
1. What bank cards/accounts do you use? (e.g., Chase Visa, Discover, Cash)
2. What currency? (e.g., USD, EUR, GBP)
3. Do you have a business for tax deductions? (no / rental property / freelancer / small business)
   - If yes: briefly describe it (e.g., "Airbnb beach house")

**Step 2:** Once the user answers, run these 3 commands in sequence (do NOT stop between them):

```bash
cd ~/.openclaw/workspace/skills/finance-tracker/scripts

# 1. Setup — name and language are auto-detected from USER.md
python3 finance.py setup '{"cards":"CARDS_HERE","currency":"CURRENCY_HERE","tax":"none"}'

# 2. Create Google Sheet
python3 finance.py setup-sheets

# 3. Test
python3 finance.py parse-text '$25 Starbucks'
```

If user has tax tracking, use:
```bash
python3 finance.py setup '{"cards":"CARDS","currency":"USD","tax":"rental","tax_description":"Airbnb beach house"}'
```

Tax type options: `none`, `rental`, `freelancer`, `business`, `other`

**Step 3:** Show the user the final result: parsed transaction + Google Sheet URL.

**NEVER run `finance.py setup` without a JSON argument. It will fail with EOFError.**

## When You Activate

This skill activates when the user sends ANY of:

1. **An expense** — dollar amount, merchant name, receipt photo, or CSV file
2. **A finance command** — balance, cashflow, status, reconcile, weekly, monthly, rule, savings, goal, payday
3. **A receipt photo** — any image of a receipt
4. **A CSV file** — bank statement upload

## How to Process Expenses

### Text expenses

When the user sends something like "$45 Publix Chase" or "Spent 45 at Publix":

1. Run: `finance.py parse-text "$45 Publix Chase"`
2. Review the JSON output
3. If `rule_matched: true` and `needs_confirmation: false` → auto-log it:
   - Run: `finance.py log '<json>'`
   - Send the confirmation message
4. If `needs_confirmation: true` → send parsed result and ask for confirmation
5. If `_duplicate_warning` exists → show the warning, wait for response

### Receipt photos and receipt links

When the user sends a **photo** OR a **receipt link** (URLs from walmart.com, target.com, costco.com, publix.com, instacart.com, or any retailer receipt/order page):
1. Save the image to `/tmp/receipt_YYYYMMDD_HHMMSS.jpg` (for photos) or fetch the URL content first (for links)
2. **Always use `finance.py parse-photo`** — never parse-text for photos or links
3. Run: `finance.py parse-photo /tmp/receipt_YYYYMMDD_HHMMSS.jpg`
4. Always ask the user to confirm before logging

**Rule: If the input is an image or a URL to a receipt, use parse-photo. Only use parse-text for plain text messages with amounts.**

### CSV uploads

When the user sends a CSV file:
1. Save to `/tmp/bank_statement.csv`
2. Run: `finance.py reconcile /tmp/bank_statement.csv [bank]`
3. Show the reconciliation summary
4. For probable matches, ask the user to confirm each one

## Receipt Splitting + Tax Deduction

### Receipt photos with multiple categories

When a receipt photo is parsed and has items from different categories, the parser outputs a **split receipt** with `receipt_id` and `transactions` array. Each group has its own category.

**Items that might be tax-deductible** (based on the user's tax profile) get `needs_confirmation: true` with a `confirmation_reason`.

Show the split confirmation format:
```
Walmart $127.43 — 4 groups detected

Auto-logged:
  ✔ $52.10 → Groceries (food)
  ✔ $23.90 → Shopping (clothing)

Personal or business?
  1. $18.99 — Clorox wipes, Lysol (cleaning_supplies)
  2. $23.45 — Bath towels x2 (linens)

Reply: "all business", "1,3 business 2 personal", or by number
```

Process responses:
- "all business" / "todos airbnb" → set all pending items: `tax_deductible=true`, assign tax_category
- "all personal" / "todos personal" → set all pending: `tax_deductible=false`, `tax_category=none`
- "1,3 business" → items 1,3 deductible, rest personal
- "1 business 2 personal" → explicit assignment

After resolving, run `finance.py log-split '<receipt_json>'` to log all transactions.

### Text with business keywords

If the user types "$19 Clorox para airbnb" or includes a business keyword → auto-set `tax_deductible=true`, no confirmation needed.

### ask_airbnb merchants

Merchants flagged with `ask_airbnb` in rules always ask "Personal or business?" even for single-item text input — unless user already specified in the message.

### Food is NEVER deductible — NEVER ask about food items.

## Confirmation Flow

After parsing a single transaction, show:
```
Logged: $45.32 at Publix (Groceries) with Chase.
Groceries this month: $195/$250 (78%).
Correct?
```

- "yes", "ok", "si" → run `finance.py log '<json>'`
- User sends corrections → update fields and re-confirm
- "no", "cancel" → discard
- If user corrects the category → the system learns (auto-creates rules after 2 corrections for same merchant)

## Finance Commands

| User says | Action |
|-----------|--------|
| `balance: 3200` or `saldo: 3200` | `finance.py balance 3200` |
| `cashflow` or `flujo` | `finance.py cashflow` |
| `status` or `status Groceries` | `finance.py status [category]` |
| `weekly` or `weekly summary` | `finance.py weekly-summary` |
| `monthly` or `monthly report` | `finance.py monthly-report [YYYY-MM]` |
| `reconcile` + CSV attachment | `finance.py reconcile /path/to/csv` |
| `rule: target → Shopping 0.95` | `finance.py add-rule "target" Shopping 0.95` |
| `savings colombia 200` | `finance.py savings colombia 200` |
| `savings-target colombia 2500` | `finance.py savings-target colombia 2500` |
| `payday: biweekly 2800` | `finance.py payday biweekly 2800` |
| `payments` | `finance.py payment-check` |
| `taxes 2026` | `finance.py taxes 2026` |
| `setup` | `finance.py setup '<json>'` (ALWAYS pass JSON, never run without args) |
| `new-tax-profile` | `finance.py new-tax-profile ['<json>']` |
| `update-tax-profile` | `finance.py update-tax-profile [regenerate\|remove-rule N\|add-keywords N 'kw1,kw2']` |
| `current-tax-profile` | `finance.py current-tax-profile` |

## Tax Profiles

Tax deduction tracking is configurable per user's business type. Configured via:
- `finance.py new-tax-profile` — AI-powered wizard to create a new tax profile
- `finance.py update-tax-profile` — modify existing rules
- `finance.py current-tax-profile` — view current profile

Supports: rental properties, freelancers, small businesses, and custom business types.

## Noise Control Rules

- Max 3 budget alerts per day per category
- No alerts 10 PM — 7 AM (except urgent payment alerts)
- Don't re-alert same category same week unless it crosses next threshold (80% → 95% → 100%)

## Cron Jobs (Scheduled)

These run automatically — do NOT run them when processing messages:

| Schedule | Command | Purpose |
|----------|---------|---------|
| Daily 7:30 AM | `finance.py cashflow` | Morning "safe to spend" message |
| Daily 9:00 AM | `finance.py payment-check` | Payment due date alerts |
| Sundays 8:00 AM | `finance.py weekly-summary` | Weekly spending review |
| 1st of month 8:00 AM | `finance.py monthly-report` | Monthly analysis |

## Error Responses

- Unreadable image: "Could not read the receipt. Can you send a clearer one or type the expense manually?"
- Ambiguous amount: "Is the total $X.XX or $Y.YY?"
- Ambiguous category: "Is this for work or personal?"
- Sheets unavailable: Log locally, sync when available

## Categories

Categories are loaded dynamically from `tracker_config.json`. Default set created by setup wizard; add more with:
```bash
bash add_category.sh "CategoryName" <budget> [threshold]
```

## Language

The tracker responds in the user's preferred language (auto-detected from workspace USER.md). Supports English and Spanish.
