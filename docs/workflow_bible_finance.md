# WORKFLOW BIBLE — FINANCE TRACKER (ROBOTIN FINANCE)
## Documento técnico autoritativo
### Last verified: 2026-04-02 (audit v3.1)
### Sources: Build Instructions + v1.1 Addendum + Split/Tax Upgrade + Plan Financiero + Bible v2 §11 + v1.0.8–v1.0.11 changelogs

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
| 2026-04-01 | v1.0.8: Setup UX overhaul — auto-detect name/language from USER.md, only ask 3 questions (cards, currency, tax), JSON-only setup (no interactive mode) | EOFError x7 eliminated | [v1.0.8] |
| 2026-04-01 | v1.0.8: Schedule E parsing fixed — "Airbnb" maps to "rental" automatically | Tax type mapping bug fixed | [v1.0.8] |
| 2026-04-01 | v1.0.8: Personal name removed from code comment (leak scanner) | Privacy fix | [v1.0.8] |
| 2026-04-01 | v1.0.9: 5 new commands (modify-payment, add-debt, update-debt, pay-debt, remove-goal) | 34→38 CLI subcommands | [v1.0.9] |
| 2026-04-01 | v1.0.9: KeyError fix in logger.py — format_confirmation uses .get() with defaults | Supabase telemetry id 40 | [v1.0.9] |
| 2026-04-01 | v1.0.9: Version tracking in telemetry — every event includes "v" field | Telemetry improvement | [v1.0.9] |
| 2026-04-01 | v1.0.10: Numbered command menu (38 items) when user sends /finance_tracker | UX overhaul | [v1.0.10] |
| 2026-04-01 | v1.0.11: Setup asks questions one at a time (not all 3 at once) | UX improvement | [v1.0.11] |
| 2026-04-01 | v1.0.11: Telemetry notice shown after setup (GDPR/CCPA compliance) | Legal requirement | [v1.0.11] |
| 2026-04-01 | v1.0.11: Enhanced telemetry — setup_input, ai_call, setup_sheets, tax_profile events | Observability | [v1.0.11] |
| 2026-04-01 | v1.0.11: Natural language tax type mapping ("Airbnb" → rental, "consulting" → freelancer) | SKILL.md improvement | [v1.0.11] |
| 2026-04-01 | Supabase telemetry: `reviewed` column added, events ≤46 marked reviewed | Ops improvement | [INFRA] |
| 2026-04-01 | Website: price updated $120 → $47, Stripe Payment Link connected | Commercialization | [WEB] |
| 2026-04-01 | Website: Privacy Policy page created at /products/finance-tracker-privacy | Legal/compliance | [WEB] |
| 2026-04-01 | Website: Dynamic pricing via Stripe API (Supabase Edge Function get-stripe-price) | Infrastructure | [WEB] |
| 2026-04-01 | Website: Portfolio card updated — "(Robotin)" → "(OpenClaw Skill)", chips show product features | Branding | [WEB] |
| 2026-04-01 | Website: Nav "Products" → "Workflows", new /workflows page with featured + other workflow cards | UX restructure | [WEB] |
| 2026-04-01 | Website: M.AI education updated — removed "in progress", added "Continuous AI Development" | Profile fix | [WEB] |
| 2026-04-01 | Website: Skills updated — new Automotive & Quality Standards category (ISO 9001, IATF 16949) | Profile enhancement | [WEB] |
| 2026-04-01 | Website: ScrollToTop component — pages now scroll to top on navigation | UX fix | [WEB] |
| 2026-04-01 | Website: OpenClaw Portfolio tabs now deep-linkable via ?tab= param | UX improvement | [WEB] |
| 2026-04-02 | Stripe: New account created, migrated from old profile | Infrastructure | [WEB] |
| 2026-04-02 | Stripe: Switched from hardcoded price_id to lookup keys (`financial_tracker_standard`) | Architecture | [WEB] |
| 2026-04-02 | Stripe: Dynamic checkout sessions replace static Payment Link | Architecture | [WEB] |
| 2026-04-02 | Supabase: Migrated to own project `oetfiiatbzfydbtzozlz` (Lovable project inaccessible via CLI) | Infrastructure | [WEB] |
| 2026-04-02 | Supabase: Edge Functions deployed — `get-stripe-price` + `create-checkout` (no-verify-jwt) | Infrastructure | [WEB] |
| 2026-04-02 | Website: Headline changed to "Stop guessing. Start tracking every purchase — line by line." | Copy optimization | [WEB] |

