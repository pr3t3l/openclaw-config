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

---

# 3. ARCHITECTURE — 8 MODULES

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

### Module 9 (designed, not implemented): Batch Receipt Processor `[BATCH]`

Processes 17+ receipt links (Walmart w-mt.co, Target, etc.) at once, replacing generic CSV-imported transactions with detailed line-item breakdowns.

```
Multiple receipt links → dedup check → fetch each (2s delay) → parse items
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
**Spec:** `BATCH_RECEIPT_INSTRUCTIONS.md` — ready for Claude Code

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
| **Cashflow_Ledger** | Signed transaction amounts for daily cashflow | date, amount (signed), category, running_balance |

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

### Library modules (10) `[AUDIT]`

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

### Config files `[AUDIT]`

| File | Purpose |
|------|---------|
| `budgets.json` | Monthly budgets per category |
| `rules.json` | Auto-categorization rules (merchant → category) |
| `payments.json` | Bill due dates, amounts, APR |
| `savings.json` | Savings goals with targets and deadlines |

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

# 10. MODEL ROUTING

| Component | Model | Cost |
|-----------|-------|------|
| Receipt parsing (text) | LLM via LiteLLM (cost-efficient model) | ~$0.001-0.003/parse |
| Receipt parsing (photo) | LLM via LiteLLM (vision model) | ~$0.005-0.01/parse |
| Monthly analyst report | LLM via LiteLLM | ~$0.01/report |
| Rule Engine | No AI — pattern matching | $0 |
| All other modules | No AI — deterministic | $0 |

---

# 11. PERSONAL FINANCIAL CONTEXT `[FIN]`

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

# 12. COMMERCIALIZATION PLAN

| Phase | Timeline | What | Target |
|-------|----------|------|--------|
| 1 | NOW → Q2 2026 | Personal use for 3 months — build case studies | Alfredo |
| 2 | Q3 2026 | OpenClaw skill marketplace ($49-99) | OpenClaw users |
| 3 | Q4 2026 | SaaS via Telegram ($19/mo) | Airbnb hosts |
| 4 | 2027 | Scale or white-label to accounting firms | Small businesses |

**Key differentiator for SaaS:** Airbnb deduction tracking is the hook. Most expense trackers don't auto-categorize rental property deductions.

---

# 13. CURRENT STATE `[AUDIT]`

### Working ✅
- SKILL.md exists and is deployed `[AUDIT]`
- 10 library modules present `[AUDIT]`
- 4 config files (budgets, rules, payments, savings) `[AUDIT]`
- Google Sheets OAuth token valid `[AUDIT]`
- 4 cron jobs ACTIVE and configured `[AUDIT]`
- **Reconciliation v2 deployed** — false positive elimination, multi-month CSV, Wells Fargo support `[CHANGES]`
- **Cashflow_Ledger tab** added to Google Sheets `[CHANGES]`
- **18 categories** (4 new: Pets, Debt_Interest, Bank_Fees, Refunds) `[CHANGES]`
- **Batch writes** to avoid 429 quota errors `[CHANGES]`

### Issues ⚠️
- **Smoke test failed** — `finance.py parse-text '$15.50 uber'` → traceback `[AUDIT]`
- **NOT referenced in CEO AGENTS.md** — skill auto-discovered by OpenClaw but not explicitly routed `[AUDIT]`
- **google_client_secret.json naming** — file is `google-client.json` instead `[AUDIT]`

### Not implemented
- Multi-category receipt splitting (designed in upgrade doc) `[UPG]`
- Tax deduction tracking (designed in upgrade doc) `[UPG]`
- CSV backfill of 2025-2026 historical data `[BUILD]`
- **Batch Receipt Processor** (spec ready in BATCH_RECEIPT_INSTRUCTIONS.md) `[BATCH]`

---

# 14. TECHNICAL LESSONS

| ID | Lesson | Impact |
|----|--------|--------|
| TL-29 | Google Sheets OAuth in WSL: use `run_local_server(port=18900, open_browser=False)` | Setup |
| TL-30 | Google Sheets needs BOTH spreadsheets AND drive scopes | Setup |
| TL-26 (PL) | When 3+ dollar amounts in receipt, auto-activate split mode | UX |
| TL-27 (PL) | gspread needs `pip install gspread google-auth google-auth-oauthlib` in litellm-venv | Dependency |

---

# 15. CONNECTIONS

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

# 16. DIRECTORY STRUCTURE `[AUDIT]`

```
~/.openclaw/workspace/skills/finance-tracker/
├── SKILL.md
├── config/
│   ├── budgets.json          — Monthly budgets per category
│   ├── rules.json            — Auto-categorization rules
│   ├── payments.json         — Bill due dates and amounts
│   └── savings.json          — Savings goals
├── scripts/
│   ├── finance.py            — Main entry point
│   ├── add_category.sh       — Safe category addition
│   ├── cron_runner.sh        — Cron job wrapper
│   └── lib/                  — 10 modules
│       ├── parser.py, rules.py, budget.py, cashflow.py
│       ├── payments.py, analyst.py, reconcile.py
│       ├── sheets.py, logger.py, config.py
│       └── __init__.py
├── logs/                     — Runtime logs
└── templates/                — Report templates

~/.openclaw/credentials/
├── finance-tracker-token.json  — Google Sheets OAuth
└── google-client.json          — Google OAuth client config
```

---

# 17. PENDING ITEMS (prioritized)

| Priority | Item | Blocker | Est. effort |
|----------|------|---------|-------------|
| 🔴 | Debug smoke test traceback (parse-text) | None | 30 min |
| 🔴 | Verify cron jobs actually execute and send Telegram messages | Wait for next cron trigger | 15 min |
| 🟡 | Implement multi-category receipt splitting | None — doc ready | 3 hours |
| 🟡 | Implement Airbnb tax deduction tracking | After split works | 3 hours |
| 🟡 | CSV backfill of 2025-2026 historical data | Bank CSV exports | 2 hours |
| 🟡 | Add Finance Tracker reference to CEO AGENTS.md | None | 10 min |
| 🟢 | Build unified cost dashboard (finance + LiteLLM spend) | Design needed | 4 hours |
| 🟢 | Start collecting personal use case studies for SaaS | 3 months of use | Ongoing |

---

**END OF WORKFLOW BIBLE — FINANCE TRACKER**

*Consolidates: Build Instructions, v1.1 Addendum, Split/Tax Upgrade doc, Plan Financiero, and Project Bible v2 §11. Verified against system audit 2026-03-29.*
