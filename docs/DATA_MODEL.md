# DATA_MODEL.md — OpenClaw
<!--
SCOPE: ALL data storage schemas — PostgreSQL, Google Sheets, JSON manifests.
NOT HERE: API endpoints → INTEGRATIONS.md
NOT HERE: Why we chose these → PROJECT_FOUNDATION.md §6
NOT HERE: Cost data interpretation → CONSTITUTION.md §6

UPDATE FREQUENCY: When a workflow adds or modifies tables/sheets/schemas.
-->

**Last updated:** 2026-04-04
**Sources:** Project Bible v2 §12, workflow bibles (archived in docs/archivo/)

---

## Conventions

| Convention | Standard |
|-----------|----------|
| ID format | UUID v4 for run_id, agent-generated IDs; serial for DB PKs |
| Timestamps | PostgreSQL TIMESTAMPTZ; ISO 8601 in JSON |
| Field naming | snake_case (PostgreSQL, Python); camelCase (TypeScript) |
| Soft delete | `is_active: false` where applicable |
| Null handling | NULL in DB; omit field in JSON |

---

## 1. PostgreSQL 16 (port 5432)

**Connection:** `postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db`
**GUI:** DBeaver on Windows (Host: localhost, Port: 5432, DB: litellm_db)

### Schema: `marketing` (24 tables)

Created by Marketing System. See docs/archivo/workflow_bible_marketing.md for full column details.

#### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `buyer_segments` | Buyer personas for marketing | segment_id, segment_name, priority, demographics, pain_points |
| `brand_strategy` | Brand positioning per product | strategy_id, product_slug, positioning, tone, visual_identity |
| `seo_keywords` | Keyword research results | keyword_id, keyword, volume, difficulty, intent, cluster |
| `channel_strategy` | Per-channel marketing config | channel_id, channel_name, cadence, format, cta_strategy |
| `competitor_analysis` | Competitive landscape | competitor_id, name, strengths, weaknesses, tier |

#### Content Tables

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `weekly_content` | Generated scripts/ads/emails per week | content_id, product_slug, week_id, content_type, body, status |
| `content_calendar` | Publishing schedule | calendar_id, week_id, channel, publish_date, content_id |
| `email_campaigns` | Email content per persona | campaign_id, week_id, persona, subject, body, cta |
| `ad_creatives` | Ad copy variants (A/B) | creative_id, week_id, variant, headline, body, cta |
| `video_scripts` | Veo 3 / marketing video scripts | script_id, week_id, hook, body, cta, duration_target |

#### Quality & Tracking

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `claim_lint_results` | QA linter output per content | lint_id, content_id, claim_type, severity, passed |
| `qa_reviews` | Quality gate results | review_id, week_id, gate, score, criticals, passed |
| `cost_metrics` | Per-run cost tracking | metric_id, run_id, module, input_tokens, output_tokens, estimated_usd |

#### Growth Intelligence

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `growth_metrics` | Raw metrics ingested | metric_id, week_id, channel, metric_name, value |
| `growth_diagnosis` | AI diagnosis of metric patterns | diagnosis_id, week_id, finding, severity, recommendation |
| `experiments` | A/B test definitions and results | experiment_id, hypothesis, variant_a, variant_b, result |

#### Stripe & Orders

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `stripe_orders` | Synced from Stripe | order_id, stripe_id, amount, currency, status, product, created_at |

**Note:** Full column definitions, FK relationships (33 FKs), and CHECK constraints (142) are documented in the archived bible. Run `\d+ marketing.table_name` in psql for current schema.

### Schema: `public` (LiteLLM managed)

LiteLLM auto-creates and manages these tables. Do NOT modify manually.

| Table | Purpose |
|-------|---------|
| `LiteLLM_SpendLogs` | Token usage and cost per API call |
| `LiteLLM_TeamTable` | Team/org config |
| `LiteLLM_UserTable` | User config |
| Various others | LiteLLM internal state |

**Useful query:**
```sql
-- Cost per model last 7 days
SELECT model, COUNT(*) as calls, SUM(spend) as total_usd
FROM "LiteLLM_SpendLogs"
WHERE "startTime" > NOW() - INTERVAL '7 days'
GROUP BY model ORDER BY total_usd DESC;
```

---

## 2. Google Sheets (Finance Tracker)

