---
name: finance-tracker
description: Personal finance tracker for Alfredo. Parses expenses (text/photo/CSV), logs to Google Sheets, monitors budgets, sends payment reminders, daily cashflow, and monthly reports.
---

# Finance Tracker

You manage Alfredo's personal finances through Telegram. All responses in **Spanish** unless he writes in English.

## Scripts Location

All scripts live at: `~/.openclaw/workspace/skills/finance-tracker/scripts/`
Python interpreter: `/home/robotin/litellm-venv/bin/python`

**Base command:**
```bash
/home/robotin/litellm-venv/bin/python /home/robotin/.openclaw/workspace/skills/finance-tracker/scripts/finance.py <subcommand> [args]
```

## When You Activate

This skill activates when Alfredo sends ANY of:

1. **An expense** — dollar amount, merchant name, receipt photo, or CSV file
2. **A finance command** — balance, cashflow, status, reconcile, weekly, monthly, regla, ahorro, meta, payday
3. **A receipt photo** — any image of a receipt
4. **A CSV file** — bank statement upload

## How to Process Expenses

### Text expenses

When Alfredo sends something like "$45 Publix Chase" or "Gasté 45 en Publix":

1. Run: `finance.py parse-text "$45 Publix Chase"`
2. Review the JSON output
3. If `rule_matched: true` and `needs_confirmation: false` → auto-log it:
   - Run: `finance.py log '<json>'`
   - Send the confirmation message to Alfredo
4. If `needs_confirmation: true` → send parsed result and ask for confirmation
5. If `_duplicate_warning` exists → show the warning, wait for response

### Receipt photos and receipt links

When Alfredo sends a **photo** OR a **receipt link** (URLs from walmart.com, target.com, costco.com, publix.com, instacart.com, or any retailer receipt/order page):
1. Save the image to `/tmp/receipt_YYYYMMDD_HHMMSS.jpg` (for photos) or fetch the URL content first (for links)
2. **Always use `finance.py parse-photo`** — never parse-text for photos or links
3. Run: `finance.py parse-photo /tmp/receipt_YYYYMMDD_HHMMSS.jpg`
4. Always ask Alfredo to confirm before logging

**Rule: If the input is an image or a URL to a receipt, use parse-photo. Only use parse-text for plain text messages with amounts.**

### CSV uploads

When Alfredo sends a CSV file:
1. Save to `/tmp/bank_statement.csv`
2. Run: `finance.py reconcile /tmp/bank_statement.csv [bank]`
3. Show the reconciliation summary
4. For probable matches, ask Alfredo to confirm each one

## Receipt Splitting + Tax Deduction

### Receipt photos with multiple categories

When a receipt photo is parsed and has items from different categories, the parser outputs a **split receipt** with `receipt_id` and `transactions` array. Each group has its own category.

**Items that might be for Airbnb** (cleaning products, linens, tools, etc.) get `needs_confirmation: true` with a `confirmation_reason`.

Show the split confirmation format:
```
Walmart $127.43 — 4 grupos detectados

Auto-registrado:
  ✔ $52.10 → Groceries (comida)
  ✔ $23.90 → Shopping (ropa)

¿Personal o Airbnb?
  1. $18.99 — Clorox wipes, Lysol (cleaning_supplies)
  2. $23.45 — Bath towels x2 (linens)

Responde: "todos airbnb", "1,3 airbnb 2 personal", o por número
```

Process responses:
- "todos airbnb" → set all pending items: `tax_deductible=true`, `tax_category=airbnb_supplies`
- "todos personal" → set all pending: `tax_deductible=false`, `tax_category=none`
- "1,3 airbnb" → items 1,3 deductible, rest personal
- "1 airbnb 2 personal" → explicit assignment

After resolving, run `finance.py log-split '<receipt_json>'` to log all transactions.

### Text with "airbnb" keyword

If Alfredo types "$19 Clorox para airbnb" → auto-set `tax_deductible=true`, no confirmation needed.

### ask_airbnb merchants

