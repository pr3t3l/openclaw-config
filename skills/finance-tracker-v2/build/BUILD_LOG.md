# Build Log — Finance Tracker v2

## Phase 1: Foundation (2026-04-02)

### Files Created

| File | Purpose |
|------|---------|
| `src/VERSION` | Version string: `2.0.0` |
| `src/requirements.txt` | Minimal deps: gspread, google-auth, google-auth-oauthlib |
| `src/scripts/lib/__init__.py` | Package init |
| `src/scripts/lib/errors.py` | Typed error system — `FinanceError` + `ErrorCode` enum |
| `src/scripts/lib/config.py` | Unified config access with atomic writes, setup state mgmt |
| `src/scripts/lib/state_machine.py` | Core `SetupStateMachine` — 13 states, meta commands, checkpointing |
| `src/install/schemas/income.v1.json` | Income source schema |
| `src/install/schemas/debt.v1.json` | Debt/credit balance schema |
| `src/install/schemas/budget.v1.json` | Budget category schema |
| `src/install/schemas/bill.v1.json` | Recurring bill schema |
| `src/scripts/finance.py` | CLI entry point — routes to state machine |

### Decisions Made

1. **Runtime data in `~/.openclaw/products/finance-tracker/`** — Keeps src/ read-only, config lives at runtime path.
2. **Atomic writes everywhere** — Write to `.tmp` then `os.replace()`. No corrupt configs on crash.
3. **13-state setup flow** — UNPACK → DETECT_USER → CARDS → CURRENCY → INCOME → DEBTS → BUDGETS → BILLS → TAX_CHECK → TAX_DESCRIBE → REVIEW → SHEETS → COMPLETE.
4. **Quick mode** — Skips INCOME, DEBTS, BUDGETS, BILLS for fast setup (cards + currency + tax only).
5. **Bilingual** — All prompts have English and Spanish variants, auto-detected from USER.md.
6. **DONE_SIGNALS** — Both English and Spanish termination words for multi-item collection states.
7. **META_COMMANDS** — `undo`, `list`, `edit N`, `skip`, `back` available in all collection states.
8. **JSON-only output** — Every CLI call returns structured JSON. LLM never controls flow.
9. **Schemas are validation specs** — JSON Schema draft 2020-12 with proper constraints (min/max, enums, required fields).

### Cherry-Picked from v1

| Pattern | Source | Adaptation |
|---------|--------|------------|
| `read_user_md()` | `v1/config.py:14-36` | Identical logic, detects name + language from USER.md |
| Config accessor pattern | `v1/config.py:268-313` | Same getter functions, now with atomic writes |
| Config cache + invalidation | `v1/config.py:229-264` | Same pattern, `_CONFIG_CACHE` with manual invalidation |
| Tax type selection (1-5) | `v1/setup_wizard.py:121-137` | Same choices, now state-machine driven |
| Default categories | `v1/setup_wizard.py:79-91` | Same defaults used when user skips budgets |
| Payment structure | `v1/setup_wizard.py` | Same fields: name, amount, due_day, autopay, apr |

### What Changed from v1

- **No interactive `input()` calls** — Everything flows through `process(user_input)` for bot/LLM compatibility.
- **Separate setup_state.json** — v1 baked state into tracker_config.json. v2 checkpoints separately for clean resume.
- **Typed errors** — v1 used `sys.exit(1)` and `print()`. v2 returns structured `FinanceError` as JSON.
- **No telemetry in Phase 1** — Will be added in Phase 2.
- **No AI calls in setup** — Tax profile AI generation deferred to Phase 2 (ai_parser module).

### Tests Run

| Command | Result | Notes |
|---------|--------|-------|
| `finance.py install-check` | PASS | All checks OK except gog_auth (expected — no GOG creds in test env) |
| `finance.py preflight` | PASS | Returns `UNPACK` state, `can_resume: false` |
| `finance.py setup-next "start"` | PASS | Auto-detected Alfredo/es, advanced to CARDS, greeted in Spanish |
| `finance.py setup-status` | PASS | Shows `CARDS` state with collected user data, resume works |
| `finance.py setup-reset` | PASS | Clears state cleanly |

### Problems Encountered

- **No reference docs** — `docs/IMPLEMENTATION_GUIDE.md` and `docs/SESSION_PLAN.md` don't exist yet. Built from v1 source analysis and the task prompt spec.
- **gog_auth check** — GOG credentials directory exists but may be empty in some environments. install-check correctly reports this.

### What Session 2 Needs

