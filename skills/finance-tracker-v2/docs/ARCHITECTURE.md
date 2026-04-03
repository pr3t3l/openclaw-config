# Finance Tracker v2 — Architecture

## Overview

Finance Tracker is a personal finance skill for OpenClaw that tracks expenses via receipt photos and text, monitors budgets with fixed/variable categories, manages tax deductions using IRS-referenced rulepacks, and sends automated daily/weekly/monthly reports. It runs as a Python CLI that the OpenClaw agent calls via `exec`, with Google Sheets as the data store. The system is designed so that the LLM never controls flow — a deterministic Python state machine handles all transitions, validation, and data persistence.

## How It Works

The system has three layers:

**Interaction Layer (LLM + Telegram):** The agent receives user messages and photos. It does NOT decide what to ask or what step comes next. It passes the user's raw message to the Python CLI and relays the response back verbatim. The SKILL.md enforces this — the agent is a "message relay, not a financial advisor."

**Orchestration Layer (Python state machine):** `state_machine.py` controls the entire setup flow through 21 states. Each state validates input, persists progress to `setup_state.json`, and returns a JSON response with the next message to show. If the process is interrupted at any point, it resumes exactly where it left off. During runtime, `finance.py` dispatches commands to specialized modules.

**Execution Layer (CLI + APIs):** Python modules write to Google Sheets, call AI for parsing, manage merchant rules, calculate cashflow, and generate reports. All side effects are controlled by the orchestration layer. Every CLI call returns JSON to stdout.

## File Structure

```
finance-tracker/
├── SKILL.md                              # Agent router (setup relay + runtime intent mapping)
├── VERSION                               # "2.0.0"
├── requirements.txt                      # gspread, google-auth, google-auth-oauthlib
├── install/
│   ├── manifest.json                     # Package metadata, requirements, changelog
│   ├── schemas/
│   │   ├── income.v1.json                # Income source schema (source_type, account_label, is_regular)
│   │   ├── debt.v1.json                  # Debt schema (type, balance, apr, minimum_payment)
│   │   ├── budget.v1.json                # Budget category schema (type: fixed|variable)
│   │   └── bill.v1.json                  # Recurring bill schema (frequency for sinking funds)
│   ├── rulepacks/
│   │   ├── us-personal.v1.json           # No deductions (salary/W-2)
│   │   ├── us-rental-property.v1.json    # 9 Schedule E categories with IRS line refs
│   │   ├── us-freelance.v1.json          # 10 Schedule C categories
│   │   └── us-small-business.v1.json     # 12 Schedule C categories
│   └── migrations/
│       └── 001_initial.py                # Baseline config migration
├── scripts/
│   ├── finance.py                        # CLI entry point — 30+ commands
│   └── lib/
│       ├── __init__.py
│       ├── config.py                     # Atomic JSON I/O, config cache, path management
│       ├── errors.py                     # Typed error codes (FinanceError + ErrorCode enum)
│       ├── state_machine.py              # 21-state setup flow with checkpointing
│       ├── ai_parser.py                  # 3-level AI cascade (LiteLLM → API → llm-task)
│       ├── parser.py                     # Transaction parsing (regex → rules → AI)
│       ├── merchant_rules.py             # Two-tier merchant matching + auto-learning
│       ├── rules.py                      # Tax deduction keyword matching (base + user overlay)
│       ├── sheets.py                     # Google Sheets CRUD (10 tabs, by sheetId)
│       ├── budget.py                     # Budget status with fixed/variable alerts
│       ├── cashflow.py                   # Safe-to-spend with sinking funds
│       ├── payments.py                   # Payment calendar + due-soon alerts
│       ├── reports.py                    # Daily/weekly/monthly report generators
│       ├── reconcile.py                  # Bank CSV reconciliation + import
│       ├── csv_analyzer.py               # Recurring bill/income detection from CSV
│       ├── debt_optimizer.py             # Avalanche vs snowball payoff strategies
│       ├── telemetry.py                  # Anonymous setup-only telemetry (Supabase)
│       └── migrations.py                 # Sequential version migration runner
└── docs/
    └── SYSTEM_GUIDE.md                   # User-facing reference guide
```

## Setup Flow

21 states, executed in sequence. Each state writes to `setup_state.json` before transitioning. If interrupted, `setup-next` resumes at the saved state.

