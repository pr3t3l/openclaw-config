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
