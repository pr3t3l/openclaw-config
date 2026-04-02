# CLAUDE CODE SESSION PLAN — Finance Tracker v2

## Prerequisites
- Implementation Guide: copy to `~/.openclaw/workspace/skills/finance-tracker-v2/docs/IMPLEMENTATION_GUIDE.md`
- V1 source: `~/.openclaw/workspace/skills/finance-tracker/` (read-only reference)
- V2 target: `~/.openclaw/workspace/skills/finance-tracker-v2/` (new directory)

---

## Session 1: Foundation
```
Read the Implementation Guide at docs/IMPLEMENTATION_GUIDE.md, Phase 1.
Create the v2 directory structure.
Build: errors.py, config.py, state_machine.py (core class + state enum + transitions).
Build: All 4 JSON schemas in install/schemas/.
Build: VERSION file, requirements.txt.
Write unit tests for state transitions.
Do NOT build any runtime commands yet — only setup flow skeleton.
The v1 code is at ~/.openclaw/workspace/skills/finance-tracker/ for reference.
```

## Session 2: Setup Engine
```
Read the Implementation Guide at docs/IMPLEMENTATION_GUIDE.md, Phase 2.
Build: finance.py (entry point with install-check, preflight, setup-next, setup-status).
Build: ai_parser.py (income, debt, transaction parsing via LiteLLM curl).
Implement UNPACK, PREFLIGHT, DETECT_CONTEXT states fully.
Implement SETUP_MODE_SELECT (quick vs full).
Test: python3 finance.py install-check should validate structure.
Test: python3 finance.py preflight should check gog + exec + deps.
Test: python3 finance.py setup-next "start" should begin setup flow.
```

## Session 3: Collectors
```
Read the Implementation Guide at docs/IMPLEMENTATION_GUIDE.md, Phase 3.
Implement all collector states: INCOME_COLLECT, DEBT_COLLECT, BUDGET_COLLECT, BILLS_COLLECT.
Implement confirm states: INCOME_CONFIRM, DEBT_CONFIRM, BUDGET_CONFIRM.
Implement BUSINESS_RULES_MAP + BUSINESS_RULES_CONFIRM.
Implement REVIEW_ALL state.
Build all rulepacks in install/rulepacks/ (us-personal, us-rental, us-freelance, us-small-business).
Test full setup flow: preflight → income → business → debt → budget → bills → review.
All meta-commands must work: undo, list, edit N, skip, done signals.
```

## Session 4: Google Sheets
```
Read the Implementation Guide at docs/IMPLEMENTATION_GUIDE.md, Phase 4.
Build: sheets.py (create sheet, batch_update, write by sheetId, validate schema, auto-repair).
Build: templates/sheet_structure.json.
Build: sheets_config.json management.
Implement SHEETS_CREATE state.
Cherry-pick gspread connection logic from v1 sheets.py.
Test: create a real Google Sheet with all 10 tabs.
Test: verify sheetId storage and tab-name-independent access.
Implement monthly archival function (Archive_YYYY_MM).
```

## Session 5: Runtime Commands
```
Read the Implementation Guide at docs/IMPLEMENTATION_GUIDE.md, Phase 5.
Build: merchant_rules.py (two-tier: merchant + line-item, normalization, auto-learn).
Build: rules.py (base rules from rulepack + user overlays).
Build: parser.py (receipt text + photo parsing, line-item extraction).
Implement finance.py commands: add, add-photo, transactions, edit-transaction, delete-transaction.
Implement: add-category, remove-category, list-categories, list-rules, add-rule.
Implement: add-business (load new rulepack + create rules).
Implement: tax-summary, tax-export.
Implement implicit confirmation with undo for high-confidence transactions.
Cherry-pick from v1 parser.py and rules.py but adapt to v2 architecture.
```

## Session 6: Reports + Cashflow + Cron
```
Read the Implementation Guide at docs/IMPLEMENTATION_GUIDE.md, Phase 6.
Build: cashflow.py (safe-to-spend with sinking funds + savings).
Build: budget.py (tracking with fixed/variable, alerts at thresholds).
Build: payments.py (calendar with multi-frequency, sinking fund provisions).
Build: reports.py (daily cashflow, weekly review with optimization, monthly AI analysis).
Build: debt_optimizer.py (avalanche + snowball comparison).
Build: reconcile.py + csv_analyzer.py (bank format detection, reconciliation).
Implement CRONS_SETUP state (output cron specs for OpenClaw native cron).
Implement all cron-triggered commands: cashflow, payment-check, weekly-review, monthly-report.
Implement: safe-to-spend, budget-status, debt-strategy, projection, update-balance.
Implement: savings-goals, add-savings-goal.
Implement: repair-sheet, reconnect-sheets.
Implement drift protection: inactivity nudge in cashflow report.
```

## Session 7: SKILL.md + Telemetry + Packaging
```
Read the Implementation Guide at docs/IMPLEMENTATION_GUIDE.md, Phase 7.
Build: SKILL.md (thin router — setup detection, command routing, cron registration).
Build: telemetry.py (Supabase events, zero PII, opt-in only).
Implement TELEMETRY_OPT + ONBOARDING_MISSIONS + COMPLETE states.
Build: migrations.py (version detection, sequential migration runner).
Build: install/manifest.json.
Build: docs/SYSTEM_GUIDE.md (complete user reference).
Implement: telemetry on/off, version, help commands.
Test FULL end-to-end: unzip → preflight → setup → sheets → crons → onboarding → runtime.
Package as ZIP with leak scanner (no API keys, no personal data).
```

---

## TESTING PROTOCOL PER SESSION

After each session, test in this order:
1. `python3 finance.py install-check` — structure OK
2. `python3 finance.py preflight` — deps OK
3. `python3 finance.py setup-next "start"` — flow begins
4. Walk through the setup conversation manually
5. Verify JSON output format on every response
6. Verify setup_state.json checkpointing (kill mid-setup, resume)
7. Verify error codes are typed and actionable

---

## NOTES FOR CLAUDE CODE

- DO NOT run `openclaw` commands directly — we're building the skill files, not operating the gateway.
- The LiteLLM proxy is at http://127.0.0.1:4000 — use for AI parsing calls.
- Google Sheets OAuth token: ~/.openclaw/credentials/finance-tracker-token.json
- Google client: ~/.openclaw/credentials/google-client.json
- Test Google Sheets operations against a test spreadsheet, not production.
- Git: after each session, commit to openclaw-config repo with descriptive message.