| # | State | What it does |
|---|-------|-------------|
| 1 | UNPACK | Verify skill files are present |
| 2 | PREFLIGHT | Check Python, deps, Google OAuth (live API test) |
| 3 | DETECT_CONTEXT | Auto-read name, language, timezone from OpenClaw config |
| 4 | SETUP_MODE_SELECT | User picks Quick (~2 min) or Full (~10 min) |
| 5 | INCOME_COLLECT | Gather income sources (loop: comma format or free text via AI) |
| 6 | INCOME_CONFIRM | Show formatted summary, require explicit "yes" |
| 7 | BUSINESS_RULES_MAP | Load tax rulepacks based on income source_types |
| 8 | BUSINESS_RULES_CONFIRM | Show deductible categories with IRS references |
| 9 | DEBT_COLLECT | Gather debts (loop, multiline, AI fallback) |
| 10 | DEBT_CONFIRM | Show debt summary with warnings |
| 11 | BUDGET_PRESENT | Show suggested categories with Fixed/Variable tags |
| 12 | BUDGET_COLLECT | Gather budgets (numbered refs, comma, multiline, AI fallback) |
| 13 | BUDGET_CONFIRM | Show budget with fixed/variable totals |
| 14 | BILLS_COLLECT | Gather recurring bills with frequency (multiline, AI fallback) |
| 15 | BILLS_CONFIRM | Show bills with monthly equivalents for sinking funds |
| 16 | REVIEW_ALL | Full data review with estimated surplus |
| 17 | SHEETS_CREATE | Create 10-tab Google Sheet via batch_update |
| 18 | CRONS_SETUP | Output 4 cron job specs for agent to register |
| 19 | TELEMETRY_OPT | Consent for anonymous setup-only telemetry |
| 20 | ONBOARDING_MISSIONS | Start interactive onboarding (3 missions) |
| 21 | COMPLETE | Setup finished |

**Quick mode** skips states 9-15 (debts, budgets, bills).

**Collector states** (5, 9, 12, 14) all follow the same pattern:
1. Check done signals (Python, not AI)
2. Check meta commands: `undo`, `list`, `edit N`, `skip`, `back`
3. Try regex/comma parsing
4. If that fails → call ai_parser for free-text parsing
5. Guard against AI amount truncation (compare regex vs AI amount)
6. Split multiline input by `\n`, process each line independently
7. Validate and append to collected data

## Runtime Commands

### Transaction Management
| Command | Description | Example |
|---------|-------------|---------|
| `add "<text>"` | Parse and log expense | `add "$15 Uber"` |
| `add-photo "<path>"` | Parse receipt photo via AI | `add-photo "/tmp/receipt.jpg"` |
| `undo` | Revert last transaction (5-min window) | `undo` |
| `transactions [N]` | List last N transactions | `transactions 20` |
| `import-csv "<path>" [--dry-run]` | Import bank CSV as transactions | `import-csv "/tmp/chase.csv"` |

### Budget & Spending
| Command | Description |
|---------|-------------|
| `budget-status` | Per-category spending vs budget |
| `safe-to-spend` | Daily safe spending amount |
| `list-categories` | Show all budget categories |
| `add-category "<name>" <budget> <type>` | Create budget category |
| `remove-category "<name>"` | Remove category |

### Reports (cron job targets)
| Command | Schedule | Description |
|---------|----------|-------------|
| `cashflow` | Mon-Fri 7:30am | Daily safe-to-spend + alerts + budget brief |
| `payment-check` | Daily 9am | Due-soon payment alerts |
| `weekly-review` | Sundays 8am | Spending breakdown + optimization |
| `monthly-report [month]` | 1st of month 8am | Full AI analysis |

### Tax & Deductions
| Command | Description |
|---------|-------------|
| `tax-summary [year]` | Deductions by category with rulepack info |
| `tax-export [year]` | CSV-ready export for accountant |

### Financial Planning
| Command | Description |
|---------|-------------|
| `debt-strategy` | Avalanche vs Snowball comparison |
| `savings-goals` | Show goals with daily required |
| `add-savings-goal "<name>" <target> "<deadline>"` | Create goal |
| `update-balance "<account>" <amount>` | Set account balance |

### Bank Reconciliation
| Command | Description |
|---------|-------------|
| `reconcile "<csv>"` | Match CSV against logged transactions |
| `analyze-csv "<csv>"` | Detect recurring bills/income from bank data |

### Merchant Rules
| Command | Description |
|---------|-------------|
| `list-rules` | Show auto-learned merchant rules |
| `add-rule "<pattern>" "<category>" [confidence]` | Manual rule |

### System
| Command | Description |
|---------|-------------|
| `install-check` | Verify all dependencies |
| `repair-sheet` | Validate sheet schema |
| `reconnect-sheets` | Refresh Google OAuth |
| `check-migrations` | Show pending migrations |
| `ai-backend` | Show detected AI backend |
| `help` | List all commands |

