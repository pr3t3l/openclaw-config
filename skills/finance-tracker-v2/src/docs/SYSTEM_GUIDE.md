# Finance Tracker v2 — System Guide

## Overview

Personal finance tracker that runs as an OpenClaw skill. Tracks expenses via receipt photos and text, monitors budgets, calculates safe-to-spend, manages tax deductions, and sends automated reports.

## Setup

Setup is fully guided — the state machine asks questions one at a time:

1. **Preflight** — Checks Python, dependencies, Google OAuth credentials
2. **Context Detection** — Auto-reads name, language, timezone from OpenClaw config
3. **Mode Selection** — Quick (~2 min) or Full (~10 min)
4. **Income Sources** — Name, amount, frequency, type, account
5. **Business Rules** — Auto-loads tax rulepacks based on income types
6. **Debts** — Name, type, balance, APR, minimum payment (Full mode)
7. **Budget Categories** — Fixed vs Variable with monthly limits (Full mode)
8. **Recurring Bills** — Name, amount, due day, frequency (Full mode)
9. **Review** — Full summary before committing
10. **Google Sheet** — Creates 10-tab spreadsheet
11. **Cron Jobs** — 4 automated reports registered
12. **Telemetry** — Opt-in anonymous usage data
13. **Onboarding** — 3 quick missions to learn the basics

## Commands

### Transaction Management

| Command | Example | Description |
|---------|---------|-------------|
| `add "text"` | `add "$15 Uber"` | Parse and log an expense |
| `add-photo "path"` | `add-photo "/tmp/receipt.jpg"` | Parse receipt photo |
| `undo` | `undo` | Revert last transaction (5-min window) |
| `transactions [N]` | `transactions 20` | List last N transactions |

### Budget & Spending

| Command | Example | Description |
|---------|---------|-------------|
| `budget-status` | `budget-status` | Budget overview by category |
| `safe-to-spend` | `safe-to-spend` | Daily safe spending amount |
| `list-categories` | `list-categories` | Show all budget categories |
| `add-category` | `add-category "Pets" 200 variable` | Add budget category |
| `remove-category` | `remove-category "Pets"` | Remove category |

### Reports (Cron Targets)

| Command | Schedule | Description |
|---------|----------|-------------|
| `cashflow` | Mon-Fri 7:30am | Daily safe-to-spend + upcoming bills |
| `payment-check` | Daily 9am | Due-soon payment alerts |
| `weekly-review` | Sundays 8am | Week spending review + optimization |
| `monthly-report` | 1st of month 8am | Full month AI analysis |

### Financial Planning

| Command | Example | Description |
|---------|---------|-------------|
| `debt-strategy` | `debt-strategy` | Avalanche vs Snowball comparison |
| `savings-goals` | `savings-goals` | Show savings progress |
| `add-savings-goal` | `add-savings-goal "Vacation" 2000 "2026-12-31"` | Create goal |
| `update-balance` | `update-balance "Checking" 3200` | Set account balance |

### Tax

| Command | Example | Description |
|---------|---------|-------------|
| `tax-summary` | `tax-summary 2026` | Deductions by category |
| `tax-export` | `tax-export 2026` | CSV export for accountant |

### Bank Reconciliation

| Command | Example | Description |
|---------|---------|-------------|
| `reconcile "csv"` | `reconcile "/tmp/chase.csv"` | Match CSV vs logged |
| `analyze-csv "csv"` | `analyze-csv "/tmp/3months.csv"` | Detect bills/income |

Supported banks: Chase, Wells Fargo, Discover, Citi, Amex (auto-detected).

### Merchant Rules

| Command | Example | Description |
|---------|---------|-------------|
| `list-rules` | `list-rules` | Show auto-learned rules |
| `add-rule` | `add-rule "starbucks" "Restaurants" 0.95` | Manual rule |

Rules auto-learn from confirmed transactions. After 1 successful categorization, the merchant is remembered for future transactions ($0 AI cost on repeat visits).