1. **AI parser module** (`src/scripts/lib/ai_parser.py`) — subprocess+curl pattern from v1, no Python requests.
2. **Tax profile generation** — Hook into TAX_DESCRIBE state to call AI for tax profile.
3. **Sheets integration** (`src/scripts/lib/sheets.py`) — Create spreadsheet on SHEETS state.
4. **Transaction parsing** — parse-text, parse-photo commands.
5. **Logging** — log, log-split, income commands.
6. **Rules engine** — merchant matching from v1.
7. **Wire up remaining CLI commands** beyond setup.

---

## Phase 1.1: Alignment Patch (2026-04-02)

Aligned state machine with spec at `docs/workflow_bible_finance specs V2.md` §3.

### State Flow Changes

**Old (13 states):** UNPACK → DETECT_USER → CARDS → CURRENCY → INCOME → DEBTS → BUDGETS → BILLS → TAX_CHECK → TAX_DESCRIBE → REVIEW → SHEETS → COMPLETE

**New (21 states):** UNPACK → PREFLIGHT → DETECT_CONTEXT → SETUP_MODE_SELECT → INCOME_COLLECT → INCOME_CONFIRM → BUSINESS_RULES_MAP → BUSINESS_RULES_CONFIRM → DEBT_COLLECT → DEBT_CONFIRM → BUDGET_PRESENT → BUDGET_COLLECT → BUDGET_CONFIRM → BILLS_COLLECT → BILLS_CONFIRM → REVIEW_ALL → SHEETS_CREATE → CRONS_SETUP → TELEMETRY_OPT → ONBOARDING_MISSIONS → COMPLETE

### Changes Made

| # | Change | Reason |
|---|--------|--------|
| 1 | Added 10 new states: PREFLIGHT, SETUP_MODE_SELECT, INCOME_CONFIRM, DEBT_CONFIRM, BUDGET_CONFIRM, BUSINESS_RULES_MAP, BUSINESS_RULES_CONFIRM, CRONS_SETUP, TELEMETRY_OPT, ONBOARDING_MISSIONS | Spec §3.2-3.14 requires all of these as real states |
| 2 | Removed CARDS and CURRENCY as separate states | Spec §3.4: cards are account_labels collected during INCOME_COLLECT. Currency auto-set in DETECT_CONTEXT |
| 3 | Removed TAX_CHECK + TAX_DESCRIBE | Replaced by BUSINESS_RULES_MAP which loads pre-compiled rulepacks based on income source_type — no user description needed |
| 4 | Created 4 rulepacks under install/rulepacks/ | Spec §3.6: deterministic tax rules from IRS references, not AI-generated |
| 5 | Income schema: added source_type, account_label, is_regular | Spec §3.4: drives rulepack selection + cashflow calculator |
| 6 | Budget schema: added type (fixed/variable) | Spec §3.8: AI analyst only suggests optimizations on variable categories |
| 7 | SHEETS_CREATE no longer marks setup_complete | Spec §3.11-3.14: COMPLETE only after SHEETS + CRONS + TELEMETRY + ONBOARDING all succeed |
| 8 | Every collect state has a confirm state | Spec §3.5, 3.7, 3.8, 3.9: formatted summary with explicit "yes" required before advancing |
| 9 | GOG check now verifies google-client.json + finance-tracker-token.json | Spec §3.2: correct credential paths, not gog/ directory |
| 10 | PREFLIGHT is a real state that blocks setup if checks fail | Spec §3.2: "no questions until this passes" |

### Files Created

| File | Purpose |
|------|---------|
| `src/install/rulepacks/us-personal.v1.json` | No-op placeholder for salary/personal income |
| `src/install/rulepacks/us-rental-property.v1.json` | 9 deductible categories with IRS Schedule E references |
| `src/install/rulepacks/us-freelance.v1.json` | 10 deductible categories with IRS Schedule C references |
| `src/install/rulepacks/us-small-business.v1.json` | 12 deductible categories with IRS Schedule C references |

### Files Modified

| File | Changes |
|------|---------|
| `src/scripts/lib/state_machine.py` | Full rewrite: 21 states, confirm states, rulepack loading, CRONS_SETUP, TELEMETRY_OPT, ONBOARDING_MISSIONS |
| `src/scripts/lib/config.py` | Added RULEPACKS_DIR path |
| `src/install/schemas/income.v1.json` | Added: source_type, account_label, is_regular, currency. frequency now includes "irregular" |
| `src/install/schemas/budget.v1.json` | Added: type (fixed/variable) as required field |

### Rulepack Design (spec §3.6)