**Spreadsheet:** "Robotin Finance 2026"
**Access:** OAuth via `~/.openclaw/credentials/finance-tracker-token.json`
**Module:** Finance Tracker skill in CEO workspace

### Tabs

| Tab | Purpose | Key Columns |
|-----|---------|------------|
| `Transactions` | All logged expenses/income | date, description, amount, category, payment_method, is_deductible |
| `Budgets` | Monthly budget by category | category, monthly_limit, current_spent, remaining |
| `Categories` | Category definitions | category_name, type (expense/income), tax_relevant |
| `Cashflow_Ledger` | Signed amounts with flow type | date, description, signed_amount, flow_type (expense/refund/income/payment/transfer) |
| `Reconciliation` | Bank CSV import matching | bank_date, bank_description, bank_amount, matched_transaction_id, status |
| `Schedule_E` | Airbnb tax deduction tracking | expense_date, description, amount, category, property, deduction_type |
| `Payment_Methods` | Credit cards and accounts | name, type, last_four, current_balance, due_date |

---

## 3. JSON Manifests (per-run state)

### Pipeline manifest: `manifest.json`

Lives in each case directory. Updated after every phase.

```json
{
  "case_id": "string — unique case identifier",
  "tier": "SHORT | NORMAL | PREMIUM",
  "status": "in_progress | completed | failed",
  "phases": {
    "phase_name": {
      "status": "pending | running | completed | failed",
      "started_at": "ISO 8601",
      "completed_at": "ISO 8601",
      "cost": {
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_usd": 0.00
      },
      "output_path": "string — path to phase output",
      "error": "string | null"
    }
  },
  "total_cost": {
    "tracked_usd": 0.00,
    "orchestrator_overhead_usd": 0.00,
    "estimated_total_usd": 0.00
  }
}
```

### Marketing run state: `run_state.json`

Lives in `products/{slug}/weekly_runs/{week_id}/`.

```json
{
  "product_slug": "string",
  "week_id": "2026-WXX",
  "status": "strategy_pending | content_generating | qa_review | approved | published",
  "strategy_version": "string — git hash or date",
  "content_generated": ["scripts", "ads", "emails"],
  "qa_result": {
    "passed": true,
    "criticals": 0,
    "warnings": 0
  },
  "cost_usd": 0.00
}
```

### Planner run state: `runs/{slug}/plan_state.json`

```json
{
  "slug": "string — idea identifier",
  "status": "phase_a | phase_b | phase_c | completed | failed",
  "current_phase": "A1 | A2 | A3 | B1 | B2 | B3 | C1 | C2 | C3",
  "gate_results": {
    "gate_1": { "passed": true, "score": 85 },
    "gate_2": { "passed": true, "score": 72 },
    "gate_3": { "passed": false, "issues": 3 }
  },
  "cost_usd": 0.00,
  "artifacts": ["00_intake.json", "01_gaps.json", "..."]
}
```

---

## Relationships

```
PostgreSQL (marketing schema)
  ├── buyer_segments ←── weekly_content (per persona)
  ├── weekly_content ←── claim_lint_results (per content)
  ├── weekly_content ←── qa_reviews (per week)
  └── cost_metrics (standalone, per run)

PostgreSQL (public schema)
  └── LiteLLM_SpendLogs (standalone, per API call)

Google Sheets
  ├── Transactions → Categories (by category_name)
  ├── Transactions → Payment_Methods (by payment_method)
  ├── Reconciliation → Transactions (by matched_transaction_id)
  └── Schedule_E ← filtered from Transactions (is_deductible=true)

JSON Manifests
  └── One per run, independent, not cross-referenced
```

---

## Migration Log

| Date | Store | Change | Status |
|------|-------|--------|--------|
| 2026-03-28 | PostgreSQL | marketing schema v2.1 — 24 tables, 33 FK, 142 CHECK | ✅ Deployed |
| 2026-03-28 | PostgreSQL | db.py — 46 functions, 926 lines | ✅ Deployed |
| 2026-03-31 | Google Sheets | Cashflow_Ledger tab added | ✅ Deployed |
| 2026-03-31 | Google Sheets | Categories expanded 14→18 | ✅ Deployed |
| 2026-04-04 | All | Documented in SDD DATA_MODEL.md | ✅ This file |
