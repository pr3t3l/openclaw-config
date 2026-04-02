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

## When User Sends /finance_tracker

When the user sends `/finance_tracker` with no arguments or just wants to see what's available, respond with this menu:

```
Finance Tracker — Commands

Setup:
 1. /setup — Initial setup wizard

Categories + Budgets:
 2. /list-categories — View all with budget & spending
 3. /add-category <name> <budget> — New category
 4. /modify-budget <category> <amount> — Change budget
 5. /remove-category <name> — Delete category

Balance + Income:
 6. /balance <amount> — Set current balance
 7. /income <amount> — Register income
 8. /payday <schedule> <amount> [days] — Configure pay schedule

Payments:
 9. /list-payments — View all bills
10. /add-payment <name> <amount> <day> [account] — Add bill
11. /modify-payment <name> <amount> — Change amount
12. /remove-payment <name> — Delete bill
13. /payment-check — Check upcoming bills

Debts:
14. /list-debts — View all debts
15. /add-debt <name> <balance> [apr] — Add debt
16. /update-debt <name> <balance> — Update balance
17. /pay-debt <name> <amount> — Record payment

Cards:
18. /add-card <name> — Add card/account
19. /remove-card <name> — Remove card/account

Savings:
20. /list-goals — View savings goals
21. /add-goal <name> <target> [deadline] — New goal
22. /save <goal> <amount> — Contribute to goal
23. /remove-goal <name> — Delete goal

Tax:
24. /new-tax-profile — AI tax deduction wizard
25. /update-tax-profile — Modify tax rules
26. /current-tax-profile — View active profile

Reports:
27. /cashflow — Daily safe-to-spend
28. /status [category] — Budget overview
29. /weekly — Weekly summary
30. /monthly [YYYY-MM] — Monthly report
31. /taxes [year] — Tax deduction report

Data:
32. /reconcile + CSV — Match bank statement
33. /batch-receipts + links — Process receipt links
34. /add-rule <pattern> <category> [confidence] — Add categorization rule

Telemetry:
35. /telemetry-on — Enable anonymous analytics
36. /telemetry-off — Disable anonymous analytics
37. /telemetry-status — Show current status
38. /telemetry-info — What data is collected

Reply with a number or command name.
```

When the user replies with a number (1-34) or a command name, execute the corresponding action below.

## Command Actions

When the user selects a command (by number or name), here is exactly what to do:

### 1. /setup
Ask the user 3 questions ONE AT A TIME (cards, currency, tax type). See "First Run" section for full details.
Map natural language to tax types: Airbnb/VRBO = rental, consulting = freelancer, etc.
Then run:
```bash
python3 finance.py setup '{"cards":"CARDS","currency":"CURRENCY","tax":"TYPE"}'
python3 finance.py setup-sheets
python3 finance.py parse-text '$25 Starbucks'
```
NEVER run setup without JSON.

### 2. /list-categories
```bash
python3 finance.py list-categories
```
Show the output to the user.

### 3. /add-category
Ask: category name and monthly budget. Then:
```bash
python3 finance.py add-category <name> <budget>
```

### 4. /modify-budget
Ask: which category and new amount. Then:
```bash
python3 finance.py modify-budget <category> <amount>
```

### 5. /remove-category
Ask: which category. Then:
```bash
python3 finance.py remove-category <name> yes
```

### 6. /balance
Ask: current balance amount. Then:
```bash
python3 finance.py balance <amount>
```

### 7. /income
Ask: income amount and source (optional). Then:
```bash
python3 finance.py income <amount> [source]
```

### 8. /payday
Ask: schedule type (biweekly/monthly), amount, pay days. Then:
```bash
python3 finance.py payday <schedule> <amount> [days]
```

### 9. /list-payments
```bash
python3 finance.py list-payments
```

### 10. /add-payment
Ask: name, amount, due day, account (optional). Then:
```bash
python3 finance.py add-payment <name> <amount> <day> [account]
```

### 11. /modify-payment
Ask: payment name and new amount. Then:
```bash
python3 finance.py modify-payment <name> <amount>
```

### 12. /remove-payment
Ask: payment name. Then:
```bash
python3 finance.py remove-payment <name>
```

### 13. /payment-check
```bash
python3 finance.py payment-check
```

### 14. /list-debts
```bash
python3 finance.py list-debts
```

### 15. /add-debt
Ask: creditor name, balance, APR (optional). Then:
```bash
python3 finance.py add-debt <name> <balance> [apr]
```