- Source type → rulepack mapping is deterministic: salary→personal, rental→us-rental-property, freelance→us-freelance, business→us-small-business
- Multiple income types load multiple rulepacks (e.g., salary + rental loads both)
- Each rulepack has IRS form reference and per-category line references
- Keywords enable future merchant-level auto-tagging
- User customizations go to rules.user.json (overlay), never modify rulepack originals

### Tests Run

| Command | Result | Notes |
|---------|--------|-------|
| `install-check` | PASS | All schemas + all 4 rulepacks detected. google_oauth correctly shows client_json=true, token_json=false |
| `preflight` | PASS | Returns UNPACK state |
| `setup-next "start"` | PASS (with test token) | PREFLIGHT blocks without token. With token: auto-detects Alfredo/es, shows SETUP_MODE_SELECT |
| Full flow test (21 states) | PASS | start → mode=full → income(2) → confirm → business_rules(rental rulepack loaded, 9 cats) → confirm → debts(skip) → confirm → budget(3 entries) → confirm → bills(skip) → confirm → review → sheets → crons → telemetry(yes) → onboarding → COMPLETE |
| `setup-status` after complete | PASS | Shows `COMPLETE`, `21/21` |
| `setup-reset` | PASS | Clears state cleanly |

### What Session 2 Needs

1. **SHEETS_CREATE** — Real Google Sheet creation via gspread (currently placeholder)
2. **CRONS_SETUP** — Register OpenClaw native crons via gateway API (currently placeholder, shows plan)
3. **ai_parser.py** — subprocess+curl for AI calls
4. **sheets.py** — gspread integration with sheetId-based tab references
5. **Transaction commands** — parse-text, parse-photo, log, log-split
6. **Rules engine** — Two-tier: merchant_rules.json + line-item rules from rulepacks

---

## Phase 2: AI Parser, Sheets Integration, Crons, Onboarding (2026-04-02)

### Phase 1.1 Fixes Applied

| Fix | Detail |
|-----|--------|
| Bills frequency | Added `frequency` field (monthly/quarterly/semi_annual/annual) to bills collector, confirm, schema, and config builder. Shows monthly equivalent for non-monthly bills (e.g., "$600 semi-annual ($100.00/mo)"). Enables sinking fund calculations. |
| Interactive onboarding | Onboarding missions are now tracked in `tracker_config.json["onboarding"]`. Mission 1 completes on add/parse-text/log. Mission 2 on budget-status. Mission 3 on safe-to-spend/cashflow. Shows "Mission N complete!" and prompts the next. After all 3: "You're all set!" |

### Files Created

| File | Purpose |
|------|---------|
| `src/scripts/lib/ai_parser.py` | LLM calls via subprocess+curl to LiteLLM. Functions: parse_income, parse_debt, parse_transaction, parse_receipt_lines. Auto-detects AI config from openclaw.json providers → env → system env. |
| `src/scripts/lib/sheets.py` | Google Sheets via gspread + google-client.json/finance-tracker-token.json. create_spreadsheet() creates 10 tabs with headers and initial data via batch_update. All tab references use numeric sheetId. Saves sheets_config.json. |

### Files Modified

| File | Changes |
|------|---------|
| `src/scripts/lib/state_machine.py` | SHEETS_CREATE now calls sheets.py (stays in state on failure for retry). CRONS_SETUP outputs 4 OpenClaw native cron job specs as JSON. Onboarding missions interactive with check_onboarding() API. Bills collector/confirm show frequency + monthly equivalent. |
| `src/scripts/finance.py` | Added `onboarding-check` command. Imports check_onboarding. |
| `src/install/schemas/bill.v1.json` | Added `frequency` as required field (monthly/quarterly/semi_annual/annual). |

### Architecture Decisions

1. **AI via subprocess+curl** — NOT Python requests (fails in WSL for long calls). Cherry-picked from v1 `config.py:157-198`.
2. **AI config cascade** — openclaw.json providers → env section → system env vars → fallback to localhost:4000.
3. **Sheets by sheetId** — All tabs referenced by numeric `sheetId` (never by name). User can rename tabs without breaking anything.
4. **batch_update** — All initial sheet writes go in one API call (headers, budget data, payment calendar, debt tracker, businesses). Respects Google's 60 req/min limit.
5. **sheets_config.json** — Stores spreadsheet_id, url, and all tab sheetIds with schema versions. Enables migration path.
6. **SHEETS_CREATE retry** — On failure, stays in state with typed error. User types "retry" to attempt again.
7. **Cron job specs as JSON** — CRONS_SETUP outputs full OpenClaw native cron job specs. The SKILL.md instructs the agent to register them via the cron tool.
8. **Onboarding in config** — Mission progress in tracker_config.json, not setup_state.json (persists after setup reset).