---

# 3. ARCHITECTURE — 10 MODULES

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

| 4 | **Setup Wizard** | Interactive setup (cards, currency, tax), auto-detect name/language from USER.md, Google Sheets creation | setup_wizard.py |
| 9 | **Batch Receipt Processor** | Process multiple receipt links, match against CSV rows, replace generic rows with detailed line items | batch_receipts.py |
| 10 | **Telemetry** | Anonymous usage analytics to Supabase, version tracking, opt-out support | telemetry.py |

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

### Library modules (13) `[AUDIT v3.0]`

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
| `logger.py` | Transaction logging + confirmation formatting |
| `config.py` | Configuration loading + AI call wrapper with telemetry |
| `batch_receipts.py` | Batch receipt link processing with dedup and CSV row replacement |
| `setup_wizard.py` | First-run setup wizard — auto-detect name/language, 3 questions, Sheets creation |
| `telemetry.py` | Anonymous usage analytics to Supabase (opt-out, version tracking) |

### Config files `[AUDIT v3.0]`

| File | Purpose |
|------|---------|
| `tracker_config.json` | Unified config — cards, currency, categories, budgets, payments, savings, tax profile |
| `rules.json` | Auto-categorization rules (merchant → category) |
| `processed_receipts.json` | Dedup tracker for batch receipt links |

### Utility scripts

- `add_category.sh` — safely adds a new category
- `cron_runner.sh` — wrapper for cron job execution
- `setup_crons.sh` — install/remove cron jobs
- `test_crons.sh` — test cron job execution

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

# 15. TELEMETRY SYSTEM `[v1.0.9+]`

### Infrastructure
- **Supabase project:** oetfiiatbzfydbtzozlz (separate from website Supabase)
- **Table:** `telemetry` with columns: id, install_id, event, data (JSONB), created_at, reviewed (bool)
- **Version tracking:** every event includes `"v": "1.0.11"` in data field

### Events tracked
| Event | Data | Source |
|-------|------|--------|
| `install` | os, python_version, v | First run |
| `setup_complete` | language, currency, categories_count, cards_count, v | After setup |
| `setup_input` | cards_count, currency, tax_type, had_tax_description, source | After setup |
| `parse_text` / `parse_photo` | duration_ms, had_rule, confidence, v | Each parse |
| `command` | name, success, duration_ms, v | Each CLI command |
| `ai_call` | command, model, duration_ms, status (success/timeout/empty/invalid_json/error) | Each AI call |
| `setup_sheets` | created_new, tabs_created | setup-sheets command |
| `tax_profile` | method (ai_wizard/basic_fallback/ai_failed), tax_type, rules_count | Tax profile creation |
| `error` | error_type, command, v | On exceptions |
| `reconcile` | bank, tx_count, matched, match_rate, v | CSV reconciliation |

### Opt-out
- `finance.py telemetry off` — disables, no data sent
- `finance.py telemetry on` — re-enables
- `finance.py telemetry status` — shows current state
- `finance.py telemetry info` — shows what is collected

### Reviewed column
- `reviewed = false` (default) — new unreviewed events
- Query: `SELECT * FROM telemetry WHERE reviewed = false ORDER BY id DESC;`
- After review: `UPDATE telemetry SET reviewed = true WHERE id <= N;`