## Data Flow

### Transaction Processing

```
User input: "$15 Uber"
  │
  ���─ 1. Extract via regex: amount=$15, merchant="Uber"
  │
  ├─ 2. Normalize merchant: "UBER *TRIP" → "uber"
  │
  ├─ 3. Lookup merchant_rules.json
  │     ├─ HIT (confidence ≥ 0.8): category="Transportation" → skip AI ($0)
  │     ├─ MULTI-CATEGORY (walmart, target): → AI parse line items
  │     └─ MISS: → AI fallback
  │
  ├─ 4. AI fallback (if needed): parse_transaction() via 3-level cascade
  │
  ├─ 5. Auto-learn rule: save "uber" → "Transportation" (confidence 0.85)
  │
  ├─ 6. Write to Google Sheets (Transactions tab)
  │
  ├─ 7. Check budget alerts
  ���
  └─ 8. Return JSON with _message: "Added: $15 → Transportation (Uber)"
```

### Two-Tier Merchant Rules

**Tier 1 — Single-category merchants:** Uber, Netflix, Starbucks. Matched by normalized name substring. Auto-learned after first confirmed transaction. Confidence increases with each use (up to 0.98).

**Tier 2 — Multi-category merchants:** Walmart, Target, Costco, Home Depot, Amazon, CVS, Walgreens, etc. (19 merchants in `MULTI_CATEGORY_MERCHANTS`). These always trigger AI line-item parsing because a single receipt can span Groceries, Cleaning Supplies, and Electronics.

## Google Sheets Schema

All tabs referenced by numeric `sheetId` (stored in `sheets_config.json`), never by tab name. User can rename tabs without breaking anything.

| Tab | Columns |
|-----|---------|
| **Transactions** | date, amount, merchant, category, subcategory, card, input_method, confidence, matched, source, notes, timestamp, month, receipt_id, receipt_number, store_address, tax_deductible, tax_category, type, business_id |
| **Budget** | category, type, monthly_limit, threshold, current_spent, pct_used |
| **Payment Calendar** | name, amount, due_day, frequency, account, autopay, apr, promo_expiry, next_due |
| **Monthly Summary** | month, total_income, total_expenses, total_fixed, total_variable, surplus, savings_contrib, debt_payments, deductible_total |
| **Debt Tracker** | name, type, balance, apr, minimum_payment, monthly_payment, payoff_date_est, total_interest_est, notes |
| **Rules** | merchant_pattern, category, subcategory, requires_line_items, confidence, times_used, last_used, created_by |
| **Reconciliation Log** | date, amount, merchant_bank, merchant_receipt, status, receipt_row, csv_row, resolved_by, notes |
| **Cashflow Ledger** | date, account, merchant, amount_signed, flow_type, category, subcategory, notes, source, timestamp, month |
| **Businesses** | business_id, name, type, schedule, rulepack_id, active, created_at |
| **Savings Goals** | goal, target, saved, deadline, daily_required, status |

Initial data written via single `batch_update` call (headers + budget rows + payment calendar + debt tracker + business info).

## AI Parser

### 3-Level Cascade

**Level 2 — LiteLLM proxy (preferred):** Checks `http://127.0.0.1:4000/health`. If up, discovers available models via `GET /models` and picks the cheapest (prefers mini/flash variants). No hardcoded model names.

**Level 3 — Direct API:** Checks openclaw.json providers, then env vars `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`. Anthropic Messages API is supported with format translation to OpenAI-compatible responses.

**Level 1 — llm-task (fallback):** If no backend is available, returns `{llm_request: true, system, user}` for the agent to process via the `llm-task` tool. The SKILL.md instructs the agent how to handle this.

### When AI is Used vs Not

- **Known merchant + high confidence** → merchant rule hit, $0 AI cost
- **Multi-category merchant** → AI parses line items ($)
- **Unknown merchant** → AI parses, then auto-learns rule for next time
- **Free-form setup input** → AI parses when comma format fails
- **Receipt photos** → always AI
- **Weekly/monthly reports** → AI generates analysis narrative

### Amount Truncation Guard

AI models sometimes drop leading digits from amounts ($3190.12 ��� $190.12). After every AI parse in collectors, the system:
1. Extracts amount from raw text via regex
2. Compares regex amount vs AI amount
3. If regex > AI × 1.5 → overrides with regex amount

## Tax Rulepacks

Rulepacks are pre-compiled JSON files with IRS-referenced deductible categories. They are loaded during setup based on income `source_type`:

