# Finance Tracker — System Guide v1.0.10

Complete reference for the Finance Tracker skill. Covers every module, command, cron job, and integration point.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Modules](#modules)
3. [Commands (34 total)](#commands)
4. [Cron Jobs](#cron-jobs)
5. [Google Sheets Structure](#google-sheets-structure)
6. [AI Models Used](#ai-models-used)
7. [Rule Engine](#rule-engine)
8. [Tax Deduction System](#tax-deduction-system)
9. [Telemetry](#telemetry)
10. [Configuration Files](#configuration-files)

---

## Architecture Overview

```
User (Telegram) → Agent → finance.py → lib modules → Google Sheets
                                           ↓
                                      AI (LiteLLM)
                                           ↓
                                    Supabase (telemetry)
```

**Data flow:**
1. User sends expense (text, photo, CSV) → `parser.py` parses it (rules first, AI fallback)
2. Agent confirms with user → `logger.py` writes to Google Sheets
3. `budget.py` checks thresholds → alerts if near/over limit
4. Cron jobs send daily/weekly/monthly reports via Telegram

**Key principle:** Rules engine tries first (free, fast). AI only called when rules can't match.

---

## Modules

### parser.py — Expense Parser

Converts raw input into structured transaction data.

**Three input types:**
- **Text:** `"$45 Publix Chase"` → extracts amount, merchant, card using regex + AI
- **Photo:** Receipt image → base64-encoded, sent to vision AI model
- **CSV:** Bank statement → auto-detects bank format (Chase, Discover, Citi, Wells Fargo)

**How parsing works:**
1. Tries `rules.match_rules(merchant)` first — if match found, skips AI
2. If no rule matches, calls AI with system prompt containing: categories, cards, tax rules
3. For photos with multiple categories: AI splits into transaction groups
4. Income detection: keywords like "paycheck", "ingreso", "deposito" → type="income"

**Output fields:**
- `amount`, `merchant`, `date`, `category`, `subcategory`, `card`
- `confidence` (0-1), `input_method` (text/photo/csv)
- `tax_deductible`, `tax_category`, `needs_confirmation`
- `rule_matched` (true = rule engine, false = AI parsed)
- `items[]` (for receipts with multiple items)

**Split receipts:** When a receipt has items in 3+ categories, returns a `receipt_id` + `transactions[]` array for grouped logging.

---

### logger.py — Transaction Logger

Writes confirmed transactions to Google Sheets and tracks budget status.

**Functions:**
- `log_transaction(tx)` — Writes expense to Transactions tab. Returns month spending total, budget %, and alert if threshold crossed.
- `log_income(tx)` — Writes income, auto-updates available balance in config. Returns old/new balance + month income total.
- `log_split_receipt(receipt)` — Logs all transactions from a multi-category receipt.
- `format_confirmation(tx, budget)` — Generates user-facing message: "Logged: $45.32 at Publix (Groceries) with Chase. Groceries: $195/$250 (78%)."

**Budget alerts:** Triggered at configurable thresholds (default 80%). Escalates: CAUTION (80%) → ALERT (95%) → OVER (100%).

**Auto-fills:** timestamp, month (YYYY-MM), matched=false, source="receipt", type="expense".

---

### cashflow.py — Daily Cashflow

Morning "safe to spend" calculation.

**Formula:**
```
safe_daily = (available_balance - upcoming_14d_payments) / days_until_payday - daily_savings_quota
```

**`daily_cashflow()` output includes:**
- Available balance
- Upcoming payments in next 14 days (name, amount, due day)
- Days until next payday + expected paycheck
- Safe-to-spend per day
- Risk indicator (green/yellow/red based on amount)
- Per-category budget status with % bars
- Savings goals progress

**Other functions:**
- `update_balance(amount)` — Sets current available balance
- `update_savings(goal, amount)` — Adds contribution to a savings goal
- `update_savings_target(goal, target)` — Changes goal target
- `update_payday(schedule, amount, dates)` — Sets pay schedule (biweekly/monthly)

---

### budget.py — Budget Monitor & Weekly Reports

**`weekly_summary()`:**
- Month-to-date total spending + daily average
- Per-category: amount/budget, %, status flag (OK/CAUTION/ALERT/OVER)
- Upcoming payments in next 7 days
- AI analysis: 3-4 sentences on spending patterns + actionable tip

**`budget_status_brief(month)`:**
- Compact version for daily cashflow
- Only shows categories with spending >0 or >50% of budget

---

### analyst.py — Monthly AI Report

**`monthly_report(month)`:**
- Total spent in month
- Per-category breakdown with budget comparison
- Top 5 merchants by spending
- Fixed monthly payments total
- Promo APR expiry warnings (if any debt promo expires within 90 days)
- Tax deduction summary (if enabled)
- AI analysis: insights on over/under categories, savings opportunities, motivational note

Uses `ANALYSIS_MODEL` (can be a more capable model than the parser).

---

### reconcile.py — CSV Bank Reconciliation

Matches bank CSV rows against existing receipt transactions.

**Process:**
1. **Auto-detect bank** by CSV headers (Chase=memo, Discover=trans. date, etc.)
2. **Parse rows** → {date, amount, merchant, raw_category, raw_type}
3. **Match against receipts** — scoring: +1 exact amount, +1 date (±2 days), +1 fuzzy merchant
4. **Score ≥2** = matched (amount + one other field). Score 1 = probable (needs manual review).
5. **Unmatched rows:**
   - Check for payment/transfer/income keywords
   - Try rules engine for merchant categorization
   - Batch AI classification for unknowns → auto-creates rules (confidence 0.80)
6. **Auto-log** unmatched expenses to Transactions + Cashflow tabs

**Output:** Summary with matched count, auto-logged count, probable matches for review, unmatched receipts.

---

### payments.py — Payment Reminders

**`check_payments()`:**
- Scans all configured payments
- Generates alerts for: due today, due tomorrow, due in 3 days
- Promo APR expiry warnings at 60d, 30d, 7d, 0d milestones
- Shows autopay status (warning if not enabled)

**`payment_summary_14d()`:**
- Returns total + list of payments due in next 14 days
- Used by cashflow to calculate safe spending

---

### batch_receipts.py — Walmart Receipt Processor

Processes digital Walmart receipt links in batch.

**Process:**
1. Fetches each URL, extracts JSON from page
2. Parses: items (name/qty/price), subtotal, tax, total, payment
3. Deduplication via `processed_receipts.json`
4. Classifies items: rules → heuristic regex → AI batch
5. Flags potential Airbnb/business items for user confirmation
6. Distributes receipt tax proportionally across items
7. If matching CSV row exists (amount ±$0.02, date ±2 days): replaces generic row with itemized transactions

---

### sheets.py — Google Sheets Client

**Authentication:** Uses GOG (Google OAuth Gateway) credentials at `~/.config/gogcli/credentials.json`.

**Read:** `get_all_records()` → list of dicts, filtered by category/month/year.

**Write:** `append_rows()` in 100-row batches with 1s throttle between batches.

**Key functions:**
- `get_month_spending(category, month)` — Category total for month (excludes income)
- `get_all_month_spending(month)` — All categories in one call
- `get_transactions_for_month(month)` — Full transaction list
- `get_tax_deductions(year, month)` — Filters tax_deductible=true
- `get_recent_transactions(days)` — For duplicate detection

---

### rules.py — Rule Engine

Fast merchant-to-category matching without AI calls.

**Rule structure:**
```json
{
  "merchant_pattern": "publix",
  "category": "Groceries",
  "confidence": 0.85,
  "amount_condition": "any",
  "default_account": "Chase",
  "created_by": "manual|system_correction|ai_auto"
}
```

**Matching:** Normalizes merchant (lowercase, strips prefixes like "TST*", removes store #/city/ZIP), then finds highest-confidence substring match.

**Learning:** After 2+ corrections to same category for a merchant, auto-creates a rule. Rules also auto-created during CSV reconciliation from AI classifications.

---

### telemetry.py — Anonymous Telemetry

Fire-and-forget POST to Supabase. Never blocks main flow.

**Events tracked:**
| Event | When | Data |
|-------|------|------|
| `install` | Setup wizard completes | OS, Python, GOG available, AI provider type |
| `setup_complete` | Wizard done | language, currency, cards_count, tax_enabled, categories_count |
| `command` | Every command | command name, duration_ms |
| `error` | On failure | command name, error type (never the message) |
| `reconcile` | After CSV reconcile | bank, tx_count, matched, ai_rules_created |

**Every event includes:** `install_id` (random UUID), `v` (version number).

**User controls:** `finance.py telemetry off/on/status/info`.

---

## Commands

### Setup (1)
| # | Command | What it does |
|---|---------|-------------|
| 1 | `/setup` | Runs wizard: auto-detects name+language from USER.md, asks cards/currency/tax, creates config + Google Sheet |

### Categories + Budgets (4)
| # | Command | What it does |
|---|---------|-------------|
| 2 | `/list-categories` | Shows all categories with monthly budget, current spending, and % |
| 3 | `/add-category <name> <budget>` | Creates new category with monthly budget limit |
| 4 | `/modify-budget <category> <amount>` | Changes monthly budget for existing category |
| 5 | `/remove-category <name>` | Deletes a category (with confirmation) |

### Balance + Income (3)
| # | Command | What it does |
|---|---------|-------------|
| 6 | `/balance <amount>` | Sets current available balance (used in cashflow calculations) |
| 7 | `/income <amount> [source]` | Registers income, auto-updates balance, logs to Sheets |
| 8 | `/payday <schedule> <amount> [days]` | Configures pay schedule: biweekly/monthly, amount, which days |

### Payments (5)
| # | Command | What it does |
|---|---------|-------------|
| 9 | `/list-payments` | Shows all bills with amount, due day, account, autopay status, APR |
| 10 | `/add-payment <name> <amount> <day> [account]` | Adds recurring bill |
| 11 | `/modify-payment <name> <amount>` | Changes payment amount |
| 12 | `/remove-payment <name>` | Deletes a recurring bill |
| 13 | `/payment-check` | Checks for upcoming bills (today, tomorrow, 3 days) |

### Debts (4)
| # | Command | What it does |
|---|---------|-------------|
| 14 | `/list-debts` | Shows all debts from Debt Tracker sheet tab |
| 15 | `/add-debt <name> <balance> [apr]` | Adds debt entry to Sheets |
| 16 | `/update-debt <name> <balance>` | Updates current balance for a debt |
| 17 | `/pay-debt <name> <amount>` | Records payment, reduces balance |

### Cards (2)
| # | Command | What it does |
|---|---------|-------------|
| 18 | `/add-card <name>` | Adds card/account to config (used by parser for matching) |
| 19 | `/remove-card <name>` | Removes card from config |

### Savings Goals (4)
| # | Command | What it does |
|---|---------|-------------|
| 20 | `/list-goals` | Shows all goals with saved/target, %, daily rate needed, deadline |
| 21 | `/add-goal <name> <target> [deadline]` | Creates savings goal (default deadline: 6 months) |
| 22 | `/save <goal> <amount>` | Adds contribution to a savings goal |
| 23 | `/remove-goal <name>` | Deletes a savings goal |

### Tax Profile (3)
| # | Command | What it does |
|---|---------|-------------|
| 24 | `/new-tax-profile` | AI wizard: asks business type, generates deduction rules + keywords |
| 25 | `/update-tax-profile` | Modify: regenerate with AI, remove a rule, or add keywords to existing rule |
| 26 | `/current-tax-profile` | Shows active tax profile: business type, schedule, rules, keywords |

### Reports (5)
| # | Command | What it does |
|---|---------|-------------|
| 27 | `/cashflow` | Daily safe-to-spend: balance - upcoming payments / days to payday |
| 28 | `/status [category]` | Budget overview: all categories or specific one with month spending |
| 29 | `/weekly` | Week summary: per-category breakdown + AI analysis with tips |
| 30 | `/monthly [YYYY-MM]` | Month report: spending, top merchants, AI insights, tax summary |
| 31 | `/taxes [year]` | Tax deduction report: total by category for the year |

### Data (3)
| # | Command | What it does |
|---|---------|-------------|
| 32 | `/reconcile` + CSV | Matches bank CSV against receipts, auto-categorizes unknowns, logs new transactions |
| 33 | `/batch-receipts` + links | Processes Walmart receipt URLs, itemizes and replaces generic CSV rows |
| 34 | `/add-rule <pattern> <category>` | Creates manual categorization rule for merchant matching |

---

## Cron Jobs

Installed via `bash setup_crons.sh`. All times are **America/New_York (EST)**.

| Job | Schedule | Time | What it does |
|-----|----------|------|-------------|
| **cashflow** | Mon-Fri | 7:30 AM | Sends morning safe-to-spend message with balance, upcoming payments, budget status, savings progress |
| **payment-check** | Daily | 9:00 AM | Checks for bills due today/tomorrow/3 days. Warns about promo APR expiry. |
| **weekly-summary** | Sundays | 8:00 AM | Week breakdown by category + AI analysis with spending patterns and tips |
| **monthly-report** | 1st of month | 8:00 AM | Full month report with AI insights, top merchants, tax summary |

**How crons work:**
1. `setup_crons.sh` installs crontab entries tagged `# finance-tracker`
2. Each entry calls `cron_runner.sh <job_name> <subcommand>`
3. `cron_runner.sh` runs `finance.py`, captures output
4. If output has content → sends via Telegram API (max 4096 chars)
5. If error → sends error alert (first 500 chars)
6. Logs to `skills/finance-tracker/logs/<job_name>.log`

**Manage:**
```bash
bash setup_crons.sh          # Install all 4 crons
bash setup_crons.sh --remove # Remove all finance-tracker crons
bash test_crons.sh           # Test each cron manually
```

---

## Google Sheets Structure

5 tabs, auto-created by `finance.py setup-sheets`:

### Transactions (main data)
| Column | Description |
|--------|-------------|
| date | YYYY-MM-DD |
| amount | Dollar amount |
| merchant | Store/vendor name |
| category | Budget category |
| subcategory | Optional detail |
| card | Payment method |
| input_method | text / photo / csv |
| confidence | 0-1 (rule=0.85+, AI=0.7) |
| matched | true if reconciled with bank |
| source | receipt / csv / manual |
| notes | Parser notes |
| timestamp | ISO datetime |
| month | YYYY-MM (for fast filtering) |
| receipt_id | Groups split receipts |
| receipt_number | Store receipt # |
| store_address | Store location |
| tax_deductible | true/false |
| tax_category | Deduction category ID |
| type | expense / income / payment / transfer |

### Monthly Summary
| Column | Description |
|--------|-------------|
| month | YYYY-MM |
| total_spent | Sum of expenses |
| total_budget | Sum of all budgets |
| categories_over | Count of over-budget categories |
| top_merchant | Highest-spend merchant |
| notes | AI-generated insights |

### Debt Tracker
| Column | Description |
|--------|-------------|
| month | YYYY-MM |
| creditor | Debt name |
| balance | Current balance |
| minimum_payment | Monthly minimum |
| apr | Interest rate % |
| notes | Notes |

### Reconciliation Log
| Column | Description |
|--------|-------------|
| date, amount | Transaction details |
| merchant_bank | Name from bank CSV |
| merchant_receipt | Name from receipt |
| status | matched / probable / unmatched |
| receipt_row, csv_row | Row references |
| resolved_by | auto / manual / ai |
| notes | Match details |

### Cashflow Ledger
| Column | Description |
|--------|-------------|
| date, account, merchant | Transaction details |
| amount_signed | Positive=income, Negative=expense |
| flow_type | expense / income / payment / transfer |
| category, subcategory | Classification |
| notes, source, timestamp, month | Metadata |

---

## AI Models Used

Configured in `config.py`, auto-detected from `openclaw.json`:

| Model | Used for | Temperature |
|-------|----------|-------------|
| `PARSE_MODEL` | Text/photo parsing, weekly analysis | 0.1 (parsing), 0.3 (analysis) |
| `CLASSIFY_MODEL` | Batch merchant classification, tax profile generation | 0.1 (classify), 0.3 (tax) |
| `ANALYSIS_MODEL` | Monthly reports | 0.7 |

**Cost optimization:** Rules engine handles known merchants (free). AI only called for unknowns. Batch classification groups multiple merchants in one API call.

---

## Rule Engine

Rules are stored in `config/rules.json`. They match merchants to categories without AI.

**How rules are created:**
1. **Manual:** `/add-rule "publix" Groceries 0.9`
2. **Auto-correction:** After 2+ user corrections for same merchant → rule auto-created
3. **AI reconciliation:** When CSV reconcile classifies unknown merchants → rules saved at 0.80 confidence

**Matching priority:** Longest pattern match wins. If tie, highest confidence wins.

---

## Tax Deduction System

Configured per business type via AI-powered wizard.

**Supported types:** Rental property (Schedule E), Freelancer (Schedule C), Small business (Schedule C), Other.

**How it works:**
1. AI generates: tax_categories (4-8), ask_rules (keyword patterns), never_ask (personal items)
2. When parsing receipts, items matching business keywords get `needs_confirmation: true`
3. User confirms: "business" or "personal" per item
4. Confirmed items logged with `tax_deductible: true` + `tax_category`
5. Food items NEVER flagged as deductible

**Reports:** `/taxes 2026` shows annual deduction totals by category.

---

## Telemetry

Anonymous usage data sent to Supabase (opt-out available).

**What is collected:** OS, Python version, AI provider type, command names, error types, duration, version number.

**What is NEVER collected:** Names, amounts, merchants, API keys, financial data, message content.

**Supabase table:** `telemetry` with columns: id, created_at, install_id, event, data (jsonb), reviewed (boolean).

**Dashboard queries:**
```sql
-- New unreviewed events
SELECT * FROM telemetry WHERE reviewed = false ORDER BY id DESC;

-- Errors by version
SELECT data->>'v' as version, data->>'type' as error, count(*)
FROM telemetry WHERE event = 'error'
GROUP BY version, error ORDER BY count DESC;

-- Most used commands
SELECT data->>'name' as command, count(*)
FROM telemetry WHERE event = 'command'
GROUP BY command ORDER BY count DESC;
```

---

## Configuration Files

### tracker_config.json (main config)
```
config/tracker_config.json
├── user: {name, language, currency, cards[], spreadsheet_name, setup_complete}
├── categories: {Name: {monthly, threshold}}
├── balance: {available, pay_schedule, pay_dates[], expected_paycheck}
├── tax: {enabled, business_type, schedule_type, ask_rules[], never_ask[]}
├── payments: [{name, amount, due_day, account, autopay, apr}]
├── savings: [{goal, target, saved, deadline}]
└── telemetry: {install_id, enabled}
```

### rules.json (categorization rules)
```
config/rules.json
└── [{merchant_pattern, category, confidence, amount_condition, default_account, created_by}]
```

### Key paths
| File | Purpose |
|------|---------|
| `~/.openclaw/workspace/USER.md` | Auto-detected: user name + language |
| `~/.openclaw/openclaw.json` | Auto-detected: AI provider URL + key + models |
| `~/.config/gogcli/credentials.json` | Google OAuth via GOG |
| `skills/finance-tracker/config/` | tracker_config.json + rules.json |
| `skills/finance-tracker/logs/` | Cron job logs |
