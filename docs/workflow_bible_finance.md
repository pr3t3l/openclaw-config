# WORKFLOW BIBLE — FINANCE TRACKER (ROBOTIN FINANCE)
## Documento técnico autoritativo
### Last verified: 2026-03-29 (audit v2.1)
### Sources: Build Instructions + v1.1 Addendum + Split/Tax Upgrade + Plan Financiero + Bible v2 §11

> **Source tags:** `[AUDIT]` = machine-verified 2026-03-29. `[BUILD]` = from build instructions.
> `[UPG]` = from upgrade docs. `[FIN]` = from plan financiero. `[BIBLE]` = from Project Bible v2.

---

# 1. PURPOSE & CONTEXT

The Finance Tracker is a personal expense tracking system built as an OpenClaw skill inside the CEO workspace (Robotin). It is NOT a separate bot — it runs through @Robotin1620_Bot via Telegram, with Google Sheets as data storage.

**Key differentiator:** Airbnb rental property tax deduction tracking — automatically categorizes expenses as personal vs. business deductible.

**Bot:** @Robotin1620_Bot (shared with CEO agent)
**Skill location:** `~/.openclaw/workspace/skills/finance-tracker/` `[AUDIT]`

### What are the other workflows?

| Workflow | Relationship to Finance |
|----------|------------------------|
| **Platform (Robotin)** | Finance is a SKILL inside the CEO agent — auto-discovered by OpenClaw |
| **Marketing System** | Marketing costs tracked via LiteLLM SpendLogs (separate from Finance Tracker) |
| **Declassified Pipeline** | Pipeline costs ($6-8/case) could be tracked here but currently only in LiteLLM |
| **Meta-Workflow Planner** | Not directly connected |

---

# 2. TIMELINE

| Date | Event | Result | Source |
|------|-------|--------|--------|
| 2026-03-27 | Finance Tracker designed (V1: 5 modules) | Build instructions created | [BUILD] |
| 2026-03-27 | V1.1 addendum: 3 new modules (Reconciliation, Rule Engine, Daily Cashflow) | 8 modules total | [BUILD] |
| 2026-03-27 | Claude Code built the entire tracker | Commit faf052f (part of larger commit with Marketing) | [BIBLE] |
| 2026-03-27 | Google Sheets OAuth configured | Port 18900, WSL → Windows browser redirect | [BIBLE] |
| 2026-03-27 | Split/Tax upgrade designed | Multi-category receipt splitting + Airbnb tax deductions | [UPG] |
| 2026-03-28 | 4 cron jobs configured | cashflow, payment-check, weekly-summary, monthly-report | [AUDIT] |
| 2026-03-28 | add_category.sh script created | Safely updates budgets.json, parser.py, and Google Sheets | [BUILD] |
| 2026-03-30 | Plan financiero personal created | Debt analysis, budget, 3-phase plan | [FIN] |
| 2026-03-31 | Reconciliation v2: false positive elimination, multi-month CSV, positive amount classification | 4 fixes applied to reconcile.py | [CHANGES] |
| 2026-03-31 | New categories: Pets, Debt_Interest, Bank_Fees, Refunds | config.py updated (14→18 categories) | [CHANGES] |
| 2026-03-31 | Batch writes to Sheets (avoid 429 quota errors) | sheets.py updated | [CHANGES] |
| 2026-03-31 | Cashflow_Ledger tab with signed amounts | New Google Sheets tab | [CHANGES] |
| 2026-03-31 | Wells Fargo checking CSV support | reconcile.py updated | [CHANGES] |
| 2026-03-31 | Batch Receipt Processor spec created | BATCH_RECEIPT_INSTRUCTIONS.md — not yet implemented | [BATCH] |
| 2026-03-31 | AI batch classification implemented | reconcile.py calls AI for unknown merchants, auto-creates rules | [CHANGES] |
| 2026-03-31 | Batch receipt processor built | batch_receipts.py — process multiple receipt links at once | [CHANGES] |
| 2026-03-31 | Receipt splitting + tax deduction deployed | Multi-category receipts with Airbnb flag per line item | [CHANGES] |
| 2026-03-31 | Income tracking added | "me pagaron 2800" auto-updates balance, tracks payday schedule | [CHANGES] |
| 2026-03-31 | 4 reconciliation fixes applied | false positive matching eliminated, payment classification fixed, multi-month support, CATEGORIES synced | [CHANGES] |
| 2026-03-31 | Cashflow_Ledger tab added | Signed amounts, flow_type classification (expense/refund/income/payment/transfer) | [CHANGES] |
| 2026-03-31 | Wells Fargo checking CSV support | _parse_csv_row_wells() for WF format | [CHANGES] |
| 2026-03-31 | 17 Walmart receipts batch-processed | First real batch import with line-item splitting | [CHANGES] |

