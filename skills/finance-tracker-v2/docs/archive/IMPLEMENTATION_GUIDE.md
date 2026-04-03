# FINANCE TRACKER v2 — IMPLEMENTATION GUIDE FOR CLAUDE CODE

## Classification: IMPLEMENTATION SPEC — Pass to Claude Code as reference

---

## BUILD ORDER (7 phases, one Claude Code session each)

### Phase 1: Foundation (errors + config + state machine core)
### Phase 2: Setup engine (preflight + detect context + state transitions)
### Phase 3: Collectors (income, debt, budget, bills — parsing + validation)
### Phase 4: Google Sheets (create, write by sheetId, schema validation, batch ops)
### Phase 5: Runtime commands (transactions, receipts, merchant rules, budget status)
### Phase 6: Reports + Cashflow + Cron setup (daily/weekly/monthly, OpenClaw native cron)
### Phase 7: SKILL.md + telemetry + migrations + packaging

---

## ENVIRONMENT CONTEXT

- Platform: OpenClaw skill running on WSL Ubuntu via Telegram
- Skill location: `{workspace}/skills/finance-tracker/`
- Python: 3.x, use `python3` always
- Google Sheets: via `gspread` + `google-auth` (GOG skill provides OAuth)
- LLM access: via the agent's default model (OpenClaw handles routing)
- AI parsing: use `exec` to call the CLI, which internally calls LLM via LiteLLM or OpenClaw llm-task
- Cron: OpenClaw native cron (Gateway scheduler), NOT system crontab
- All file paths use `{baseDir}` which resolves to the skill's root directory
- The agent calls `exec: python3 {baseDir}/scripts/finance.py <subcommand> [args]`
- finance.py returns JSON to stdout, agent shows the `message` field to user

## CRITICAL RULES

1. `finance.py` is the ONLY entry point. All logic goes through CLI subcommands.
2. Every subcommand returns JSON: `{"message": "...", "state": "...", "done": bool, "error": null}`
3. The LLM NEVER decides flow. Python state machine controls all transitions.
4. Google Sheets references use numeric `sheetId`, NEVER tab names.
5. No hardcoded API keys or user data anywhere.
6. `pip install --break-system-packages` for any pip installs.
7. All imports must be try/excepted with clear error messages.
8. Python `requests` library FAILS in WSL for long calls — use `subprocess` + `curl` for LLM API calls.

---

## FILE STRUCTURE

```
finance-tracker/
├── SKILL.md
├── VERSION                            # contains "2.0.0"
├── requirements.txt
├── install/
│   ├── manifest.json
│   ├── schemas/
│   │   ├── income.v1.json
│   │   ├── debt.v1.json
│   │   ├── budget.v1.json
│   │   └── bill.v1.json
│   ├── rulepacks/
│   │   ├── us-personal.v1.json
│   │   ├── us-rental-property.v1.json
│   │   ├── us-freelance.v1.json
│   │   └── us-small-business.v1.json
│   └── migrations/
│       └── 001_initial.py
├── config/                             # generated during setup
│   ├── tracker_config.json
│   ├── sheets_config.json
│   ├── setup_state.json
│   ├── rules.base.json
│   ├── rules.user.json
│   ├── merchant_rules.json
│   └── processed_receipts.json
├── scripts/
│   ├── finance.py                      # CLI entry point
│   └── lib/
│       ├── __init__.py
│       ├── state_machine.py
│       ├── ai_parser.py
│       ├── sheets.py
│       ├── telemetry.py
│       ├── rules.py
│       ├── merchant_rules.py
│       ├── budget.py
│       ├── cashflow.py
│       ├── payments.py
│       ├── reconcile.py
│       ├── reports.py
│       ├── parser.py
│       ├── csv_analyzer.py
│       ├── debt_optimizer.py
│       ├── errors.py
│       ├── migrations.py
│       └── config.py
├── docs/
│   └── SYSTEM_GUIDE.md
└── templates/
    └── sheet_structure.json
```

---

## PHASE 1: FOUNDATION

### File: `scripts/lib/errors.py`

