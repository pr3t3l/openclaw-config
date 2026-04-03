# Finance Tracker v2

Personal finance tracking skill for [OpenClaw](https://openclaw.ai). Tracks expenses via receipt photos and text, monitors budgets, calculates safe-to-spend, manages tax deductions with IRS-referenced rulepacks, and sends automated daily/weekly/monthly reports — all through your existing OpenClaw agent in Telegram.

## Features

- **Smart expense logging** — type "$15 Uber" or send a receipt photo
- **Two-tier merchant rules** — known merchants auto-categorize ($0 AI), unknown merchants use AI then auto-learn
- **Budget monitoring** — Fixed vs Variable categories with 3-tier alerts (80%/95%/100%)
- **Safe-to-spend** — daily spending limit accounting for upcoming bills, debt payments, savings goals, and sinking funds
- **Tax deductions** — pre-compiled US rulepacks (rental/freelance/small-business) with IRS Schedule C/E line references
- **Debt optimizer** — avalanche vs snowball payoff comparison with timeline and interest savings
- **Bank CSV import** — auto-detect Chase, Wells Fargo, Discover, Citi, Amex; import or reconcile
- **Automated reports** — daily cashflow, payment alerts, weekly review, monthly AI analysis
- **Bilingual** — English and Spanish, auto-detected from your OpenClaw profile
- **Deterministic setup** — 21-state Python state machine, not prompt-based (LLM cannot deviate)

## Requirements

- [OpenClaw](https://openclaw.ai) agent with `exec` capability
- Python 3.10+
- Google Sheets OAuth (GOG skill)
- `curl` (for AI calls and telemetry)

## Installation

Send the skill ZIP to your OpenClaw agent. It will:

1. Unpack to `{workspace}/skills/finance-tracker/`
2. Run `python3 scripts/finance.py install-check`
3. Guide you through setup via the state machine

Or manually:

```bash
cd ~/.openclaw/workspace/skills/
unzip finance-tracker-v2.zip
cd finance-tracker
python3 scripts/finance.py install-check
python3 scripts/finance.py setup-next "start"
```

## Quick Start

After setup:

```
You: $15 Uber
Bot: Added: $15.00 -> Transportation (Uber). Reply 'undo' to revert.

You: budget status
Bot: Budget Status (2026-04):
     [+] Groceries (V): $210/$300 (70%)
     [!] Restaurants (V): $85/$100 (85%)
     ...

You: safe to spend
Bot: Safe to spend today: $42.50
     Upcoming: Power $120 in 3 days
     Sinking funds: $3.33/day reserved
```

## Commands

30+ commands for transactions, budgets, reports, tax, debt, and system management. Run `python3 scripts/finance.py help` for the full list.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Complete technical architecture (file structure, data flow, state machine, schemas, AI cascade, lessons learned, how to extend)
- [src/docs/SYSTEM_GUIDE.md](src/docs/SYSTEM_GUIDE.md) — User-facing reference guide

## Structure

```
src/
  SKILL.md              — Agent router
  VERSION               — 2.0.0
  scripts/
    finance.py          — CLI entry point (30+ commands)
    lib/                — 14 Python modules
  install/
    schemas/            — 4 JSON schemas
    rulepacks/          — 4 US tax rulepacks
    migrations/         — Version migrations
  docs/
    SYSTEM_GUIDE.md     — User reference
```

## License

MIT