---

# 3. ARCHITECTURE — 9 MODULES

| Phase | Module | Priority | What it does | Uses AI? |
|-------|--------|----------|-------------|----------|
| 1 | **Rule Engine** | FIRST | Auto-categorize known merchants without AI | No ($0) |
| 1 | **Expense Parser** | FIRST | Parse receipts (photo/text) into structured JSON | Yes (LLM) |
| 1 | **Transaction Logger** | FIRST | Write parsed transactions to Google Sheets | No |
| 2 | **Budget Monitor** | SECOND | Alert when spending approaches budget limits | No |
| 2 | **Payment Reminder** | SECOND | Alert before payment due dates | No |
| 2 | **Daily Cashflow** | SECOND | Daily "safe to spend" calculation | No |
| 3 | **Monthly Analyst** | THIRD | Month-end AI summary report | Yes (LLM) |
| 3 | **Reconciliation** | THIRD | Match receipts against bank CSV uploads | No |

**Flow:**

```
User sends receipt/text via Telegram
    ↓
Rule Engine: known merchant? → auto-categorize (skip AI)
    ↓ (if unknown)
Expense Parser: AI extracts amount, merchant, category, items
    ↓
User confirms (or adjusts)
    ↓
Transaction Logger: writes to Google Sheets
    ↓
Budget Monitor: checks if near limit → alerts if needed
```

| 9 | **Batch Receipt Processor** | Process multiple receipt links, match against CSV rows, replace generic rows with detailed line items | batch_receipts.py |

**Flow:**

```
Multiple receipt links → dedup check → fetch each (2s delay) → parse items via __NEXT_DATA__
    ↓
Match against existing CSV transaction (amount exact, merchant fuzzy, date ±2d)
    ↓
Match found: delete generic row, insert detailed item rows (split by category)
No match: insert as new receipt
    ↓
Batch-ask Airbnb confirmation for cleaning/linens/supplies items
```

**CLI:** `finance.py batch-receipts <file_with_links> [--account Chase]`
**Dedup:** `processed_receipts.json` in config/
**Status:** OPERATIONAL — 17 Walmart receipts processed 2026-03-31

---

# 4. GOOGLE SHEETS STRUCTURE `[BUILD]`

Sheet name: **"Robotin Finance 2026"**

| Tab | Purpose | Key columns |
|-----|---------|-------------|
| **Transactions** | All expenses logged | date, amount, merchant, category, subcategory, card, input_method, confidence, matched, tax_deductible, tax_category |
| **Budget** | Monthly budgets per category + savings goals | category, monthly_budget, alert_threshold + available_balance, next_payday |
| **Payment Calendar** | Bills and loan due dates | acreedor, due_day, amount, account, autopay, APR, promo_expiry |
| **Monthly Summary** | AI-generated monthly reports | month, total_spent, by_category, vs_budget, insights |
| **Debt Tracker** | Debt balances and payoff tracking | creditor, balance, APR, minimum, promo_rate, promo_expiry |
| **Rules** | Rule Engine auto-categorization rules | merchant_pattern, category, subcategory, priority |
| **Reconciliation_Log** | Bank CSV matching results | date, csv_amount, matched_receipt, status |
| **Cashflow_Ledger** | Signed transaction amounts for daily cashflow | date, account, merchant, amount_signed, flow_type, category, subcategory, notes, source, timestamp, month |

