# Finance Tracker Handoff — 2026-03-31

## Objetivo
Se intentó dejar el sistema de finance tracker listo para:
- importar statements 2026 (Discover, Chase 5614, Wells checking)
- separar `Transactions` (gasto útil) de `Cashflow_Ledger` (flujo real)
- evitar rate limits de Google Sheets
- clasificar `expense`, `refund`, `income`, `payment`, `transfer`, `interest`, `fees`

## Problemas originales detectados
1. `reconcile.py` escribía fila por fila y abría Google Sheets repetidamente.
   - Resultado: `429 Quota exceeded`.
2. El reconciliador mezclaba gastos con pagos, transfers, income y refunds.
3. Se necesitó crear categorías más claras:
   - `Debt_Interest`
   - `Bank_Fees`
   - `Refunds`
4. Se añadió `Cashflow_Ledger` para llevar balance real de cuenta por movimientos signed.
5. El matching probable sigue siendo débil en algunos casos porque usa amount/date sin suficiente merchant similarity.
6. Wells checking necesitó soporte especial y ejecución forzada como `Wells`.
7. La clasificación por signo/tipo mejoró, pero aún puede requerir limpieza adicional en edge cases.

## Ajustes realizados

### 1) Batch + caching para Google Sheets
Archivo: `scripts/lib/sheets.py`

Se añadieron:
- cache global para cliente, spreadsheet y worksheets
- `append_transactions()` con `append_rows()` por lotes
- `append_reconciliation_rows()` por lotes
- `append_cashflow_rows()` para el nuevo tab `Cashflow_Ledger`

Objetivo: reducir llamadas y evitar 429.

### 2) Nuevas categorías
Se agregaron al sistema:
- `Debt_Interest`
- `Bank_Fees`
- `Refunds`

Afecta:
- `config/budgets.json`
- `scripts/lib/config.py`
- `scripts/lib/parser.py`
- Google Sheets Budget tab (mediante `add_category.sh`)

### 3) Nuevo tab `Cashflow_Ledger`
Se añadió:
- constante `TAB_CASHFLOW = "Cashflow_Ledger"` en `scripts/lib/config.py`
- headers en `finance.py setup-sheets`
- creación manual del tab en Google Sheets

Columnas:
- `date`
- `account`
- `merchant`
- `amount_signed`
- `flow_type`
- `category`
- `subcategory`
- `notes`
- `source`
- `timestamp`
- `month`

### 4) Soporte de clasificación por tipo
Archivo: `scripts/lib/reconcile.py`

Se creó / ajustó `_classify_csv_transaction()` para separar:
- `expense`
- `refund`
- `income`
- `payment`
- `transfer`

Reglas actuales aproximadas:
- créditos positivos:
  - returns / credits => `refund`
  - payroll / deposit / Airbnb payouts / instant payments => `income`
  - bank adjustment => `transfer`
- débitos negativos:
  - payment / epay / thank you => `payment`
  - transfers / zelle to / worldremit / wire / ext trnsfr => `transfer`
  - interest => `Debt_Interest`
  - fees / svc charge / overdraft => `Bank_Fees`
  - lo demás => `expense`

### 5) Preservación de `signed_amount`
En `reconcile.py` se corrigió `unmatched_bank` para preservar:
- `signed_amount`
- `raw_category`
- `raw_type`

Antes se perdía y eso rompía la clasificación final.

### 6) Batch write desde reconcile
En `reconcile.py`:
- antes se hacía `append_transaction()` uno por uno
- ahora se junta una lista y se llama `append_transactions()`
- también se construyen `cashflow_rows` y se mandan a `append_cashflow_rows()`
- reconciliation log también se manda por batch

### 7) Wells checking support
Archivo: `scripts/lib/reconcile.py`

Se añadió:
- `_parse_csv_row_wells(row)`
- `_parse_csv(content, bank)` con branch especial para `Wells`
- `_detect_bank()` intentó detectar Wells, pero el archivo filtrado no siempre cae bien por autodetección

Prácticamente se terminó usando:
- `finance.py reconcile <csv> Wells`

### 8) Resets ejecutados
Se vaciaron y rehicieron headers de:
- `Transactions`
- `Cashflow_Ledger`
- `Reconciliation_Log`

### 9) Estado final observado
Después del último reset + reimport limpio:
- `Transactions`: 305 filas
  - 273 `expense`
  - 32 `refund`
- `Cashflow_Ledger`: 343 filas
  - 273 `expense`
  - 32 `refund`
  - 18 `income`
  - 6 `payment`
  - 14 `transfer`

Esto ya es mucho mejor que el estado intermedio, donde casi todo había quedado como `refund`.

## Cosas que siguen pendientes / sospechosas
1. El matching de `probable_match` sigue generando falsos positivos.
   - Ejemplos vistos:
     - Anthropic vs interest charge
     - wire fee vs anthropic
     - La Dolce Vita vs ChatGPT
2. `matched/probable` debería exigir mejor similitud de merchant.
3. Algunos ajustes finos por recibo (Amazon split, Target split, etc.) quedaron parcialmente manuales o pendientes de mejor tooling.
4. `Cashflow_Ledger` y `Transactions` quedaron usables, pero todavía conviene auditar unos cuantos merchants edge-case.

## Archivos incluidos en este handoff ZIP
- `skills/finance-tracker/scripts/finance.py`
- `skills/finance-tracker/scripts/add_category.sh`
- `skills/finance-tracker/scripts/lib/config.py`
- `skills/finance-tracker/scripts/lib/parser.py`
- `skills/finance-tracker/scripts/lib/reconcile.py`
- `skills/finance-tracker/scripts/lib/sheets.py`
- `skills/finance-tracker/config/budgets.json`
- `tmp/finance_tracker_handoff/CHANGES_SUMMARY.md`

## Recomendación para el fix externo
1. corregir `probable_match` / matching score
2. revisar clasificación edge-cases de Wells + Discover + Chase
3. idealmente añadir tests con fixtures de CSV
4. devolver un ZIP listo para reemplazar estos archivos