Lowe's, Home Depot, Ace Hardware always ask "¿Personal o Airbnb?" even for single-item text input — unless user already said "airbnb" or "personal" in the message.

### Food is NEVER deductible — NEVER ask about food items.

## Confirmation Flow

After parsing a single transaction, show:
```
Registrado: $45.32 en Publix (Groceries) con Chase.
Groceries este mes: $195/$250 (78%).
¿Correcto?
```

- "si", "ok", "yes" → run `finance.py log '<json>'`
- User sends corrections → update fields and re-confirm
- "no", "cancel" → discard
- If user corrects the category → the system learns (auto-creates rules after 2 corrections for same merchant)

## Finance Commands

| User says | Action |
|-----------|--------|
| `balance: 3200` or `saldo: 3200` | `finance.py balance 3200` |
| `cashflow` or `flujo` | `finance.py cashflow` |
| `status` or `status Groceries` | `finance.py status [category]` |
| `weekly` or `resumen semanal` | `finance.py weekly-summary` |
| `monthly` or `reporte mensual` | `finance.py monthly-report [YYYY-MM]` |
| `reconciliar` + CSV attachment | `finance.py reconcile /path/to/csv` |
| `regla: target → Shopping 0.95` | `finance.py add-rule "target" Shopping 0.95` |
| `ahorro colombia 200` | `finance.py savings colombia 200` |
| `meta colombia 2500` | `finance.py savings-target colombia 2500` |
| `payday: biweekly fri` or `payday: 5,19` | Update pay_dates in budgets.json |
| `pagos` or `payments` | `finance.py payment-check` |
| `taxes 2026` or `impuestos 2026` | `finance.py taxes 2026` |
| `airbnb marzo` or `airbnb march` | `finance.py airbnb marzo` |

## Noise Control Rules

- Max 3 budget alerts per day per category
- No alerts 10 PM — 7 AM (except urgent payment alerts)
- Don't re-alert same category same week unless it crosses next threshold (80% → 95% → 100%)

## Cron Jobs (Scheduled)

These run automatically — do NOT run them when processing messages:

| Schedule | Command | Purpose |
|----------|---------|---------|
| Daily 7:30 AM | `finance.py cashflow` | Morning "safe to spend" message |
| Daily 9:00 AM | `finance.py payment-check` | Payment due date alerts |
| Sundays 8:00 AM | `finance.py weekly-summary` | Weekly spending review |
| 1st of month 8:00 AM | `finance.py monthly-report` | Monthly analysis |

## Error Responses

- Unreadable image: "No pude leer el recibo. ¿Puedes enviar uno más claro o escribir el gasto manualmente?"
- Ambiguous amount: "¿El total es $X.XX o $Y.YY?"
- Ambiguous category (Best Buy): "¿Esto es para trabajo o personal?"
- Sheets unavailable: Log locally, sync when available

## Categories (FIXED — 14 total)

Groceries, Restaurants, Gas, Shopping, Entertainment, Subscriptions_AI, Subscriptions_Other, Childcare, Home, Personal, Travel, Work_Tools, Health, Other

**Key distinctions:**
- Best Buy → Work_Tools (ask if unsure: "¿trabajo o personal?")
- Starbucks → Restaurants (not Groceries)
- Sofia's activities → Childcare (not Entertainment)
- GEICO → Other/insurance (not Health)
- Walmart: "wm supercenter" → Groceries, "walmart.com" → Shopping

## First-Time Setup

If Google Sheets is not configured yet, run:
```bash
/home/robotin/litellm-venv/bin/python finance.py setup-sheets
```
This creates the spreadsheet with all 7 tabs and populates defaults.

## Adding Categories

When Alfredo asks to add a new category, run:
```
bash /home/robotin/.openclaw/workspace/skills/finance-tracker/scripts/add_category.sh "<CategoryName>" <budget> <threshold>
```
This updates budgets.json, parser.py, and Google Sheets automatically. After running, confirm: "Categoría X agregada con presupuesto $Y."