### Cherry-Picked from v1

| Pattern | Source | Adaptation |
|---------|--------|------------|
| AI config auto-detection | `v1/config.py:45-155` | Same cascade: providers → env → system vars. Simplified to single parse model. |
| curl payload for AI | `v1/config.py:157-198` | Same subprocess+curl pattern with timeout handling. |
| JSON fence stripping | `v1/config.py:211-222` | Same regex to extract JSON from markdown fences. |
| gspread connection | `v1/sheets.py:100-117` | Adapted from GOG to direct google-client.json + token. |
| Tab headers + structure | `v1/sheets.py:120-277` | Same transaction schema (19 cols + business_id). Added 4 new tabs. |

### 10 Tabs Created

| Tab | Purpose |
|-----|---------|
| Transactions | All income/expense entries (20 columns) |
| Budget | Category budgets with type (fixed/variable) and usage tracking |
| Payment Calendar | Recurring bills with frequency for sinking fund calculations |
| Monthly Summary | Aggregated monthly financial overview |
| Debt Tracker | Debt balances, APR, payoff estimates |
| Rules | Merchant categorization rules (auto-learned + manual) |
| Reconciliation Log | Bank CSV reconciliation results |
| Cashflow Ledger | Signed amounts for daily cashflow tracking |
| Businesses | Multi-business support (rulepack references) |
| Savings Goals | Savings targets with daily required calculations |

### Tests Run

| Test | Result | Notes |
|------|--------|-------|
| `install-check` | PASS (all green) | All schemas, rulepacks, deps, and OAuth creds (with test token) verified |
| Full 21-state flow | PASS | Start → mode → income(2) → confirm → biz rules(rental, 9 cats) → confirm → debts(skip) → budget(2 entries) → confirm → bills(Power monthly + Car Insurance semi-annual) → confirm → review → sheets(auth error expected) → manual advance → crons(4 jobs) → telemetry(yes) → onboarding(mission 1) → COMPLETE |
| Bills frequency display | PASS | "Car Insurance — $600.00 semi-annual due day 1 ($100.00/mo)" |
| Bills confirm total | PASS | "Monthly equivalent: $220.00" (correctly calculates $120 + $600/6) |
| SHEETS_CREATE error handling | PASS | Returns SHEETS_CREATE_FAILED, stays in state for retry |
| CRONS_SETUP job specs | PASS | 4 cron jobs with proper schedule, timezone, payload, delivery |
| Onboarding mission 1 (add) | PASS | "Misión 1 completa! Misión 2: budget status" |
| Onboarding mission 2 (budget-status) | PASS | "Misión 2 completa! Misión 3: safe to spend" |
| Onboarding mission 3 (cashflow) | PASS | "Misión 3 completa! Ya estás listo." |
| Onboarding after all complete | PASS | Returns null (no more missions) |

### What Phase 3 Needs

1. **Transaction commands** — parse-text, parse-photo, log, log-split, income wired to AI parser + sheets
2. **Rules engine** — Two-tier merchant + line-item matching from rulepacks
3. **Budget monitoring** — budget-status, threshold alerts
4. **Cashflow calculator** — safe-to-spend with sinking fund calculations
5. **Payment reminders** — payment-check with upcoming due dates
6. **Reconciliation** — Bank CSV import + reconcile
7. **Reports** — weekly-summary, monthly-report with AI analysis

---

## Phase 3: Runtime Commands (2026-04-02)

### AI Parser Fix

Rewrote `ai_parser.py` with 3-level backend detection cascade:
- **Level 1 (llm-task):** Returns `{llm_request: true, system, user}` for agent to process via llm-task tool. Used when no AI backend is available.
- **Level 2 (LiteLLM):** Checks `localhost:4000/health`, discovers models via `GET /models`, picks cheapest for parsing. No hardcoded model names.
- **Level 3 (Direct API):** Reads OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY from openclaw.json env or system env. Anthropic Messages API supported with format translation.