### 16. /update-debt
Ask: creditor name and current balance. Then:
```bash
python3 finance.py update-debt <name> <balance>
```

### 17. /pay-debt
Ask: creditor name and payment amount. Then:
```bash
python3 finance.py pay-debt <name> <amount>
```

### 18. /add-card
Ask: card/account name. Then:
```bash
python3 finance.py add-card "<name>"
```

### 19. /remove-card
Ask: card name. Then:
```bash
python3 finance.py remove-card <name>
```

### 20. /list-goals
```bash
python3 finance.py list-goals
```

### 21. /add-goal
Ask: goal name, target amount, deadline (optional). Then:
```bash
python3 finance.py add-goal <name> <target> [YYYY-MM-DD]
```

### 22. /save
Ask: goal name and amount. Then:
```bash
python3 finance.py save <goal> <amount>
```

### 23. /remove-goal
Ask: goal name. Then:
```bash
python3 finance.py remove-goal <name>
```

### 24. /new-tax-profile
Ask: business type (rental/freelancer/business) and description. Then:
```bash
python3 finance.py new-tax-profile '{"tax":"TYPE","tax_description":"DESCRIPTION"}'
```

### 25. /update-tax-profile
Show current profile, then ask what to do (regenerate / remove rule / add keywords). Then:
```bash
python3 finance.py update-tax-profile regenerate
python3 finance.py update-tax-profile remove-rule <number>
python3 finance.py update-tax-profile add-keywords <number> "kw1,kw2,kw3"
```

### 26. /current-tax-profile
```bash
python3 finance.py current-tax-profile
```

### 27. /cashflow
```bash
python3 finance.py cashflow
```

### 28. /status
Ask: specific category (optional, default = all). Then:
```bash
python3 finance.py status [category]
```

### 29. /weekly
```bash
python3 finance.py weekly-summary
```

### 30. /monthly
Ask: month (optional, default = current). Then:
```bash
python3 finance.py monthly-report [YYYY-MM]
```

### 31. /taxes
Ask: year (optional, default = current). Then:
```bash
python3 finance.py taxes [year]
```

### 32. /reconcile
User must attach a CSV file. Save to `/tmp/bank_statement.csv`, then:
```bash
python3 finance.py reconcile /tmp/bank_statement.csv [bank]
```
Supported banks: Chase, Discover, Citi, Wells Fargo. Show summary and ask confirmation for probable matches.

### 33. /batch-receipts
User must provide a file with receipt URLs. Save to `/tmp/receipt_links.txt`, then:
```bash
python3 finance.py batch-receipts /tmp/receipt_links.txt [account]
```

### 34. /add-rule
Ask: pattern, category, confidence (optional). Then:
```bash
python3 finance.py add-rule "<pattern>" <Category> [confidence]
```

### 35. /telemetry-on
```bash
python3 finance.py telemetry on
```

### 36. /telemetry-off
```bash
python3 finance.py telemetry off
```

### 37. /telemetry-status
```bash
python3 finance.py telemetry status
```

### 38. /telemetry-info
```bash
python3 finance.py telemetry info
```

## First Run — Installation & Setup

**IMPORTANT: Follow this sequence WITHOUT stopping. Ask questions ONE AT A TIME, wait for each answer.**

### After setup.sh completes, do this immediately:

**Step 1:** Ask: "What bank cards or accounts do you use? (e.g., Chase Visa, Discover, Cash)"
Wait for answer.

**Step 2:** Ask: "What currency? (e.g., USD, EUR, GBP, COP)"
Wait for answer.

**Step 3:** Ask: "Do you have a business for tax deductions? Options: no, rental, freelancer, business"
Wait for answer.
- If the user says anything related to rental/Airbnb/VRBO → use `"tax":"rental"`
- If the user says freelancer/contractor/consulting → use `"tax":"freelancer"`
- If the user says business/shop/store/side hustle → use `"tax":"business"`
- If anything else that is not "no" → use `"tax":"other"` and ask for a short description
- IMPORTANT: map the user's natural language to the correct tax type. "Airbnb" = rental, not literal "Airbnb".

**Step 4:** Run these 3 commands in sequence (do NOT stop between them):

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
python3 finance.py add-category "CategoryName" <budget>
```

## Language

The tracker responds in the user's preferred language (auto-detected from workspace USER.md). Supports English and Spanish.