| Income Type | Rulepack | IRS Form | Categories |
|-------------|----------|----------|------------|
| salary/other | us-personal.v1 | N/A | 0 (no deductions) |
| rental | us-rental-property.v1 | Schedule E | 9 (cleaning, maintenance, insurance, utilities, linens, professional, furnishing, advertising, travel) |
| freelance | us-freelance.v1 | Schedule C | 10 (office, equipment, internet, professional, education, marketing, travel, home office, insurance, bank fees) |
| business | us-small-business.v1 | Schedule C | 12 (COGS, office, equipment, rent, utilities, shipping, marketing, professional, insurance, vehicle, travel, bank fees) |

Each category has: `category` (snake_case ID), `irs_reference` (e.g. "Schedule E Line 7"), `description`, and `keywords` for matching.

Multiple income types load multiple rulepacks. User customizations go to `rules.user.json` (overlay), never modifying the original rulepack.

### Adding a New Rulepack

1. Create `install/rulepacks/<jurisdiction>-<type>.v1.json`
2. Follow the existing schema: `rulepack_id`, `jurisdiction`, `business_type`, `irs_form`, `deductible_categories[]`
3. Add the `source_type` → `rulepack_id` mapping to `SOURCE_TYPE_TO_RULEPACK` in `state_machine.py`

## Cron Jobs

Registered via OpenClaw native cron during setup. The agent registers them using specs from the CRONS_SETUP state response.

| Job | Cron Schedule | Timezone | Command |
|-----|---------------|----------|---------|
| Daily Cashflow | `30 7 * * 1-5` (Mon-Fri 7:30am) | From config | `finance.py cashflow` |
| Payment Check | `0 9 * * *` (Daily 9am) | From config | `finance.py payment-check` |
| Weekly Review | `0 8 * * 0` (Sundays 8am) | From config | `finance.py weekly-review` |
| Monthly Report | `0 8 1 * *` (1st of month 8am) | From config | `finance.py monthly-report` |

All jobs use `sessionTarget: "isolated"` and `delivery: {mode: "announce", channel: "last"}` — no Telegram bot token needed.

## Telemetry

### What's Collected (setup stages only)

| Field | Example |
|-------|---------|
| event | "setup_stage_complete", "setup_complete", "preflight_failed" |
| v | "2.0.0" |
| stage | "INCOME_COLLECT" |
| result | "ok" or "error" |
| duration_bucket | "5-15s" |
| error_code | "AUTH_GOOGLE_INVALID" |
| setup_mode | "full" or "quick" |
| detected_language | "es" |
| income_source_count | 2 |
| rulepack_ids | ["us-rental-property.v1"] |

### What's NEVER Collected

Names, emails, phone numbers, chat IDs, account names, balances, transactions, merchant names, receipt text, Google Sheet URLs, API keys, IP addresses. No user_id, no install_id, no session_id. Zero traceability.

### Supabase Table

```sql
CREATE TABLE telemetry_v2 (
  id bigserial primary key,
  created_at timestamptz default now(),
  event text not null,
  v text, stage text, result text,
  duration_bucket text, error_code text,
  setup_mode text, detected_language text, distribution text,
  income_source_count int, debt_count int,
  business_type_count int, custom_category_count int,
  rulepack_ids jsonb, cron_job_count int,
  reviewed boolean default false
);
```

RLS policy: anon insert only (no read, update, or delete).

## Configuration Files

All stored in `~/.openclaw/products/finance-tracker/config/`.

| File | Created | Purpose |
|------|---------|---------|
| `tracker_config.json` | REVIEW_ALL state | Main config: user, categories, balance, tax, payments, savings, income, debts, telemetry, onboarding |
| `setup_state.json` | Every state transition | Setup checkpoint: current_state, collected data, mode. Deleted after COMPLETE. |
| `sheets_config.json` | SHEETS_CREATE state | Spreadsheet ID, URL, tab sheetIds with schema versions |
| `merchant_rules.json` | First `add` command | Auto-learned merchant→category rules with confidence and usage tracking |
| `rules.base.json` | BUSINESS_RULES_MAP state | Compiled deduction rules from rulepacks (read-only) |
| `rules.user.json` | User edits | User's custom deduction rule overrides |
| `last_transaction.json` | Every `add` command | Last transaction for 5-minute undo window |

All writes are atomic: write to `.tmp` file, then `os.replace()`.

## Error Codes