```python
"""Typed error system. Every error has a code, stage, recoverability flag."""

class FinanceError(Exception):
    def __init__(self, code: str, stage: str, message: str, recoverable: bool = True, 
                 suggested_action: str = None, action_url: str = None):
        self.code = code
        self.stage = stage
        self.message = message
        self.recoverable = recoverable
        self.suggested_action = suggested_action
        self.action_url = action_url
        super().__init__(message)

    def to_dict(self):
        return {
            "error_code": self.code,
            "stage": self.stage,
            "message": self.message,
            "recoverable": self.recoverable,
            "suggested_action": self.suggested_action,
            "action_url": self.action_url
        }

# Error code catalog:
# INSTALL_CORRUPT, INSTALL_MISSING_FILE, INSTALL_PERMISSIONS
# AUTH_GOOGLE_MISSING, EXEC_DENIED, DEPS_INSTALL_FAILED, VERSION_MISMATCH
# PARSE_FAILED, SCHEMA_INVALID, SHEETS_CREATE_FAILED, CRON_REGISTER_FAILED
# SHEETS_AUTH_EXPIRED, SHEETS_SCHEMA_DRIFT, RATE_LIMIT, AI_PARSE_TIMEOUT
# CSV_FORMAT_UNKNOWN, DUPLICATE_DETECTED, BALANCE_MISMATCH
```

### File: `scripts/lib/config.py`

Unified config access. All config reads/writes go through this module.

```python
"""
Config paths (relative to {baseDir}):
  config/tracker_config.json    — main config (user settings, timezone, language)
  config/sheets_config.json     — spreadsheet_id + tab sheetIds + schema versions
  config/setup_state.json       — state machine checkpoint
  config/rules.base.json        — from rulepack (read-only after setup)
  config/rules.user.json        — user overrides/additions
  config/merchant_rules.json    — auto-learned merchant → category
  config/processed_receipts.json — dedup tracking

All config operations are atomic: write to .tmp then rename.
"""

KEY FUNCTIONS:
  load_config(name) → dict
  save_config(name, data) → None  # atomic write
  get_base_dir() → str            # resolves {baseDir}
  get_setup_state() → dict
  save_setup_state(state) → None
  is_setup_complete() → bool
```

### File: `scripts/lib/state_machine.py`

This is the core governance layer. 

```python
"""
States enum and transition logic.
Each state has:
  - prompt_template: what to show the user
  - parser: how to parse user input (regex first, AI fallback)
  - validator: schema validation for parsed data
  - on_success: next state
  - on_special: handlers for 'undo', 'list', 'edit N', 'skip'
  - side_effects: None until SHEETS_CREATE (no side effects before REVIEW_ALL)
"""

STATES = [
    "UNPACK",
    "PREFLIGHT",
    "DETECT_CONTEXT",
    "SETUP_MODE_SELECT",      # quick vs full
    "INCOME_COLLECT",
    "INCOME_CONFIRM",
    "BUSINESS_RULES_MAP",
    "BUSINESS_RULES_CONFIRM",
    "DEBT_COLLECT",           # skipped in quick mode
    "DEBT_CONFIRM",           # skipped in quick mode
    "BUDGET_PRESENT",
    "BUDGET_COLLECT",
    "BUDGET_CONFIRM",
    "BILLS_COLLECT_OR_SKIP",  # skipped in quick mode
    "REVIEW_ALL",
    "SHEETS_CREATE",
    "CRONS_SETUP",
    "TELEMETRY_OPT",
    "ONBOARDING_MISSIONS",
    "COMPLETE"
]

DONE_SIGNALS = [
    "done", "that's it", "that's all", "finished", "listo",
    "terminé", "ya", "eso es todo", "no more", "nothing else",
    "nada más", "ya terminé", "end", "stop", "fin"
]

META_COMMANDS = {
    "undo": "remove last item from current collection",
    "list": "show all items collected so far",
    "edit N": "edit item number N",
    "skip": "skip current section (where allowed)",
    "back": "go to previous section",
    "restart": "restart setup from beginning (with confirmation)"
}

# State machine interface:
class SetupStateMachine:
    def process(self, user_input: str) -> dict:
        """
        Main entry point. Takes raw user input, returns:
        {
            "message": str,          # text to show user
            "state": str,            # current state name
            "progress": "3/8",       # step progress indicator
            "done": bool,            # true when COMPLETE
            "error": dict | None     # error object if any
        }
        """
```