New function `detect_ai_backend()` returns `{backend, model, url, key}`.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `merchant_rules.py` | 146 | Two-tier merchant rules: single-category auto-match + multi-category line-item flag. normalize_merchant(), lookup_merchant(), save_merchant_rule() with auto-learn. |
| `rules.py` | 85 | Base rules + user overlay for tax deductions. match_tax_deduction() with keyword matching against rulepack keywords. |
| `parser.py` | 157 | Transaction parsing: regex → merchant rules → AI fallback. Income detection, amount/merchant/card extraction. |
| `budget.py` | 108 | Budget status with Fixed/Variable distinction, 3-tier alerts (80%/95%/100%). |
| `cashflow.py` | 170 | Safe-to-spend: balance - upcoming bills - debt min - savings - sinking funds. Risk levels. |
| `payments.py` | 133 | Payment calendar, due-soon alerts (0/1/3 days), promo APR expiry warnings, sinking fund summary. |

### Files Modified

| File | Changes |
|------|---------|
| `ai_parser.py` | Full rewrite: 3-level cascade, Anthropic support, llm-task request mode, dynamic model discovery |
| `finance.py` | Full rewrite: 15+ runtime commands (add, budget-status, safe-to-spend, list-categories, list-rules, add-rule, payment-check, etc.) |

### CLI Commands Added

| Command | What it does |
|---------|-------------|
| `add "text"` | Parse + log transaction (rules → AI fallback, auto-learn merchant) |
| `add-photo "path"` | Parse receipt photo via AI |
| `budget-status` | Per-category budget overview with Fixed/Variable |
| `safe-to-spend` | Daily cashflow number with breakdown |
| `cashflow` | Alias for safe-to-spend |
| `transactions [N]` | List last N transactions (Sheets pending) |
| `list-categories` | Show budget categories |
| `add-category name budget type` | Add new category |
| `remove-category name` | Remove category |
| `list-rules` | Show merchant rules |
| `add-rule pattern category [confidence]` | Add custom merchant rule |
| `update-balance account amount` | Manual balance update |
| `payment-check` | Due-soon alerts + upcoming 7d payments |
| `ai-backend` | Show detected AI backend |

### Add Command Flow

```
input → regex extract (amount, merchant, card)
  → normalize_merchant → lookup merchant_rules.json
  → if known + single-category + confidence > 0.8:
      auto-categorize, implicit confirm: "Added: $15 → Transportation (Uber). Reply 'undo' to revert."
  → if multi-category merchant (walmart, target, etc):
      AI parse line items
  → if unknown merchant:
      AI parse → save merchant rule if single-category result
```

### Merchant Rule Auto-Learning

After `add "$15 Uber"`:
1. Regex extracts $15 + "Uber"
2. No existing rule → regex-only fallback categorizes to "Other"
3. ... but wait, AI backend detected "provider" → AI returns {category: "Transportation", confidence: 0.98}
4. save_merchant_rule("uber", "Transportation", 0.98, created_by="auto")
5. Next `add "$22 Uber"` → rule match (confidence 0.98, rule_matched=True) → $0 AI cost

### Safe-to-Spend Calculation

Tested with: balance=$3200, biweekly pay dates [1,15], 3 bills (Power $120/mo, Car Insurance $600/semi-annual, Netflix $15.99/mo)

Result: **$221.28/day** = ($3200 - $135.99 upcoming - $65 debt min) / 13 days to pay - $6.07 savings - $3.33 sinking fund

Sinking fund: Car Insurance $600/180 days = $3.33/day provisioned.

### Tests Run

| Test | Result | Notes |
|------|--------|-------|
| `add "$15 Uber"` | PASS | Parsed via AI, auto-learned rule, implicit confirm in Spanish, onboarding mission 1 complete |
| `add "$22 Uber"` (2nd) | PASS | Hit cached merchant rule (confidence 0.98, rule_matched=true) — $0 AI |
| `budget-status` | PASS | 9 categories with Fixed/Variable display, onboarding mission 2 |
| `safe-to-spend` | PASS | $221.28/day, sinking fund $3.33/day, onboarding mission 3 |
| `list-categories` | PASS | 9 categories with type and budget |
| `add-category / remove-category` | PASS | Adds/removes from config |
| `list-rules` | PASS | Shows auto-learned "uber" rule |
| `add-rule "starbucks" "Restaurants"` | PASS | Manual rule creation |
| `payment-check` | PASS | 1 alert (Netflix in 3d), 1 upcoming |
| `ai-backend` | PASS | Detected "provider" with LiteLLM proxy model |
| `transactions` | PASS | Returns empty (Sheets pending) |

### What Phase 4 Needs

1. **Sheets read/write** — Wire transactions to Google Sheets (append, read recent, get month spending)
2. **Reconciliation** — Bank CSV import with auto-detection
3. **Weekly/monthly reports** — AI-powered analysis
4. **Undo system** — Revert last transaction within 5 minutes
5. **Debt optimizer** — Avalanche vs snowball payoff strategy