### Never collected
Names, emails, financial data, transaction amounts, merchant names, receipt contents, spreadsheet URLs, file paths, IP addresses.

---

# 16. COMMERCIALIZATION — LIVE `[WEB]`

### Product page
- URL: https://alfredopretelvargas.com/products/finance-tracker
- Workflows page: https://alfredopretelvargas.com/workflows
- Privacy: https://alfredopretelvargas.com/products/finance-tracker-privacy
- Headline: "Stop guessing. Start tracking every purchase — line by line."
- **Price: dynamic from Stripe via lookup key** (no code changes needed to update price)

### Stripe integration (new account as of 2026-04-02)
- **Lookup key:** `financial_tracker_standard` (used by both price display and checkout)
- **No hardcoded price_id** — lookup key resolves to current active price
- **Dynamic Checkout Sessions** via `create-checkout` Edge Function (replaces static Payment Link)
- To change price: create new price in Stripe with same lookup key + "Transfer lookup key" checked

### Supabase (Edge Functions)
- Project: `oetfiiatbzfydbtzozlz` (own project — Lovable project `tajcmrnpnkfkkjunzkae` inaccessible via CLI)
- Edge Function 1: `get-stripe-price` — accepts `lookupKey`, returns price + priceId
- Edge Function 2: `create-checkout` (no-verify-jwt) — creates Stripe Checkout Session from lookup key
- Secret: `STRIPE_API_KEY` (set via dashboard → Edge Functions → Secrets)

### Frontend architecture
- `useStripePrice(lookupKey, fallback)` hook with in-memory cache — returns `{ formatted, priceId }`
- Used in: FinanceTracker.tsx, Workflows.tsx, PortfolioSection.tsx
- Checkout: `supabase.functions.invoke("create-checkout", { body: { lookupKey } })` → opens Stripe Checkout
- Fallback price shown instantly, replaced when Stripe responds

### Website structure
- Nav: "Workflows" → /workflows (replaced "Products" → /products/finance-tracker)
- /workflows page: 2 featured cards (Declassified + Finance Tracker) + 4 smaller "Other Workflows" cards + Contact CTA
- Each workflow card deep-links to OpenClaw Portfolio via `?tab=` param
- ScrollToTop component ensures pages start at top on navigation
- Deployment: Vercel (connected to GitHub) — replaced Lovable Publish

### Portfolio card (Home page)
- Title: "Finance Tracker (OpenClaw Skill)"
- Chips: AI Receipt Parsing, Tax Deductions, Budget Alerts, Self-Hosted

### About section updates (2026-04-01)
- M.AI: removed "in progress" — completed, now shows "Continuous AI Development"
- Skills: new "Automotive & Quality Standards" category (ISO 9001, IATF 16949)
- Skills: added Prompt Engineering, Data Mining, Six Sigma, CNC Programming, AutoCAD, Master's in AI

### Pricing history
| Date | Price | Reason |
|------|-------|--------|
| 2026-03-31 | $120 | Initial listing (old Stripe account) |
| 2026-04-01 | $47 | Adjusted for launch (old Stripe account) |
| 2026-04-02 | $20 | New Stripe account, lookup key approach |
| 2026-04-02 | Dynamic | Price set in Stripe, auto-reflected via lookup key |

**Key differentiator:** Line-item level tracking is the hook. Most expense trackers categorize at the receipt level — this one parses individual items and flags deductions per line.

---

# 17. CURRENT STATE `[AUDIT v3.0]`

### Version: v1.0.11 (68K ZIP)