### Tab 8: Cashflow_Ledger
| Column | Purpose |
|--------|---------|
| date | Transaction date |
| account | Bank/card name |
| merchant | Merchant description |
| amount_signed | Positive = money in, negative = money out |
| flow_type | expense / refund / income / payment / transfer |
| category | Spending category |
| subcategory | Optional detail |
| notes | Context |
| source | csv / receipt / manual |
| timestamp | When logged |
| month | YYYY-MM |

---

# 5. CATEGORY TAXONOMY — 18 FIXED CATEGORIES `[BUILD]` `[CHANGES]`

| Category | Monthly budget | Alert % | Notes |
|----------|---------------|---------|-------|
| Groceries | $250 | 80% | Food from stores |
| Restaurants | $100 | 80% | Eating out, delivery |
| Gas | $120 | 80% | Fuel |
| Shopping | $150 | 80% | Amazon, Best Buy, etc. |
| Entertainment | $50 | 80% | Movies, games, streaming |
| Subscriptions_AI | $500 | 90% | OpenAI, Claude, Gemini |
| Subscriptions_Other | $80 | 90% | Netflix, Spotify, etc. |
| Childcare | $400 | N/A | Fixed |
| Home | $100 | 80% | Supplies, repairs |
| Personal | $50 | 80% | Clothing, grooming |
| Travel | Variable | Per trip | Set per trip |
| Work_Tools | $200 | 80% | Software, hardware |
| Health | $50 | 80% | Pharmacy, doctor |
| Other | $50 | 80% | Uncategorized |
| Pets | Variable | 80% | Pet food, vet, supplies |
| Debt_Interest | N/A | N/A | Interest charges on credit cards/loans |
| Bank_Fees | N/A | N/A | Late fees, service charges |
| Refunds | N/A | N/A | Returns, credits (positive amounts) |

---

# 6. SCRIPTS & FILES `[AUDIT]`

### Main script

`finance.py` — entry point with CLI commands (parse-text, parse-photo, add, report, etc.)

### Library modules (11) `[AUDIT]`

| Module | Purpose |
|--------|---------|
| `parser.py` | AI receipt parsing (photo + text) |
| `rules.py` | Rule Engine — merchant pattern matching |
| `budget.py` | Budget monitoring + alerts |
| `cashflow.py` | Daily "safe to spend" calculation |
| `payments.py` | Payment calendar + reminders |
| `analyst.py` | Monthly AI analysis report |
| `reconcile.py` | Bank CSV reconciliation |
| `sheets.py` | Google Sheets read/write (gspread) |
| `logger.py` | Logging |
| `config.py` | Configuration loading |
| `batch_receipts.py` | Batch receipt link processing with dedup and CSV row replacement |

### Config files `[AUDIT]`

| File | Purpose |
|------|---------|
| `budgets.json` | Monthly budgets per category |
| `rules.json` | Auto-categorization rules (merchant → category) |
| `payments.json` | Bill due dates, amounts, APR |
| `savings.json` | Savings goals with targets and deadlines |
| `processed_receipts.json` | Dedup tracker for batch receipt links |
| `pending_categories.json` | AI-suggested categories awaiting user approval |

### Utility scripts

- `add_category.sh` — safely adds a new category (updates budgets.json, parser.py, Google Sheets)
- `cron_runner.sh` — wrapper for cron job execution

---

# 7. CRON JOBS — 4 ACTIVE `[AUDIT]`

| Schedule | Job | What it does |
|----------|-----|-------------|
| 7:30 AM EST Mon-Fri | `cron_runner.sh cashflow cashflow` | Calculates "safe to spend today" based on remaining budget, upcoming bills, and days until payday |
| 9:00 AM EST daily | `cron_runner.sh payment-check payment-check` | Checks if any bill is due in the next 3 days and sends Telegram alert |
| 8:00 AM EST Sundays | `cron_runner.sh weekly-summary weekly-summary` | Weekly spending breakdown: total, by category, vs budget, trend |
| 8:00 AM EST 1st of month | `cron_runner.sh monthly-report monthly-report` | Full month analysis: AI-generated insights, budget adherence, recommendations |

---

# 8. GOOGLE SHEETS OAUTH `[AUDIT]`

| Item | Status | Path |
|------|--------|------|
| OAuth token | ✅ EXISTS | `~/.openclaw/credentials/finance-tracker-token.json` |
| Client config | ✅ EXISTS | `~/.openclaw/credentials/google-client.json` |
| Required scopes | spreadsheets + drive (TL-30) | Both needed for create/read/write |