Multi-category merchants (Walmart, Target, Costco, etc.) always trigger line-item parsing.

### System

| Command | Description |
|---------|-------------|
| `install-check` | Verify dependencies |
| `repair-sheet` | Validate sheet structure |
| `reconnect-sheets` | Refresh Google OAuth |
| `check-migrations` | Show pending migrations |
| `ai-backend` | Show detected AI backend |
| `help` | List all commands |

## How Merchant Rules Work

1. First time you log "$15 Uber" → AI parses it → categorized as Transportation
2. System saves rule: uber → Transportation (confidence 0.85)
3. Next time you log "$22 Uber" → rule matches instantly → $0 AI cost
4. Confidence increases with each use (up to 0.98)

Multi-category merchants (Walmart, Target, etc.) always use AI to parse line items individually.

## How Tax Deductions Work

During setup, the system loads pre-compiled rulepacks based on your income types:
- Salary → no deductions (personal)
- Rental → us-rental-property.v1 (9 Schedule E categories)
- Freelance → us-freelance.v1 (10 Schedule C categories)
- Business → us-small-business.v1 (12 Schedule C categories)

Each rulepack has IRS references and keywords. When you log a transaction at a multi-category merchant, the system checks each item against these keywords to flag potential deductions.

## Cron Jobs

| Job | Schedule | What it does |
|-----|----------|-------------|
| Daily Cashflow | Mon-Fri 7:30am | Safe-to-spend + upcoming 3 days |
| Payment Check | Daily 9am | Bills due today/tomorrow/3 days |
| Weekly Review | Sundays 8am | Spending breakdown + optimization |
| Monthly Report | 1st of month 8am | Full analysis with AI insights |

Timezone from OpenClaw config. Jobs registered via OpenClaw native cron.

## Sinking Funds

Non-monthly bills (quarterly, semi-annual, annual) are provisioned daily:
- Car Insurance $600/semi-annual → $3.33/day set aside
- This provision is subtracted from your safe-to-spend amount
- Prevents the "I have $500 available" → $600 insurance bill surprise

## Telemetry Policy

Anonymous, opt-in during setup. You can disable anytime.

**Collected:** App version, stage completion, timing buckets, feature counts, error codes, language, setup mode.

**NEVER collected:** Names, emails, account names, balances, transactions, merchant names, receipt text, Sheet URLs, API keys, IP addresses.

No user_id, no install_id, no session_id. Zero traceability.

## Troubleshooting

| Error | Fix |
|-------|-----|
| `SETUP_INCOMPLETE` | Run setup: the state machine will guide you |
| `GOG_AUTH_MISSING` | Set up Google OAuth: install GOG skill first |
| `SHEETS_CREATE_FAILED` | Check Google OAuth token. Run `reconnect-sheets` |
| `PREFLIGHT_FAILED` | Run `install-check` to see what's missing |
| `AI_TIMEOUT` | LiteLLM proxy may be down. Check `ai-backend` |
| Sheet columns wrong | Run `repair-sheet` to validate and identify drift |
| Budget shows $0 | Normal before first transaction. Reads from Sheets. |

## File Structure

```
finance-tracker/
  SKILL.md              — Agent router (thin, no logic)
  VERSION               — "2.0.0"
  requirements.txt      — Python deps
  install/
    manifest.json       — Package metadata
    schemas/            — JSON schemas (income, debt, budget, bill)
    rulepacks/          — Tax deduction rules by business type
    migrations/         — Version migration scripts
  config/               — Generated during setup
    tracker_config.json — Unified config
    sheets_config.json  — Sheet IDs
    setup_state.json    — Setup checkpoint
    merchant_rules.json — Auto-learned rules
  scripts/
    finance.py          — CLI entry point (30+ commands)
    lib/                — Core modules
  docs/
    SYSTEM_GUIDE.md     — This file
```