### Working ✅
- SKILL.md: 38-command numbered menu + full agent instructions `[v1.0.10]`
- 13 library modules (11 original + setup_wizard.py + telemetry.py) `[v1.0.11]`
- 38 CLI subcommands in finance.py `[v1.0.10]`
- Unified config: tracker_config.json (replaced 4 separate JSON files) `[v1.0.8]`
- Setup wizard: 3 questions one-at-a-time, auto-detect name/language from USER.md `[v1.0.11]`
- Natural language tax type mapping: "Airbnb" → rental, "consulting" → freelancer `[v1.0.11]`
- Telemetry: anonymous analytics to Supabase with version tracking `[v1.0.9]`
- Telemetry notice shown after setup (GDPR/CCPA compliant) `[v1.0.11]`
- Enhanced telemetry events: setup_input, ai_call, setup_sheets, tax_profile `[v1.0.11]`
- KeyError fix in logger format_confirmation (.get() with defaults) `[v1.0.9]`
- Google Sheets OAuth token valid `[AUDIT]`
- 4 cron jobs configured via setup_crons.sh `[v1.0.8]`
- Reconciliation v2: false positive elimination, multi-month CSV, Wells Fargo `[CHANGES]`
- AI batch classification + income tracking + batch receipt processor `[CHANGES]`
- Website live: product page + privacy policy + Stripe checkout `[WEB]`
- Dynamic pricing: Stripe → Supabase Edge Function → frontend `[WEB]`
- Leak scanner: package.sh checks for personal data before packaging `[v1.0.8]`

### Bugs fixed (v1.0.8–v1.0.11)
| Bug | Fix | Version |
|-----|-----|---------|
| EOFError x7 — setup without JSON | JSON-only setup, NEVER run without args | v1.0.8 |
| Schedule E parsing — "Airbnb" not recognized | Auto-map natural language to tax types | v1.0.8 |
| Personal name in code comment | Leak scanner + removed | v1.0.8 |
| KeyError in logger (Supabase id 40) | .get() with defaults in format_confirmation | v1.0.9 |
| Setup questions overwhelm user | Ask one at a time, not all 3 together | v1.0.11 |

### Known issue ⚠️
| Issue | Impact | Workaround |
|-------|--------|------------|
| AI tax profile generation fails when LiteLLM proxy is down | Falls back to basic_profile | User can retry with /finance-new-tax-profile later |
| NOT referenced in CEO AGENTS.md | Skill auto-discovered but not explicitly routed | Add reference |
| PDF statement support NOT built | Spec ready | — |

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
Finance Tracker ──telemetry──→ Supabase (oetfiiatbzfydbtzozlz)
Cron jobs ──trigger──→ Finance Tracker (cashflow, payments, weekly, monthly)
LiteLLM SpendLogs ──(separate)──→ tracks API costs (not finance tracker)
Website ──Stripe price──→ Supabase Edge Function (tajcmrnpnkfkkjunzkae) ──→ Stripe API
Website ──checkout──→ Stripe Payment Link
```

**Two Supabase projects:**
- `oetfiiatbzfydbtzozlz` — telemetry (STRIPE_API_KEY configured here for webhook)
- `tajcmrnpnkfkkjunzkae` — website (STRIPE_API_KEY needed here for get-stripe-price)

**Future:** Could integrate LiteLLM SpendLogs into the finance tracker for a unified view of all expenses (subscription + API + personal).

---

# 19. DIRECTORY STRUCTURE `[AUDIT v3.0]`

```
~/.openclaw/workspace/skills/finance-tracker/
├── SKILL.md                         — 38-command menu + agent instructions
├── config/
│   ├── tracker_config.json          — Unified config (cards, currency, categories, budgets, payments, savings, tax)
│   ├── rules.json                   — Auto-categorization rules
│   └── processed_receipts.json      — Batch receipt dedup tracker
├── docs/
│   └── SYSTEM_GUIDE.md              — Complete system reference (521 lines)
├── scripts/
│   ├── finance.py                   — Main entry point (38 CLI subcommands)
│   ├── add_category.sh              — Safe category addition
│   ├── cron_runner.sh               — Cron job wrapper
│   ├── setup_crons.sh               — Install/remove cron jobs
│   ├── test_crons.sh                — Test cron execution
│   └── lib/                         — 13 modules
│       ├── parser.py, rules.py, budget.py, cashflow.py
│       ├── payments.py, analyst.py, reconcile.py
│       ├── sheets.py, logger.py, config.py
│       ├── batch_receipts.py, setup_wizard.py, telemetry.py
│       └── __init__.py
├── logs/                            — Runtime logs
└── templates/                       — Report templates