**WSL OAuth flow:** `run_local_server(port=18900, open_browser=False)` — WSL forwards to Windows browser for consent. `[BUILD]` (TL-29)

**Dependencies:** `gspread`, `google-auth`, `google-auth-oauthlib` — installed in litellm-venv `[BUILD]`

---

# 9. RECEIPT SPLITTING + TAX DEDUCTIONS `[UPG]`

### Multi-category receipt splitting

When a receipt contains items from different categories (e.g., Walmart with groceries + cleaning supplies), the parser outputs MULTIPLE transactions sharing the same `receipt_id`.

**Trigger:** 3+ dollar amounts detected in a receipt → auto-activate split mode (TL-26)

### Airbnb tax deduction tracking `[UPG]`

Each transaction gets two additional fields:
- `tax_deductible`: true/false/null (null = needs user confirmation)
- `tax_category`: none / airbnb_supply / airbnb_repair / airbnb_utility / airbnb_insurance / personal

**Auto-categorize rules for Airbnb:**
- Home Depot / Lowes with cleaning/repair items → ask: "Airbnb or personal?"
- Electricity / water / internet → ask split percentage (Airbnb vs personal)
- Insurance → ask: "Is this the Goose Creek property insurance?"

**Telegram commands for tax:**
- "Tax summary" → total deductible by category
- "Tax export" → CSV for accountant (Schedule E format)

---

# 10. AI BATCH CLASSIFICATION

When the Rule Engine has no rule for a merchant and the reconciler would default to "Other", the system instead:

1. Collects all unknown expense merchants from the CSV batch
2. Deduplicates by normalized name
3. Sends ONE prompt to LiteLLM with all merchants at once
4. AI classifies each into an existing category
5. Auto-creates rules in rules.json (confidence 0.80, created_by: ai_auto)
6. Next CSV import with the same merchant uses the saved rule (zero AI calls)

Model: chatgpt-gpt54 via LiteLLM (Codex OAuth, $0/token)
Cost: ~$0.01 per batch of 50 merchants

Function: `_ai_classify_merchants()` in reconcile.py
Integration point: `_ensure_rules_for_merchants()` runs before auto-logging in `reconcile_csv()`

---

# 11. INCOME TRACKING

Patterns detected automatically: "me pagaron", "paycheck", "ingreso:", "income:", "cobré", "deposito:", "nómina", "sueldo"

When income is detected:
1. Transaction logged with type = "income" to Google Sheets
2. available_balance auto-updated (old_balance + income)
3. Monthly income total tracked

Commands:
| Command | What it does |
|---------|-------------|
| "me pagaron 2800" | Register income + auto-update balance |
| "income 2800 paycheck" | Quick income with source label |
| "payday: biweekly 2800 5,19" | Set pay schedule + expected amount |

Payday config stored in budgets.json: pay_schedule, pay_dates, expected_paycheck

---

# 12. BATCH RECEIPT PROCESSING

Processes multiple receipt links (Walmart w-mt.co, Target, etc.) at once.

Command: `finance.py batch-receipts <file_with_links> [--account Chase]`

Flow:
1. Fetch each link, extract items via `__NEXT_DATA__` JSON (Walmart) or AI
2. For each receipt: find matching CSV transaction (exact amount + date ±2d + merchant)
3. Delete the generic CSV row (e.g., "Walmart $87.43 Groceries")
4. Insert detailed line-item rows (split by category)
5. Collect Airbnb-flaggable items across all receipts
6. Batch-ask user: "¿Personal o Airbnb?" for all at once
7. Dedup: processed_receipts.json tracks which links have been done

Dedup file: `config/processed_receipts.json`

---

# 13. MODEL ROUTING

| Component | Model | Cost |
|-----------|-------|------|
| Receipt parsing (text) | LLM via LiteLLM (cost-efficient model) | ~$0.001-0.003/parse |
| Receipt parsing (photo) | LLM via LiteLLM (vision model) | ~$0.005-0.01/parse |
| Monthly analyst report | LLM via LiteLLM | ~$0.01/report |
| Rule Engine | No AI — pattern matching | $0 |
| All other modules | No AI — deterministic | $0 |

