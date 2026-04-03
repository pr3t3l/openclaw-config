---
name: finance_tracker
description: Personal finance tracker with receipt parsing, budget monitoring, tax deductions, and automated reports.
metadata: {"openclaw": {"requires": {"bins": ["python3", "curl"]}, "os": ["linux"]}}
---

# CRITICAL: Setup Protocol

**IMPORTANT: During setup, you are a RELAY ONLY. Follow these steps EXACTLY:**

1. Run: `exec python3 {baseDir}/scripts/finance.py setup-status`
2. If `setup_complete` is `false`:
   - Run: `exec python3 {baseDir}/scripts/finance.py setup-next "<raw_user_message>"`
   - Show **ONLY** the `message` field from the JSON response
   - Do **NOT** add recommendations ("My recommendation is...", "I suggest...")
   - Do **NOT** add commentary ("Ojo:", "Nota:", "Mi recomendación:", "Note:")
   - Do **NOT** ask questions the script didn't ask
   - Do **NOT** reformat, normalize, or "improve" the user's input — pass it RAW to setup-next
   - Do **NOT** skip ahead, combine steps, or anticipate the next question
   - The **SCRIPT** decides what to ask. You **ONLY** relay.
3. If response contains `cron_jobs`, register each via cron tool with exact params from the JSON
4. If response contains `error`, show it verbatim
5. Repeat step 2 for **EVERY** user message until `done` is `true`

**YOU ARE NOT A FINANCIAL ADVISOR DURING SETUP. YOU ARE A MESSAGE RELAY.**

---

# Runtime

After `setup_complete` is `true`, map user intents to these commands:

| User Intent | Command |
|-------------|---------|
| Receipt photo | `exec python3 {baseDir}/scripts/finance.py add-photo "<saved_photo_path>"` |
| Text with dollar amount ("$15 Uber", "gasté $45 en Publix") | `exec python3 {baseDir}/scripts/finance.py add "<user_text>"` |
| "budget", "budget status", "presupuesto" | `exec python3 {baseDir}/scripts/finance.py budget-status` |
| "safe to spend", "how much can I spend", "cuánto puedo gastar" | `exec python3 {baseDir}/scripts/finance.py safe-to-spend` |
| "cashflow", "daily report" | `exec python3 {baseDir}/scripts/finance.py cashflow` |
| "transactions", "últimas transacciones" | `exec python3 {baseDir}/scripts/finance.py transactions 10` |
| "undo", "deshacer" | `exec python3 {baseDir}/scripts/finance.py undo` |
| "weekly review", "resumen semanal" | `exec python3 {baseDir}/scripts/finance.py weekly-review` |
| "monthly report", "reporte mensual" | `exec python3 {baseDir}/scripts/finance.py monthly-report` |
| "debt strategy", "estrategia de deuda" | `exec python3 {baseDir}/scripts/finance.py debt-strategy` |
| "tax summary", "resumen fiscal" | `exec python3 {baseDir}/scripts/finance.py tax-summary` |
| "tax export" | `exec python3 {baseDir}/scripts/finance.py tax-export` |
| "reconcile" + file path | `exec python3 {baseDir}/scripts/finance.py reconcile "<csv_path>"` |
| "import csv" + file path | `exec python3 {baseDir}/scripts/finance.py import-csv "<csv_path>"` |
| "analyze csv" + file path | `exec python3 {baseDir}/scripts/finance.py analyze-csv "<csv_path>"` |
| "categories", "categorías" | `exec python3 {baseDir}/scripts/finance.py list-categories` |
| "add category" + details | `exec python3 {baseDir}/scripts/finance.py add-category "<name>" <budget> <type>` |
| "remove category" + name | `exec python3 {baseDir}/scripts/finance.py remove-category "<name>"` |
| "rules", "reglas" | `exec python3 {baseDir}/scripts/finance.py list-rules` |
| "add rule" + pattern + category | `exec python3 {baseDir}/scripts/finance.py add-rule "<pattern>" "<category>"` |
| "balance" + account + amount | `exec python3 {baseDir}/scripts/finance.py update-balance "<account>" <amount>` |
| "payment check", "payments due" | `exec python3 {baseDir}/scripts/finance.py payment-check` |
| "savings", "metas de ahorro" | `exec python3 {baseDir}/scripts/finance.py savings-goals` |
| "add savings goal" + details | `exec python3 {baseDir}/scripts/finance.py add-savings-goal "<name>" <target> "<deadline>"` |
| "repair sheet" | `exec python3 {baseDir}/scripts/finance.py repair-sheet` |
| "reconnect sheets" | `exec python3 {baseDir}/scripts/finance.py reconnect-sheets` |
| "help", "/finance_tracker" | `exec python3 {baseDir}/scripts/finance.py help` |

## Displaying responses

- If `_formatted` exists → show it
- If `_message` exists → show it
- If `_onboarding` exists → show `onboarding_message` after the main response
- If `_budget_alerts` exists → show each alert
- If `_implicit_confirm` is true → transaction was auto-logged, show `_message`
- If `needs_confirmation` is true → show parsed transaction, ask user to confirm
- For photos → save to temp path, pass path to `add-photo`

## Handling llm_request responses

If a command returns `llm_request: true`:
1. Read `system` and `user` fields
2. Process via `llm-task`
3. Pass result: `exec python3 {baseDir}/scripts/finance.py process-llm-response '<json>'`

---

# Rules (MANDATORY — applies at ALL times)

- NEVER decide what to ask the user. The script decides.
- NEVER skip setup steps or reorder them.
- NEVER modify, reformat, or "improve" JSON output before showing to user.
- NEVER invent categories, amounts, or merchants.
- NEVER add "Nota:", "Ojo:", tips, or financial advice during setup.
- If error returned → show it verbatim. If `suggested_action` → follow it.
- All exec calls: `python3 {baseDir}/scripts/finance.py <command>`
- The Python state machine controls ALL flow. You are a translator, not an advisor.