| Code | When it triggers |
|------|-----------------|
| `SETUP_INCOMPLETE` | Runtime command before setup is done |
| `SETUP_INVALID_INPUT` | Bad input during a setup collector |
| `SETUP_STATE_CORRUPT` | setup_state.json is unreadable |
| `SETUP_ALREADY_COMPLETE` | Trying to run setup when already done |
| `CONFIG_NOT_FOUND` | tracker_config.json missing |
| `CONFIG_CORRUPT` | tracker_config.json is invalid JSON |
| `CONFIG_WRITE_FAILED` | Atomic write failed |
| `SCHEMA_NOT_FOUND` | Missing schema file |
| `SCHEMA_VALIDATION` | Data doesn't match schema |
| `MISSING_DEPENDENCY` | Python package or binary not found |
| `GOG_AUTH_MISSING` | Google OAuth credentials missing |
| `SHEETS_ERROR` | Google Sheets API error |
| `AI_TIMEOUT` | AI call exceeded timeout |
| `AI_INVALID_RESPONSE` | AI returned unparseable response |
| `AI_NO_KEY` | No AI backend available |
| `UNKNOWN_COMMAND` | Unrecognized CLI command |
| `INVALID_ARGS` | Missing or wrong arguments |
| `INTERNAL` | Unexpected error |

All errors serialize to JSON: `{error: true, code, message, context}`.

## Lessons Learned

### Why state machine over prompt-based setup

The LLM added its own questions, skipped steps, and reordered the flow when given prompt-based instructions. A Python state machine makes every transition deterministic — the LLM cannot deviate because it only relays `message` fields from JSON responses. This was validated in end-to-end Telegram testing where GPT-5.4 still tried to add commentary despite SKILL.md rules; the fix was making the SKILL.md governance language more aggressive ("YOU ARE A MESSAGE RELAY, NOT A FINANCIAL ADVISOR").

### Why sheetId over tab names

If a user renames "Transactions" to "Transacciones", tab-name-based code breaks silently. Google Sheets assigns permanent numeric `sheetId` values that never change regardless of renames. All our code references tabs by ID from `sheets_config.json`.

### Why subprocess+curl over Python requests

Python `requests` library fails on WSL2 for long API calls (hangs indefinitely). The v1 codebase discovered this the hard way. `subprocess.run(["curl", ...])` with `--max-time` works reliably and supports proper timeout handling.

### Why regex override for AI-parsed amounts

LLMs consistently truncate leading digits from dollar amounts ($3190.12 → $190.12). The `_fix_ai_amount()` guard extracts the amount via regex from the raw text and overrides the AI result if the regex amount is >1.5x larger. This was caught during end-to-end testing.

### Why sinking funds matter

Without sinking funds, a user with $500 available appears safe — until a $600 semi-annual car insurance bill hits. The system provisions non-monthly bills daily ($600/180 = $3.33/day) and subtracts this from safe-to-spend, preventing the surprise.

### Why AI fallback in collectors

Users don't type in perfect comma-separated format. "Scout Motors $3190 biweekly salary wells fargo" should work, not just "Scout Motors, 3190, biweekly, salary, Wells Fargo". Every collector tries comma parsing first (fast, no AI cost), then falls back to AI for free-text parsing.

## How to Extend

### Adding a new command

1. Add `cmd_<name>(args)` function in `finance.py`
2. Add entry to `runtime_commands` dict in `main()`
3. Add intent mapping row to `SKILL.md`
4. Add entry to `cmd_help()` list

### Adding a new rulepack

1. Create `install/rulepacks/<id>.json` with `rulepack_id`, `jurisdiction`, `business_type`, `irs_form`, `deductible_categories[]`
2. Add source_type mapping in `state_machine.py` `SOURCE_TYPE_TO_RULEPACK`
3. Add income source_type option to `INCOME_COLLECT` prompt and validation

### Adding a new collector state

1. Add state to `SetupState` enum in `state_machine.py`
2. Add to `STATE_ORDER` list (position matters for progress calculation)
3. Add to `QUICK_SKIP` if optional
4. Implement `_state_<name>(self, text)` method
5. Wire transitions from previous and to next state

### Adding a new Google Sheet tab

1. Add entry to `TAB_DEFS` dict in `sheets.py` with title and headers
2. Add initial data population in `create_spreadsheet()` if needed
3. Add read/write convenience functions
4. Tab will be auto-created on next setup; existing users need a migration

### Adding a migration

1. Create `install/migrations/NNN_description.py` with a `migrate()` function
2. The function receives no arguments; use `config.py` to read/write config
3. Must be idempotent (safe to run twice)
4. Will run automatically on next `check-migrations` or setup
