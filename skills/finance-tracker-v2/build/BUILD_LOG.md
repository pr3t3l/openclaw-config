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