---

# 14. PERSONAL FINANCIAL CONTEXT `[FIN]`

### Snapshot (March 2026)

| Metric | Value |
|--------|-------|
| Total debt (non-mortgage) | $49,352 |
| Mortgage | $275,000 |
| Monthly fixed obligations | ~$4,324 |
| AI subscriptions + API | ~$400-500/mo |
| Total monthly outflow | ~$5,781 |
| Estimated income | ~$5,800-6,200/mo |

### APR time bombs `[FIN]`

| Card | Balance | Current APR | Expires | Post-promo APR |
|------|---------|-------------|---------|----------------|
| Wells Fargo | $6,007 | 1% | **May 2026** | 26% |
| Discover | $6,108 | 3.99% | Feb 2027 | 24.49% |
| Citibank | $4,892 | 0% | Aug 2027 | Variable |

### Top 5 spending leaks `[FIN]`

1. Shopping: $605/mo (impulse buys)
2. AI subs duplicated: ~$94/mo
3. Xfinity Mobile: $64/mo (needs cancel)
4. Late fees Discover: $71 in 2 months
5. Restaurants: $162/mo

### Balance transfer strategy `[FIN]`

Wells Fargo + Chase → Citi 0% APR through Aug 2027. Upstart refinance for Achieve personal loan. Two-phase payoff: Discover first, then Citi.

---

# 15. COMMERCIALIZATION PLAN

| Phase | Timeline | What | Target |
|-------|----------|------|--------|
| 1 | NOW → Q2 2026 | Personal use for 3 months — build case studies | Alfredo |
| 2 | Q3 2026 | OpenClaw skill marketplace ($49-99) | OpenClaw users |
| 3 | Q4 2026 | SaaS via Telegram ($19/mo) | Airbnb hosts |
| 4 | 2027 | Scale or white-label to accounting firms | Small businesses |

**Key differentiator for SaaS:** Airbnb deduction tracking is the hook. Most expense trackers don't auto-categorize rental property deductions.

---

# 16. CURRENT STATE `[AUDIT]`

### Working ✅
- SKILL.md exists and is deployed `[AUDIT]`
- 11 library modules present (10 original + batch_receipts.py) `[CHANGES]`
- 6 config files (budgets, rules, payments, savings, processed_receipts, pending_categories) `[CHANGES]`
- Google Sheets OAuth token valid `[AUDIT]`
- 4 cron jobs ACTIVE and configured `[AUDIT]`
- **Reconciliation v2 deployed** — false positive elimination, multi-month CSV, Wells Fargo support `[CHANGES]`
- **Cashflow_Ledger tab** added to Google Sheets `[CHANGES]`
- **18 categories** (4 new: Pets, Debt_Interest, Bank_Fees, Refunds) `[CHANGES]`
- **Batch writes** to avoid 429 quota errors `[CHANGES]`
- **AI batch classification deployed and tested** `[CHANGES]`
- **Income tracking** (parse + auto-balance update) `[CHANGES]`
- **Batch receipt processor operational** — 17 Walmart receipts processed `[CHANGES]`
- **Cashflow_Ledger tab** with signed amounts and flow types `[CHANGES]`
- **Wells Fargo checking CSV support** `[CHANGES]`
- **Reconciliation fixes:** no false positives, correct payment classification, multi-month `[CHANGES]`

### Issues ⚠️
- **NOT referenced in CEO AGENTS.md** — skill auto-discovered by OpenClaw but not explicitly routed `[AUDIT]`
- **google_client_secret.json naming** — file is `google-client.json` instead `[AUDIT]`
- **Cron jobs designed but NOT configured** (cashflow 7:30AM, payments 9AM, weekly Sun, monthly 1st) `[PENDING]`
- **PDF statement support designed but NOT built** `[PENDING]`
- **Smart category creation (AI suggests new categories) designed but NOT built** `[PENDING]`

---

# 17. TECHNICAL LESSONS