### File: `install/schemas/income.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["amount", "frequency", "source_type", "account_label"],
  "properties": {
    "amount": {"type": "number", "minimum": 0},
    "currency": {"type": "string", "default": "USD"},
    "frequency": {"enum": ["weekly", "biweekly", "monthly", "irregular"]},
    "source_type": {"enum": ["salary", "freelance", "rental", "business", "investment", "other"]},
    "account_label": {"type": "string", "minLength": 1},
    "is_regular": {"type": "boolean"}
  }
}
```

### File: `install/schemas/debt.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["debt_type", "balance", "apr"],
  "properties": {
    "debt_type": {"enum": ["credit_card", "personal_loan", "auto_loan", "mortgage", "student_loan", "other"]},
    "balance": {"type": "number", "minimum": 0},
    "apr": {"type": "number", "minimum": 0, "maximum": 100},
    "minimum_payment": {"type": "number", "minimum": 0},
    "label": {"type": "string"},
    "promo_apr": {"type": "number", "minimum": 0},
    "promo_expiry": {"type": "string", "format": "date"}
  }
}
```

### File: `install/schemas/budget.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["category", "amount", "type"],
  "properties": {
    "category": {"type": "string", "minLength": 1},
    "amount": {"type": "number", "minimum": 0},
    "type": {"enum": ["fixed", "variable"]},
    "alert_threshold": {"type": "number", "default": 0.8}
  }
}
```

### File: `install/schemas/bill.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "amount", "frequency"],
  "properties": {
    "name": {"type": "string"},
    "amount": {"type": "number", "minimum": 0},
    "due_day": {"type": "integer", "minimum": 1, "maximum": 31},
    "frequency": {"enum": ["monthly", "quarterly", "semi_annual", "annual"]},
    "autopay": {"type": "boolean", "default": false},
    "account": {"type": "string"},
    "provision_monthly": {"type": "number"}
  }
}
```

---

## PHASE 2: SETUP ENGINE

### File: `scripts/finance.py` (entry point)

```python
#!/usr/bin/env python3
"""
Finance Tracker v2 — CLI entry point.
ALL interactions go through this script.
Returns JSON to stdout for the agent to display.

Usage:
  finance.py install-check          # verify ZIP structure
  finance.py preflight              # check dependencies
  finance.py setup-next "msg"       # advance setup state machine
  finance.py setup-status           # show current setup state
  finance.py setup-restart          # restart setup (with confirm)
  
  # Runtime commands (only after setup complete):
  finance.py add "receipt text"     # add transaction
  finance.py add-photo "path"       # add from receipt photo
  finance.py budget-status          # show budget overview
  finance.py safe-to-spend          # daily cashflow number
  finance.py cashflow               # full cashflow report (cron)
  finance.py payment-check          # upcoming payment alerts (cron)
  finance.py weekly-review          # weekly report (cron)
  finance.py monthly-report         # monthly AI analysis (cron)
  finance.py transactions [N]       # list last N transactions
  finance.py edit-transaction ID    # edit a transaction
  finance.py delete-transaction ID  # delete a transaction
  finance.py add-category "name" budget type  # add budget category
  finance.py remove-category "name" # remove budget category
  finance.py list-categories        # list all categories with budgets
  finance.py list-rules             # show active rules
  finance.py add-rule               # add custom rule
  finance.py add-business "type"    # add new business for tax rules
  finance.py tax-summary [year]     # tax deduction summary
  finance.py tax-export [year]      # CSV for accountant
  finance.py reconcile "csv_path"   # bank CSV reconciliation
  finance.py update-balance acct amt # manual balance update
  finance.py savings-goals          # show savings goals
  finance.py add-savings-goal       # add a savings goal
  finance.py debt-strategy          # show debt payoff plan
  finance.py projection [months]    # financial projection
  finance.py repair-sheet           # fix sheet schema drift
  finance.py reconnect-sheets       # refresh Google auth
  finance.py telemetry [on|off]     # toggle telemetry
  finance.py version                # show version
  finance.py help                   # command list
"""