~/.openclaw/credentials/
├── finance-tracker-token.json  — Google Sheets OAuth
└── google-client.json          — Google OAuth client config
```

---

# 20. VERSION HISTORY

| Version | Date | Key changes |
|---------|------|-------------|
| v1.0.0–v1.0.7 | 2026-03-27–31 | Initial build through reconciliation fixes |
| v1.0.8 | 2026-04-01 | Setup UX overhaul, EOFError fix, Schedule E fix, leak scanner |
| v1.0.9 | 2026-04-01 | 5 new commands, KeyError fix, version tracking in telemetry |
| v1.0.10 | 2026-04-01 | Numbered command menu (38 items), VERSION bump |
| v1.0.11 | 2026-04-01 | Questions one-at-a-time, telemetry notice, enhanced events, natural language tax mapping |

---

# 21. PENDING ITEMS (prioritized)

| Priority | Item | Blocker | Est. effort |
|----------|------|---------|-------------|
| ~~🔴~~ | ~~Debug smoke test traceback~~ | ~~None~~ | DONE (v1.0.7) |
| ~~🔴~~ | ~~EOFError x7 in setup~~ | ~~None~~ | DONE (v1.0.8) |
| ~~🔴~~ | ~~Schedule E parsing bug~~ | ~~None~~ | DONE (v1.0.8) |
| ~~🔴~~ | ~~KeyError in logger~~ | ~~None~~ | DONE (v1.0.9) |
| ~~🔴~~ | ~~Stripe checkout + dynamic pricing~~ | ~~None~~ | DONE (website) |
| ~~🔴~~ | ~~Deploy get-stripe-price Edge Function~~ | ~~None~~ | DONE (oetfiiatbzfydbtzozlz) |
| ~~🔴~~ | ~~Set STRIPE_API_KEY in website Supabase~~ | ~~None~~ | DONE (new Stripe account) |
| ~~🔴~~ | ~~Migrate from hardcoded price_id to lookup keys~~ | ~~None~~ | DONE (financial_tracker_standard) |
| ~~🔴~~ | ~~Create dynamic checkout (replace static Payment Link)~~ | ~~None~~ | DONE (create-checkout Edge Function) |
| 🟡 | PDF bank statement support | None — spec ready | 3 hours |
| 🟡 | Smart category creation (AI suggests + user approves) | None — spec ready | 2 hours |
| 🟡 | Add Finance Tracker reference to CEO AGENTS.md | None | 10 min |
| 🟡 | AI tax profile: add retry logic when LiteLLM is down | None | 1 hour |
| 🟢 | Build unified cost dashboard (finance + LiteLLM spend) | Design needed | 4 hours |
| 🔴 | **Product delivery system** — qué pasa cuando alguien paga? Opciones: (1) Stripe webhook → email automático con link de descarga, (2) Stripe webhook → redirect a success page con download, (3) Gumroad/Lemon Squeezy (manejo delivery integrado), (4) Manual via email. Necesita decisión + implementación | Decisión de approach | 2-4 hours |
| 🟢 | SaaS multi-tenant conversion | After 3 months personal use | 4-6 weeks |

---

**END OF WORKFLOW BIBLE — FINANCE TRACKER**

*Consolidates: Build Instructions, v1.1 Addendum, Split/Tax Upgrade doc, Plan Financiero, Project Bible v2 §11, v1.0.8–v1.0.11 changelogs, and Session 10 website/Stripe migration. Verified against system audit 2026-04-02.*