| ID | Lesson | Impact |
|----|--------|--------|
| TL-28 | Google Sheets OAuth in WSL: use `run_local_server(port=18900, open_browser=False)` | Setup |
| TL-29 | Google Sheets needs BOTH spreadsheets AND drive scopes | Setup |
| TL-26 (PL) | When 3+ dollar amounts in receipt, auto-activate split mode | UX |
| TL-27 (PL) | gspread needs `pip install gspread google-auth google-auth-oauthlib` in litellm-venv | Dependency |
| TL-30 | Receipt parsing: use re.findall + max() for amounts, not re.search. Total > line items | Bug fix |
| TL-31 | When parsing receipts with 3+ dollar amounts, auto-activate split mode | UX |
| TL-32 | Credit card payments are POSITIVE amounts in Chase CSV — classify before splitting by sign | Classification bug |
| TL-33 | Spanish payment keywords (SU PAGO, PAGO AUTOMATICO) must be in classifier | i18n |
| TL-34 | AI batch classification costs ~$0.01 for 50 merchants — cheaper than defaulting to Other | Cost/quality tradeoff |

---

# 18. CONNECTIONS

```
Telegram (@Robotin1620_Bot) ──user input──→ Finance Tracker (skill)
Finance Tracker ──writes──→ Google Sheets ("Robotin Finance 2026")
Finance Tracker ──alerts──→ Telegram (budget warnings, payment reminders)
Cron jobs ──trigger──→ Finance Tracker (cashflow, payments, weekly, monthly)
LiteLLM SpendLogs ──(separate)──→ tracks API costs (not finance tracker)
```

**NOT connected to:** PostgreSQL marketing DB, Stripe, Declassified pipeline costs.

**Future:** Could integrate LiteLLM SpendLogs into the finance tracker for a unified view of all expenses (subscription + API + personal).

---

# 19. DIRECTORY STRUCTURE `[AUDIT]`

```
~/.openclaw/workspace/skills/finance-tracker/
├── SKILL.md
├── config/
│   ├── budgets.json              — Monthly budgets per category
│   ├── rules.json                — Auto-categorization rules
│   ├── payments.json             — Bill due dates and amounts
│   ├── savings.json              — Savings goals
│   ├── processed_receipts.json   — Batch receipt dedup tracker
│   └── pending_categories.json   — AI-suggested categories awaiting approval
├── scripts/
│   ├── finance.py                — Main entry point
│   ├── add_category.sh           — Safe category addition
│   ├── cron_runner.sh            — Cron job wrapper
│   └── lib/                      — 11 modules
│       ├── parser.py, rules.py, budget.py, cashflow.py
│       ├── payments.py, analyst.py, reconcile.py
│       ├── sheets.py, logger.py, config.py
│       ├── batch_receipts.py
│       └── __init__.py
├── logs/                         — Runtime logs
└── templates/                    — Report templates

~/.openclaw/credentials/
├── finance-tracker-token.json  — Google Sheets OAuth
└── google-client.json          — Google OAuth client config
```

---

# 20. PENDING ITEMS (prioritized)

| Priority | Item | Blocker | Est. effort |
|----------|------|---------|-------------|
| ~~🔴~~ | ~~Debug smoke test traceback~~ | ~~None~~ | DONE (fixed parser, batch writes, classification) |
| ~~🔴~~ | ~~Verify cron jobs~~ | ~~Wait for trigger~~ | STILL PENDING (designed, not configured) |
| 🔴 | Configure 4 cron jobs (cashflow, payments, weekly, monthly) | None | 1 hour |
| 🟡 | PDF bank statement support | None — spec ready | 3 hours |
| 🟡 | Smart category creation (AI suggests + user approves) | None — spec ready | 2 hours |
| 🟡 | CSV backfill verification — audit Transactions for misclassified items | None | 1 hour |
| 🟡 | Add Finance Tracker reference to CEO AGENTS.md | None | 10 min |
| 🟢 | Build unified cost dashboard (finance + LiteLLM spend) | Design needed | 4 hours |
| 🟢 | SaaS multi-tenant conversion | After 3 months personal use | 4-6 weeks |

---

**END OF WORKFLOW BIBLE — FINANCE TRACKER**

*Consolidates: Build Instructions, v1.1 Addendum, Split/Tax Upgrade doc, Plan Financiero, and Project Bible v2 §11. Verified against system audit 2026-03-29.*
