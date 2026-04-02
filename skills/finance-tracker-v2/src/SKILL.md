---
name: finance_tracker
description: Personal finance tracker with receipt parsing, budget monitoring, tax deductions, and automated reports.
metadata: {"openclaw": {"requires": {"bins": ["python3", "curl"]}, "os": ["linux"]}}
---

# Finance Tracker v2

## Setup

On ANY user message related to finance tracking, FIRST check setup status:

```
exec python3 {baseDir}/scripts/finance.py setup-status
```

If `setup_complete` is `false`:

```
exec python3 {baseDir}/scripts/finance.py setup-next "<user_message>"
```

Show the `message` field from the JSON response to the user. DO NOT add your own commentary, questions, or suggestions. DO NOT reorder steps. The script controls the conversation — just relay messages.

If the response contains a `cron_jobs` key, register each job using the cron tool with the exact parameters from the JSON:

```
For each job in cron_jobs:
  cron create --name "<job.name>" --schedule "<job.schedule>" --payload "<job.payload>" --delivery "<job.delivery>"
```

If the response contains `error`, show the error message. If `suggested_action` is present, tell the user to run it.

Continue relaying `setup-next` calls until `done` is `true`.

## Runtime

After setup is complete, map user intents to these commands:

| User Intent | Command |
|-------------|---------|
| Sends a receipt photo | `exec python3 {baseDir}/scripts/finance.py add-photo "<saved_photo_path>"` |
| Text with dollar amount (e.g. "$15 Uber", "gasté $45 en Publix") | `exec python3 {baseDir}/scripts/finance.py add "<user_text>"` |
| "budget", "budget status", "presupuesto" | `exec python3 {baseDir}/scripts/finance.py budget-status` |
| "safe to spend", "how much can I spend", "cuánto puedo gastar" | `exec python3 {baseDir}/scripts/finance.py safe-to-spend` |
| "cashflow", "daily report" | `exec python3 {baseDir}/scripts/finance.py cashflow` |
| "transactions", "last transactions", "últimas transacciones" | `exec python3 {baseDir}/scripts/finance.py transactions 10` |
| "undo", "deshacer" | `exec python3 {baseDir}/scripts/finance.py undo` |
| "weekly review", "resumen semanal" | `exec python3 {baseDir}/scripts/finance.py weekly-review` |
| "monthly report", "reporte mensual" | `exec python3 {baseDir}/scripts/finance.py monthly-report` |
| "debt strategy", "estrategia de deuda" | `exec python3 {baseDir}/scripts/finance.py debt-strategy` |
| "tax summary", "resumen fiscal" | `exec python3 {baseDir}/scripts/finance.py tax-summary` |
| "tax export" | `exec python3 {baseDir}/scripts/finance.py tax-export` |
| "reconcile" + file path | `exec python3 {baseDir}/scripts/finance.py reconcile "<csv_path>"` |
| "analyze csv" + file path | `exec python3 {baseDir}/scripts/finance.py analyze-csv "<csv_path>"` |
| "categories", "categorías" | `exec python3 {baseDir}/scripts/finance.py list-categories` |
| "add category" + details | `exec python3 {baseDir}/scripts/finance.py add-category "<name>" <budget> <type>` |
| "remove category" + name | `exec python3 {baseDir}/scripts/finance.py remove-category "<name>"` |
| "rules", "reglas" | `exec python3 {baseDir}/scripts/finance.py list-rules` |
| "add rule" + pattern + category | `exec python3 {baseDir}/scripts/finance.py add-rule "<pattern>" "<category>"` |
| "balance" + account + amount | `exec python3 {baseDir}/scripts/finance.py update-balance "<account>" <amount>` |
| "payment check", "payments due" | `exec python3 {baseDir}/scripts/finance.py payment-check` |
| "savings", "savings goals", "metas de ahorro" | `exec python3 {baseDir}/scripts/finance.py savings-goals` |
| "add savings goal" + details | `exec python3 {baseDir}/scripts/finance.py add-savings-goal "<name>" <target> "<deadline>"` |
| "repair sheet" | `exec python3 {baseDir}/scripts/finance.py repair-sheet` |
| "reconnect sheets" | `exec python3 {baseDir}/scripts/finance.py reconnect-sheets` |
| "help", "/finance_tracker" | `exec python3 {baseDir}/scripts/finance.py help` |
| "check migrations" | `exec python3 {baseDir}/scripts/finance.py check-migrations` |

### Displaying responses

- If the response contains `_formatted`, show that text to the user.
- If the response contains `_message`, show that text.
- If the response contains `_onboarding`, show the `onboarding_message` field after the main response.
- If the response contains `_budget_alerts`, show each alert message.
- If the response contains `_implicit_confirm` = true, the transaction was auto-logged. Show the `_message` field.
- If `needs_confirmation` = true, show the parsed transaction and ask the user to confirm before logging.
- For receipt photos: save the photo to a temp file path, then pass that path to `add-photo`.

### Handling llm_request responses

If a command returns `llm_request: true`, the AI backend is not available. Process the request yourself:
1. Read `system` and `user` fields from the response
2. Use `llm-task` to get the AI to parse the text
3. Pass the result back: `exec python3 {baseDir}/scripts/finance.py process-llm-response '<json>'`

## Rules

- NEVER decide what to ask the user. The script decides.
- NEVER skip setup steps or reorder them.
- NEVER modify JSON output before showing to user.
- NEVER invent categories, amounts, or merchants. Only relay what the script returns.
- If an error is returned, show it. If `suggested_action` is present, follow it.
- All exec calls use: `python3 {baseDir}/scripts/finance.py <command>`
- The Python state machine controls ALL flow. You only translate between human language and CLI commands.