import sys, json, os

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(base_dir, "scripts"))
    
    if len(sys.argv) < 2:
        return output({"message": "Usage: finance.py <command> [args]", "error": None})
    
    command = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Route to handler
    try:
        if command == "install-check":
            from lib.state_machine import install_check
            result = install_check(base_dir)
        elif command == "preflight":
            from lib.state_machine import preflight
            result = preflight(base_dir)
        elif command == "setup-next":
            user_input = args[0] if args else ""
            from lib.state_machine import SetupStateMachine
            sm = SetupStateMachine(base_dir)
            result = sm.process(user_input)
        elif command == "setup-status":
            from lib.state_machine import setup_status
            result = setup_status(base_dir)
        # ... runtime commands ...
        else:
            result = {"message": f"Unknown command: {command}", "error": {"error_code": "UNKNOWN_COMMAND"}}
    except Exception as e:
        from lib.errors import FinanceError
        if isinstance(e, FinanceError):
            result = {"message": e.message, "error": e.to_dict(), "done": False}
        else:
            result = {"message": f"Unexpected error: {str(e)}", "error": {"error_code": "UNEXPECTED", "message": str(e)}, "done": False}
    
    output(result)

def output(data):
    print(json.dumps(data, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

### `ai_parser.py` — LLM calls ONLY for text → JSON parsing

```python
"""
Uses the agent's default model via LiteLLM or OpenClaw exec.
ONLY purpose: convert free-text user input to structured JSON.
NEVER used for flow decisions or conversation management.

Key rule: Python requests FAILS in WSL for long API calls.
Always use subprocess + curl for LLM calls.
"""

KEY FUNCTIONS:
  parse_income(text: str, language: str) -> dict | None
  parse_debt(text: str, language: str) -> dict | None
  parse_transaction(text: str, language: str) -> dict | None
  parse_receipt_photo(photo_path: str) -> dict | None
  classify_merchants_batch(merchants: list[str]) -> list[dict]

# Each function:
# 1. Constructs a system prompt with exact JSON schema expected
# 2. Calls LLM via subprocess curl to LiteLLM proxy (http://127.0.0.1:4000)
# 3. Parses JSON response
# 4. Validates against schema
# 5. Returns structured dict or None on failure

# The LiteLLM endpoint and model are read from environment or config.
# Default: use whatever model the user's agent has configured.
# The skill does NOT hardcode a model name.
```

---

## PHASE 3: COLLECTORS

Each collector state follows the same pattern:

```python
def handle_collect_state(self, user_input, state_name, schema_file, collection_key):
    # 1. Check for meta-commands first (Python, not LLM)
    if self._is_done_signal(user_input):
        return self._transition_to_confirm(state_name)
    if user_input.strip().lower() == "undo":
        return self._undo_last(collection_key)
    if user_input.strip().lower() == "list":
        return self._list_collected(collection_key)
    if user_input.strip().lower().startswith("edit "):
        return self._edit_item(collection_key, user_input)
    
    # 2. Try deterministic parsing first (regex)
    parsed = self._try_regex_parse(user_input, state_name)
    
    # 3. Fall back to AI parsing if regex fails
    if parsed is None:
        parsed = self._ai_parse(user_input, state_name)
    
    # 4. Validate against schema
    if parsed is None:
        return {"message": "I couldn't understand that. Please try again with format: ...", "state": state_name}
    
    errors = self._validate_schema(parsed, schema_file)
    if errors:
        return {"message": f"Missing info: {errors}. Please provide: ...", "state": state_name}
    
    # 5. Add to collection, return acknowledgment
    self._add_to_collection(collection_key, parsed)
    return {
        "message": f"Got it: {self._format_item(parsed)}\n\nAdd another or say 'done'.",
        "state": state_name,
        "progress": self._get_progress()
    }
```

### Budget collector special handling:

The budget collector shows a numbered list. Parsing is primarily regex:

```python
BUDGET_REGEX = r'(\d+)\.\s*\$?(\d[\d,]*(?:\.\d{2})?)'
CUSTOM_REGEX = r'new\s+(.+?)\s+\$?(\d[\d,]*(?:\.\d{2})?)\s*(fixed|variable)?'
```

---

## PHASE 4: GOOGLE SHEETS

### File: `scripts/lib/sheets.py`

```python
"""
ALL sheet operations use numeric sheetId from sheets_config.json.
NEVER reference tabs by name.

sheets_config.json structure:
{
  "spreadsheet_id": "...",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/...",
  "tabs": {
    "transactions": {"sheet_id": 0, "schema_version": "v1.0"},
    "budget": {"sheet_id": 123456, "schema_version": "v1.0"},
    ...
  },
  "created_at": "...",
  "last_validated": "..."
}

Key design decisions:
- All initial writes use batch_update (one API call for entire setup)
- Before any write, validate schema (columns match expected)
- If schema drift detected: try auto-repair, or return SHEETS_SCHEMA_DRIFT error
- Monthly archival: move old transactions to Archive_YYYY_MM tab
"""

TABS_TO_CREATE = [
    "Transactions", "Budget", "Payment Calendar", "Monthly Summary",
    "Debt Tracker", "Rules", "Reconciliation Log", "Cashflow Ledger",
    "Businesses", "Savings Goals"
]

# 10 tabs, each with defined columns:
TAB_SCHEMAS = {
    "transactions": {
        "columns": ["date", "merchant", "amount", "category", "account",
                     "business_id", "tax_deductible", "tax_category",
                     "confidence", "source", "notes", "receipt_id"]
    },
    "budget": {
        "columns": ["category", "monthly_budget", "type", "spent_this_month",
                     "remaining", "alert_threshold", "last_updated"]
    },
    # ... etc for each tab
}
```

### File: `templates/sheet_structure.json`

Complete template for creating the Google Sheet with all tabs, headers, formatting, and initial data. Used by `sheets.py` during SHEETS_CREATE state.

---

## PHASE 5: RUNTIME COMMANDS

### Merchant rules two-tier system (`scripts/lib/merchant_rules.py`):

```python
"""
Tier 1: Merchant-level rules (single-category merchants)
  merchant_rules.json: {"uber": {"category": "transportation", "requires_line_items": false, ...}}

Tier 2: Line-item rules (multi-category merchants like Walmart, Target)
  These always go through AI parsing per line item.

Flow:
  input → normalize_merchant(name) → lookup merchant_rules.json
    → if found AND requires_line_items == false AND confidence > 0.8:
        auto-categorize, $0 cost, implicit confirm
    → if found AND requires_line_items == true:
        parse line items via AI, check business rules for tax
    → if not found:
        AI parse, then:
          if single category: save new merchant rule
          if multi category: mark as requires_line_items

Normalization:
  "UBER *TRIP" → "uber"
  "WAL-MART #1234" → "walmart"
  Lowercase, strip numbers/special chars, match against alias list
"""

MULTI_CATEGORY_MERCHANTS = [
    "walmart", "target", "costco", "home depot", "lowes", "publix",
    "kroger", "amazon", "sam's club", "dollar general", "dollar tree",
    "walgreens", "cvs"
]
```

### Transaction add flow:

```python
# finance.py add "$15 Uber"
# 1. Parse amount + merchant from input
# 2. Normalize merchant name
# 3. Check merchant_rules.json
# 4. If known single-category, high confidence:
#    → auto-categorize, write to sheet
#    → return: "Added: $15.00 → Transportation (Uber). Reply 'undo' within 5 min."
# 5. If unknown or multi-category:
#    → AI parse for category
#    → if business rules match, ask tax deduction question
#    → write to sheet after confirm
#    → save merchant rule if single-category result
```

---

## PHASE 6: REPORTS + CASHFLOW + CRONS

### Safe-to-spend formula:

```python
def calculate_safe_to_spend(self):
    balance = self._get_current_balance()
    upcoming_bills = self._get_bills_before_next_income()
    debt_payments = self._get_debt_payments_before_next_income()
    savings_daily = self._get_daily_savings_allocation()
    sinking_provisions = self._get_sinking_fund_daily()
    days_to_income = self._get_days_to_next_income()
    
    committed = upcoming_bills + debt_payments
    daily_set_aside = savings_daily + sinking_provisions
    
    available = balance - committed - (daily_set_aside * days_to_income)
    safe_per_day = available / max(days_to_income, 1)
    
    return {
        "safe_to_spend_today": round(safe_per_day, 2),
        "balance": balance,
        "committed_before_income": committed,
        "days_to_next_income": days_to_income,
        "total_available": round(available, 2)
    }
```

### OpenClaw native cron registration:

```python
"""
Register cron jobs via OpenClaw cron tool.
The agent must execute these via the cron tool, not system crontab.

finance.py outputs the cron specs as JSON.
The SKILL.md instructs the agent to register them using the cron tool.

4 jobs to register:
1. Daily cashflow    — "30 7 * * 1-5" (7:30 AM weekdays)
2. Payment check     — "0 9 * * *" (9:00 AM daily)
3. Weekly review     — "0 8 * * 0" (8:00 AM Sundays)
4. Monthly report    — "0 8 1 * *" (8:00 AM 1st of month)

Each job runs as isolated session with announce delivery.
Timezone from user's detected context.
"""

def get_cron_specs(base_dir, timezone):
    return [
        {
            "name": "Finance: Daily Cashflow",
            "schedule": {"kind": "cron", "cron": "30 7 * * 1-5", "tz": timezone},
            "sessionTarget": "isolated",
            "payload": {
                "kind": "agentTurn",
                "message": f"Run this command and show the output to me:\npython3 {base_dir}/scripts/finance.py cashflow"
            },
            "delivery": {"mode": "announce", "channel": "last"}
        },
        # ... 3 more jobs
    ]
```

---

## PHASE 7: SKILL.MD + TELEMETRY + PACKAGING

### SKILL.md structure (thin router):

```markdown
---
name: finance_tracker
description: Personal finance tracker with receipt parsing, budget monitoring, tax deductions, and automated reports. Setup and manage via chat.
metadata: {"openclaw": {"requires": {"bins": ["python3"]}, "os": ["linux"]}}
---

# Finance Tracker v2

## SETUP (if not complete)

Check if setup is complete:
  exec: python3 {baseDir}/scripts/finance.py setup-status

If setup not complete, for ANY user message:
  exec: python3 {baseDir}/scripts/finance.py setup-next "<user_message>"

Show the "message" field from the JSON response to the user.
Do NOT add your own commentary or questions.
Do NOT skip steps or reorder the setup flow.
The script controls the conversation — just relay messages.

## RUNTIME (after setup complete)

[Command routing table — map user intents to CLI subcommands]

When user sends a receipt photo:
  exec: python3 {baseDir}/scripts/finance.py add-photo "<photo_path>"

When user sends text with a dollar amount:
  exec: python3 {baseDir}/scripts/finance.py add "<user_text>"

When user asks about budget:
  exec: python3 {baseDir}/scripts/finance.py budget-status

[... etc for all commands]

## CRON REGISTRATION

During setup, when the script outputs cron_specs, register each job using
the cron tool with the exact parameters provided. Do not modify schedules.

## RULES

- NEVER decide what to ask the user. The script decides.
- NEVER skip the preflight or any setup step.
- NEVER modify the JSON output before showing to user.
- If the script returns an error, show it and follow suggested_action.
- For receipt photos, save the photo to a temp path and pass the path.
```

### Telemetry schema:

```python
"""
Remote telemetry: Supabase table 'telemetry_v2'
ONLY sent if user opted in.
ZERO PII. ZERO traceability. No user_id, no install_id, no session_id.

Event types:
  install_start, setup_stage_complete, setup_stage_error,
  setup_complete, command_used, error_occurred, cron_executed

Every event:
{
  "event": str,
  "v": "2.0.0",
  "stage": str | null,
  "result": "ok" | "error",
  "duration_bucket": "0-5s" | "5-15s" | "15-30s" | "30-60s" | "60s+",
  "error_code": str | null,
  "setup_mode": "quick" | "full" | null,
  "detected_language": "en" | "es" | null,
  "distribution": "github_zip" | "gumroad" | "clawhub",
  # Structural counts only:
  "income_source_count": int | null,
  "debt_count": int | null,
  "business_type_count": int | null,
  "custom_category_count": int | null,
  "rulepack_ids": ["us-rental-property.v1"] | null,
  "cron_job_count": int | null
}
"""

SUPABASE_URL = "https://oetfiiatbzfydbtzozlz.supabase.co"
SUPABASE_ANON_KEY = "..."  # public anon key only, no auth
TABLE = "telemetry_v2"
```

---

## RULE PACKS (examples)

### `install/rulepacks/us-rental-property.v1.json`

```json
{
  "rulepack_id": "us-rental-property.v1",
  "jurisdiction": "US",
  "business_type": "rental_property",
  "version": "1.0",
  "irs_form": "Schedule E",
  "deductible_categories": [
    {
      "category": "cleaning_supplies",
      "irs_line": "Line 7 - Cleaning and maintenance",
      "description": "Cleaning products, trash bags, detergent, mops, brooms",
      "keywords": ["cleaning", "bleach", "mop", "broom", "trash bag", "windex", "lysol", "swiffer", "paper towel", "clorox"],
      "common_merchants": ["walmart", "target", "dollar general", "home depot"]
    },
    {
      "category": "linens_supplies",
      "irs_line": "Line 7 - Cleaning and maintenance",
      "description": "Sheets, towels, pillows, mattress protectors",
      "keywords": ["sheets", "towel", "pillow", "mattress", "blanket", "comforter", "duvet"]
    },
    {
      "category": "maintenance_repair",
      "irs_line": "Line 14 - Repairs",
      "description": "Plumbing, electrical, HVAC, appliance repair, paint, tools",
      "keywords": ["repair", "plumber", "electrician", "hvac", "paint", "tool", "hardware", "fix"]
    },
    {
      "category": "insurance",
      "irs_line": "Line 9 - Insurance",
      "description": "Property insurance, liability insurance, umbrella policy"
    },
    {
      "category": "utilities",
      "irs_line": "Line 17 - Other expenses",
      "description": "Electricity, water, gas, internet — prorated by rental use percentage",
      "requires_proration": true
    },
    {
      "category": "professional_services",
      "irs_line": "Line 17 - Other expenses",
      "description": "Property management fees, legal fees, accounting fees, Airbnb service fees"
    },
    {
      "category": "advertising",
      "irs_line": "Line 6 - Advertising",
      "description": "Listing fees, photography, marketing costs"
    },
    {
      "category": "mortgage_interest",
      "irs_line": "Line 12 - Mortgage interest",
      "description": "Interest portion of mortgage payment (not principal)"
    },
    {
      "category": "property_taxes",
      "irs_line": "Line 16 - Taxes",
      "description": "Property tax, HOA if deductible portion"
    }
  ]
}
```

---

## V1 CODE TO CHERRY-PICK

These v1 modules have reusable logic (copy and adapt, don't import):

| v1 module | What to reuse | What changes |
|---|---|---|
| sheets.py | gspread connection, OAuth flow | Add sheetId-based access, schema validation, batch_update |
| rules.py | Pattern matching logic | Split into rules.py (base) + merchant_rules.py (learning) |
| parser.py | Receipt text parsing | Add line-item parsing, multi-category support |
| budget.py | Budget calculation | Add fixed/variable distinction |
| cashflow.py | Daily cashflow | Add sinking funds, savings allocations |
| payments.py | Payment calendar | Add frequency beyond monthly |
| reconcile.py | CSV matching | Add bank format auto-detection |
| telemetry.py | Supabase connection | New schema, new table, stricter PII filter |
| config.py | JSON read/write | New config structure, atomic writes |

DO NOT reuse:
- setup_wizard.py (replaced by state_machine.py)
- setup_crons.sh (replaced by OpenClaw native cron)
- cron_runner.sh (replaced by OpenClaw native cron)
- Any v1 SKILL.md content

---

## IMPORTANT CONTEXT FROM V1 LESSONS LEARNED

- TL-01: Python requests FAILS in WSL for long API calls → use subprocess + curl
- TL-29: Google Sheets OAuth: use run_local_server(port=18900, open_browser=False) in WSL
- TL-30: Google Sheets needs BOTH spreadsheets AND drive scopes
- TL-38: Receipt amounts: re.findall + max() beats re.search
- TL-39: Credit card payments are POSITIVE in Chase CSV
- TL-40: Spanish payment keywords needed (SU PAGO, PAGO AUTOMATICO)
- TL-41: AI batch classification ~$0.01/50 merchants

---

## HOW TO USE THIS GUIDE

For each phase, tell Claude Code:

"Read the Finance Tracker v2 Implementation Guide at {path}. 
We are building Phase N: {phase_name}.
The v1 source code is at ~/.openclaw/workspace/skills/finance-tracker/.
Cherry-pick relevant logic from v1, but build to the v2 spec.
Create the files listed under Phase N."

After each phase, test before moving to the next.
