2. PRINCIPIO ARQUITECTÓNICO: TRES CAPAS SEPARADAS
Capa de Interacción (el LLM + Telegram): Recibe texto/fotos del usuario, muestra mensajes formateados. No toma decisiones de flujo. No sabe qué paso viene después. Solo pasa mensajes entre el usuario y el engine.
Capa de Orquestación (Python state machine): Controla qué paso es el actual, qué pregunta hacer, cómo validar la respuesta, a dónde transicionar. Es 100% determinista. No importa si el agente es GPT, Sonnet, Gemini o M2.7 — el Python es el mismo.
Capa de Ejecución (Python CLI + APIs): Escribe en Google Sheets, registra cron jobs, envía telemetría, parsea CSVs, procesa recibos. Efectos laterales reales, controlados por la capa de orquestación.
La regla de oro es: el LLM nunca decide flujo, solo traduce lenguaje natural a datos estructurados. Cada vez que el LLM necesita actuar, lo hace a través de exec llamando a finance.py con un subcomando específico. El script retorna JSON con el mensaje a mostrar y el próximo estado. El LLM muestra ese mensaje al usuario. Fin.

3. FLOW COMPLETO DEL SETUP (STATE MACHINE)
UNPACK
  → PREFLIGHT
    → DETECT_CONTEXT
      → INCOME_COLLECT (loop)
        → INCOME_CONFIRM
          → BUSINESS_RULES_MAP
            → BUSINESS_RULES_CONFIRM
              → DEBT_COLLECT (loop)
                → DEBT_CONFIRM
                  → BUDGET_PRESENT
                    → BUDGET_COLLECT (loop)
                      → BUDGET_CONFIRM
                        → BILLS_COLLECT_OR_SKIP
                          → REVIEW_ALL
                            → SHEETS_CREATE
                              → CRONS_SETUP
                                → TELEMETRY_OPT
                                  → ONBOARDING_MISSIONS
                                    → COMPLETE
Cada estado escribe config/setup_state.json con su resultado antes de transicionar. Si el proceso se interrumpe en cualquier punto, finance.py setup-next lee el state file y retoma exactamente donde quedó. No hay pérdida de datos, no hay reinicio.
3.1 — UNPACK
Este paso lo ejecuta el agente cuando el usuario envía el ZIP o clona el repo. El SKILL.md instruye al agente a descomprimir en {workspace}/skills/finance-tracker/ y ejecutar:
bashpython3 {baseDir}/scripts/finance.py install-check
Este comando verifica la estructura del ZIP: que SKILL.md existe, que scripts/finance.py existe, que config/ tiene los archivos esperados. Si algo falta, retorna un error tipado (INSTALL_CORRUPT, MISSING_FILE:rules.base.json) y no continúa. También ejecuta chmod +x en los scripts necesarios, porque unzip en WSL no preserva permisos de ejecución.
3.2 — PREFLIGHT
Este es el guardrail más importante. No se hace una sola pregunta al usuario hasta que este paso pase completamente.
bashpython3 {baseDir}/scripts/finance.py preflight
El preflight verifica, en orden:
¿Existe gog (Google Sheets OAuth)? El script busca si el skill gog está disponible y si hay credenciales válidas. Si no existe → el setup se DETIENE. No hay modo degradado. El mensaje al usuario es: "Google Sheets access is required. Please set up the GOG skill first: https://docs.openclaw.ai/tools/gog — then come back and say 'continue setup'." Esto es una decisión de diseño firme: sin Sheets, no hay producto.
¿Está exec disponible? Si el agente tiene tools.deny: ["exec"] o un perfil restrictivo, nada funciona. El preflight lo verifica intentando ejecutar un comando trivial. Si falla → error EXEC_DENIED con instrucciones para el usuario.
¿Están las dependencias de Python? El script hace import gspread; import google.auth y otros imports críticos. Si falta algo, ejecuta pip install --break-system-packages -r {baseDir}/requirements.txt automáticamente. Si eso también falla → error DEPS_INSTALL_FAILED.
¿Hay un setup previo? Si setup_state.json ya existe con estado COMPLETE, el usuario ya instaló. El script pregunta si quiere reinstalar o mantener. Si existe con un estado intermedio, le ofrece continuar donde quedó.
¿Hay una versión anterior? Si VERSION en el filesystem es menor que la del ZIP, activa el sistema de migraciones en lugar del setup fresh.
Cada check que falla produce un error con código tipado:
json{
  "error_code": "AUTH_GOOGLE_MISSING",
  "stage": "PREFLIGHT",
  "recoverable": true,
  "message": "Google Sheets access not found. Set up GOG skill first.",
  "action_url": "https://docs.openclaw.ai/tools/gog"
}
```

### 3.3 — DETECT_CONTEXT

Aquí el sistema reutiliza lo que OpenClaw ya sabe. No le pregunta al usuario su nombre, idioma, timezone, ni configuración de Telegram.

El script lee:
- `USER.md` del workspace → nombre, idioma preferido
- `IDENTITY.md` → nombre del agente, personalidad
- `openclaw.json` → modelo default del agente, timezone (`agents.defaults.userTimezone`), agentId
- Canal de Telegram activo → se infiere del contexto de la sesión (no se pide chat_id)

Todo lo encontrado se guarda en `setup_state.json` bajo la key `context`. Lo que no se encuentre se marca como `null` y el sistema funciona con defaults razonables (English, UTC, etc.) sin preguntar.

### 3.4 — INCOME_COLLECT (loop interactivo)

El engine envía al usuario:
```
Step 1 of 8 — Income Sources
Tell me your income sources one at a time.
For each, include: amount, frequency (weekly/biweekly/monthly),
type (salary/freelance/rental/business/other),
and which account receives it.

Say 'done' when finished.
You can also say 'undo' to remove the last one, or 'list' to see what you've entered.
Cada mensaje del usuario llega a:
bashpython3 {baseDir}/scripts/finance.py setup-next "I have salary $3000 biweekly on my personal checking"
El script usa el LLM (vía el modelo default del agente, a través de OpenClaw llm-task o via exec con curl a LiteLLM) para parsear el texto libre a JSON:
json{
  "amount": 3000,
  "currency": "USD",
  "frequency": "biweekly",
  "source_type": "salary",
  "account_label": "personal checking",
  "is_regular": true
}
Después del parsing, Python valida contra un JSON schema (install/schemas/income.v1.json). Si falta un campo — digamos que el usuario dijo "I make 3k freelancing" sin mencionar la frecuencia — el engine no avanza al siguiente income. Pregunta solo lo que falta: "How often do you receive this income? (weekly/biweekly/monthly/irregular)."
El detection de "done" NO depende del LLM. Es un check en Python antes de llamar al AI:
pythonDONE_SIGNALS = [
    "done", "that's it", "that's all", "finished", "listo",
    "terminé", "ya", "eso es todo", "no more", "nothing else",
    "nada más", "ya terminé", "end", "stop"
]
if user_input.strip().lower() in DONE_SIGNALS:
    transition_to("INCOME_CONFIRM")
```

Igualmente para "undo", "list", "edit N" — son comandos que el Python intercepta antes de que el LLM los toque.

**Manejo de ingresos irregulares:** Si el `source_type` es freelance, rental, o business, el engine automáticamente marca `is_regular: false` y pregunta: "What's your average monthly income from this source?" Esto es crucial para el cashflow calculator posterior, que no puede asumir "next payday" para ingresos irregulares. En lugar de eso, usará un promedio móvil.

### 3.5 — INCOME_CONFIRM

El engine muestra un resumen formateado de todos los ingresos colectados:
```
Income Summary:
1. Salary — $3,000 biweekly → Personal Checking (regular)
2. Airbnb — ~$800/month → Business Account (irregular)

Total estimated monthly: $7,300
Is this correct? (yes/edit N/add more)
```

Solo avanza cuando el usuario confirma explícitamente.

### 3.6 — BUSINESS_RULES_MAP

Aquí es donde las tres respuestas (Claude, GPT, Gemini) convergieron en lo mismo: **no dejes que el LLM invente reglas fiscales.**

El sistema trae rule packs pre-compilados y versionados en el ZIP:
```
install/rulepacks/
  us-personal.v1.json
  us-rental-property.v1.json
  us-freelance.v1.json
  us-small-business.v1.json
Cada rule pack contiene categorías de gastos deducibles para ese tipo de negocio, con explicaciones cortas y la referencia del IRS:
json{
  "rulepack_id": "us-rental-property.v1",
  "jurisdiction": "US",
  "business_type": "rental_property",
  "deductible_categories": [
    {
      "category": "cleaning_supplies",
      "irs_reference": "Schedule E Line 7",
      "description": "Cleaning products, trash bags, detergent for rental",
      "keywords": ["cleaning", "bleach", "mop", "broom", "trash bag", "windex"]
    },
    {
      "category": "maintenance_repair",
      "irs_reference": "Schedule E Line 14",
      "description": "Repairs and maintenance for rental property"
    }
  ]
}
```

El engine analiza los `source_type` colectados en el paso anterior. Si hay un "rental" → carga `us-rental-property.v1.json`. Si hay un "freelance" → carga `us-freelance.v1.json`. Si hay ambos, carga ambos. El mapeo es determinista, no requiere LLM.

El sistema muestra al usuario:
```
Based on your Airbnb rental income, I found these deductible expense categories:
- Cleaning supplies (Schedule E Line 7)
- Maintenance & repairs (Schedule E Line 14)
- Insurance (Schedule E Line 9)
- Utilities — prorated (Schedule E Line 17)
- Linens & supplies (Schedule E Line 7)
- Professional services (Schedule E Line 17)

I'll create tracking rules for these. OK? (yes/edit)
```

Si el usuario quiere agregar o quitar categorías deducibles, esos cambios van a `rules.user.json` (overlay), nunca modifican el rule pack original. Esto permite que cuando publiques `us-rental-property.v2.json`, el update no pise las customizaciones del usuario.

**¿Y para otros países?** v2.0 solo trae US. La estructura está lista para `mx-rental-property.v1.json`, `co-freelance.v1.json`, etc. En el setup, el país se detecta del contexto o se pregunta una vez. Pero no en v2.0.

### 3.7 — DEBT_COLLECT (loop)

Mismo patrón que ingresos:
```
Step 3 of 8 — Debts
List your debts one at a time.
For each: type (credit card/personal loan/auto loan/mortgage/student loan),
current balance, APR, and minimum payment.

Say 'done' when finished. 'undo' to remove last. 'list' to review.
```

Schema validation incluye sanity checks financieros:
- APR > 50%? → "That APR seems very high. Please double-check."
- Balance < 0? → "Balance should be a positive number."
- Min payment > balance? → "Minimum payment can't exceed balance."

Estos no son bloqueos, son warnings. El usuario puede confirmar que sí, su tarjeta tiene 29.99% APR.

### 3.8 — BUDGET_PRESENT + BUDGET_COLLECT

El engine presenta categorías sugeridas basadas en lo que ya sabe. Si el usuario tiene rental income, las categorías de Airbnb ya aparecen. Si tiene auto loan, Transportation ya está.
```
Step 4 of 8 — Monthly Budget
Here are suggested categories. Each is marked (F)ixed or (V)ariable:

FIXED (non-negotiable):
 1. Rent/Mortgage        $___
 2. Utilities            $___
 3. Insurance            $___

VARIABLE (adjustable):
 4. Groceries            $___
 5. Restaurants           $___
 6. Gas                  $___
 7. Shopping             $___
 8. Entertainment        $___
 9. Healthcare           $___
10. Personal Care        $___
11. Subscriptions        $___

Reply: 1. $1500  4. $300  5. $100 ...
To add custom: 'new Pets $200 variable'
Say 'done' when finished.
```

La distinción Fixed vs Variable es nueva y viene del análisis de gaps. ¿Por qué importa? Porque el AI analyst semanal solo debería sugerir optimizaciones en los variables. "Reduce your Entertainment spending" es accionable. "Reduce your Rent" es inútil.

El parsing aquí es mayormente determinista — regex patterns para `N. $amount` y `new Name $amount type`. El LLM solo se usa si el usuario escribe en formato libre que el regex no parsea.

### 3.9 — BILLS_COLLECT_OR_SKIP
```
Step 5 of 8 — Recurring Bills & Subscriptions
Tell me your recurring bills: name, amount, due date, frequency.
Example: "Power $120 due 15th monthly"

OR send a CSV of your last 3-6 months bank statements and I'll detect them automatically.
OR say 'skip' to set this up later.
```

Aquí hay una feature potente que viene del análisis de gaps: **el CSV auto-analyzer.** Si el usuario envía un CSV en lugar de listar bills manualmente, el script:

1. Detecta el formato del banco automáticamente (Chase, Wells Fargo, BoA, Discover, Citi, Amex — cada uno tiene headers distintos)
2. Identifica transacciones recurrentes por patrón (mismo merchant, similar amount, monthly frequency)
3. Detecta ingresos (deposits)
4. Propone un calendario de pagos basado en los datos reales
5. Muestra todo al usuario para confirmación

Esto convierte un setup de 10 minutos en 2 minutos para usuarios que tienen CSVs. Y los datos son mucho más precisos que lo que el usuario recuerda de memoria.

**Sinking funds:** Aquí también se capturan gastos periódicos no mensuales. Si el usuario dice "Car insurance $600 every 6 months" o si el CSV muestra un pago semestral, el sistema calcula la provisión mensual ($100/month) y la descuenta del cashflow disponible. Esto previene la trampa clásica: "Tengo $500 disponibles" → llega el seguro del auto → deuda.

### 3.10 — REVIEW_ALL

Este es un guardrail nuevo que GPT sugirió y es correcto: **no hay efectos laterales antes de la revisión total.**
```
Setup Review — Please confirm everything:

INCOME (2 sources):
  Salary: $3,000 biweekly → Personal Checking
  Airbnb: ~$800/mo → Business Account
  Est. monthly: $7,300

BUSINESS RULES:
  Rental Property (US): 6 deductible categories loaded

DEBTS (3):
  Credit Card 1: $2,300 @ 20% APR, min $65
  Personal Loan: $3,000 @ 12% APR, min $150
  Auto Loan: $8,500 @ 5% APR, min $220

BUDGET: 14 categories, $4,200/month total
  Fixed: $2,100 | Variable: $2,100

BILLS: 8 recurring, $1,850/month

Estimated monthly surplus: $1,250

Confirm all? (yes / edit [section])
El estimated monthly surplus es un sanity check: si es negativo, el system warns que el usuario está gastando más de lo que gana. Si es cero o muy bajo, sugiere revisar.
Solo después del "yes" del usuario se procede a crear el Sheet y los cron jobs.
3.11 — SHEETS_CREATE
Aquí integro el punto fuerte de Gemini que confirmaste: nunca depender de nombres de tabs.
Al crear el Google Sheet, el script guarda los sheetId numéricos (que Google asigna internamente y nunca cambian, aunque el usuario renombre la tab) en un config file:
json{
  "spreadsheet_id": "1RcYf...",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1RcYf...",
  "tabs": {
    "transactions": {"sheet_id": 0, "schema_version": "v1.0"},
    "budget": {"sheet_id": 123456, "schema_version": "v1.0"},
    "payment_calendar": {"sheet_id": 234567, "schema_version": "v1.0"},
    "monthly_summary": {"sheet_id": 345678, "schema_version": "v1.0"},
    "debt_tracker": {"sheet_id": 456789, "schema_version": "v1.0"},
    "rules": {"sheet_id": 567890, "schema_version": "v1.0"},
    "reconciliation_log": {"sheet_id": 678901, "schema_version": "v1.0"},
    "cashflow_ledger": {"sheet_id": 789012, "schema_version": "v1.0"},
    "businesses": {"sheet_id": 890123, "schema_version": "v1.0"},
    "savings_goals": {"sheet_id": 901234, "schema_version": "v1.0"}
  },
  "created_at": "2026-04-02T...",
  "last_validated": "2026-04-02T..."
}
Cada vez que el script escribe al Sheet, primero valida que la estructura esté intacta (columns en el orden esperado, headers correctos). Si el usuario borró una columna o movió cosas, el script tiene dos opciones: auto-repair si es seguro (re-crear un header faltante), o alertar al usuario si el daño es serio ("Column 'amount' is missing from Transactions tab. Run 'repair-sheet' to fix.").
Todas las escrituras del setup inicial van en un solo batch_update para respetar el rate limit de Google (60 req/min). No 8 calls separados — uno solo con todas las tabs, headers, y datos iniciales.
Las tabs nuevas vs v1: businesses (para multi-negocio) y savings_goals (para metas de ahorro). Esto también incluye el campo business_id en cada transacción para poder generar tax summaries por negocio.
3.12 — CRONS_SETUP
Migración completa a OpenClaw native cron. No más setup_crons.sh ni cron_runner.sh con system crontab.
El script registra los jobs vía la API del gateway cron tool:
json[
  {
    "name": "Finance: Daily Cashflow",
    "schedule": {"kind": "cron", "cron": "30 7 * * 1-5", "tz": "America/New_York"},
    "sessionTarget": "isolated",
    "payload": {
      "kind": "agentTurn",
      "message": "Run: python3 {baseDir}/scripts/finance.py cashflow\nShow the result to the user."
    },
    "delivery": {"mode": "announce", "channel": "last"}
  },
  {
    "name": "Finance: Payment Check",
    "schedule": {"kind": "cron", "cron": "0 9 * * *", "tz": "America/New_York"},
    "sessionTarget": "isolated",
    "payload": {
      "kind": "agentTurn",
      "message": "Run: python3 {baseDir}/scripts/finance.py payment-check\nShow the result to the user."
    },
    "delivery": {"mode": "announce", "channel": "last"}
  },
  {
    "name": "Finance: Weekly Review",
    "schedule": {"kind": "cron", "cron": "0 8 * * 0", "tz": "America/New_York"},
    "sessionTarget": "isolated",
    "payload": {
      "kind": "agentTurn",
      "message": "Run: python3 {baseDir}/scripts/finance.py weekly-review\nShow the result to the user."
    },
    "delivery": {"mode": "announce", "channel": "last"}
  },
  {
    "name": "Finance: Monthly Report",
    "schedule": {"kind": "cron", "cron": "0 8 1 * *", "tz": "America/New_York"},
    "sessionTarget": "isolated",
    "payload": {
      "kind": "agentTurn",
      "message": "Run: python3 {baseDir}/scripts/finance.py monthly-report\nShow the result to the user."
    },
    "delivery": {"mode": "announce", "channel": "last"}
  }
]
```

Las ventajas de OpenClaw native cron sobre system crontab son: persiste en `~/.openclaw/cron/jobs.json` (sobrevive reinicios), tiene delivery nativo a Telegram sin necesitar chat_id manual, soporta sessions aisladas que no contaminan el chat principal, y es auditable vía `openclaw cron list`.

El timezone se toma del contexto detectado en DETECT_CONTEXT. No se le pregunta al usuario.

### 3.13 — TELEMETRY_OPT

El mensaje de consentimiento es explícito, sin eufemismos:
```
To improve reliability, we collect anonymous performance data:
✓ App version and installer stage completion/failure
✓ Coarse timing buckets (e.g., "5-15 seconds")
✓ Feature counts (number of categories, rules, income sources)
✓ Standardized error codes
✓ Selected feature flags (language, quick/full setup)

We NEVER collect:
✗ Your name, email, phone, or chat ID
✗ Account names, balances, or transactions
✗ Merchant names or receipt text
✗ Google Sheet URLs or file contents
✗ Any text you type in chat

Allow anonymous telemetry? (yes/no)
El schema de cada evento de telemetría remota:
json{
  "event": "setup_stage_complete",
  "v": "2.0.0",
  "stage": "SHEETS_CREATE",
  "result": "ok",
  "duration_bucket": "15-30s",
  "distribution": "github_zip",
  "rulepack_ids": ["us-rental-property.v1"],
  "income_source_count": 2,
  "debt_count": 3,
  "custom_category_count": 1,
  "cron_job_count": 4,
  "setup_mode": "full",
  "detected_language": "en",
  "error_code": null
}
```

Sin `user_id`, sin `install_id` estable, sin `session_id`, sin IP, sin hashes. Cero trazabilidad. El costo es que no puedes hacer análisis de cohortes ni retención por usuario — pero la prioridad es privacidad radical.

Los logs locales completos (con toda la info de debugging) se guardan en `logs/` en la máquina del usuario. Esos nunca salen.

### 3.14 — ONBOARDING_MISSIONS

Feature nueva que surgió del análisis de gaps. Después de COMPLETE, en lugar de soltar al usuario con una lista de 38 comandos:
```
Setup complete! Your Google Sheet is ready: [link]
4 automated jobs are active.

Let's try 3 quick things to get you started:

Mission 1: Send me a photo of any receipt or type "$15 Uber"
```

Cuando el usuario completa la primera misión:
```
Got it! $15.00 → Transportation (Uber). Logged.

Mission 2: Say "budget status"
```

Cuando completa la segunda:
```
Budget Status:
Groceries: $0/$300 (0%)
Restaurants: $0/$100 (0%)
...

Mission 3: Say "safe to spend"
Tres interacciones de 10 segundos cada una que enseñan los tres use cases principales. Después: "You're all set! Say /finance_tracker anytime for the full command menu."

4. EL SISTEMA DE REGLAS DE DOS NIVELES (MERCHANT + LINE ITEM)
Esto viene de tu observación correcta sobre Walmart/Target/Publix. Un merchant-level rule que diga "Walmart → Groceries" pierde que $15 del receipt eran cleaning supplies para Airbnb (deducibles). El per-line approach que ya diseñaste en v1 es correcto para estos casos.
La solución es un sistema de dos niveles:
Nivel 1 — Merchant Rules (single-category merchants):
Para merchants que siempre caen en una categoría: Uber → Transportation, Netflix → Subscriptions, Starbucks → Restaurants. Estas reglas son locales, se auto-aprenden, y cuestan $0 por transacción.
json{
  "uber": {
    "category": "transportation",
    "requires_line_items": false,
    "confidence": 0.98,
    "times_used": 23,
    "last_used": "2026-04-01"
  },
  "walmart": {
    "category": null,
    "requires_line_items": true,
    "confidence": null,
    "note": "Multi-category merchant — always parse line items"
  }
}
```

Cuando llega una transacción, el flujo es:
```
input → normalize merchant name → lookup merchant_rules.json
  → if requires_line_items: false AND confidence > 0.8:
      auto-categorize, $0, implicit confirm
  → if requires_line_items: true OR unknown merchant:
      parse line items via AI
      for each item: check against business rules for tax deductibility
      confirm with user
      save new merchant rule if single-category
```

**Nivel 2 — Line Item Rules (multi-category merchants):**
Para Walmart, Target, Home Depot, Costco, Publix — merchants que venden de todo. El sistema parsea cada línea del recibo individualmente y asigna categoría + taxable flag per item.
```
Receipt: Walmart $87.43
  Line 1: Great Value Bread $3.49 → Groceries (not deductible)
  Line 2: Clorox Wipes $4.99 → Cleaning Supplies (deductible - Airbnb)
  Line 3: Light Bulbs x3 $8.97 → Maintenance (deductible - Airbnb)
  Line 4: Bananas $1.29 → Groceries (not deductible)
La pregunta de confirmación de Airbnb se hace por batch, no por item: "Items 2 and 3 could be Airbnb deductions. Confirm? (yes/no/select)". Esto reduce la fatiga de confirmación sin perder precisión.
Normalización de merchant names: "UBER *TRIP", "Uber BV", "UBER EATS" → todos normalizan a "uber". El normalizador es Python: lowercase, strip asterisks/suffixes, regex para variaciones conocidas. Un merchant puede tener aliases:
json{
  "uber": {
    "aliases": ["uber *trip", "uber bv", "uber eats", "uber technologies"],
    "category": "transportation"
  }
}
```

**Confirmación implícita (post-setup):** Para el uso diario, la confirmación explícita genera fatiga. Gemini tiene razón. El sistema usa confirmación implícita con undo:
```
"Added: $15.00 → Transportation (Uber). Reply 'undo' within 5 min to revert."
```

Esto solo aplica cuando confidence > 0.8 y el merchant no es multi-category. Para merchants desconocidos o multi-category, sigue siendo confirmación explícita.

---

## 5. SAFE-TO-SPEND (EL NÚMERO MÁS IMPORTANTE)

Esta es la métrica que hace el producto realmente útil. No es solo "cuánto gasté" — es "cuánto puedo gastar HOY sin joderme."
```
safe_to_spend = 
  projected_balance_at_next_income
  - sum(upcoming_bills_before_next_income)
  - sum(minimum_debt_payments_before_next_income)
  - sum(daily_savings_allocations)
  - sum(sinking_fund_provisions)
```

Para ingresos regulares, `projected_balance_at_next_income` es el saldo actual. Para irregulares, es el saldo actual + promedio mensual prorrateado.

El daily cashflow report (7:30 AM weekdays) muestra:
```
Good morning! Here's your financial snapshot:

Safe to spend today: $42
Budget status: 🟢 On track (68% of month used, 71% of budget used)

Upcoming (next 3 days):
  Apr 5: Power bill $120 (auto-pay)
  Apr 6: Credit Card 1 minimum $65

Savings: Vacation Fund — $15/day needed ($340 of $2,000)
```

---

## 6. WEEKLY REVIEW + OPTIMIZATION SUGGESTIONS

El weekly review (domingos 8 AM) tiene dos partes:

**Parte 1 — Lo que pasó la semana anterior:**
```
Week of Mar 24-30:
Spent: $682 across 23 transactions
Top categories: Groceries $210, Restaurants $145, Gas $80
vs Budget: Restaurants at 145% ⚠️, everything else on track
Deductible expenses logged: $89 (cleaning supplies, maintenance)
```

**Parte 2 — Lo que viene la semana siguiente:**
```
Coming up Apr 1-7:
  Apr 1: Rent $1,500 (auto-pay)
  Apr 3: Internet $65
  Apr 5: Power $120
  Total due: $1,685
  Projected balance after bills: $2,340
```

**Parte 3 — Optimization suggestions (AI-generated):**
El AI analyst revisa los patrones y sugiere:
```
Optimization ideas:
1. Restaurant spending is $45 over budget this month.
   You averaged $36/week — reducing to $25/week saves $572/year.
2. You have 3 subscriptions totaling $45/mo under "Subscriptions_Other".
   Consider reviewing if all are still needed.
3. Paying $100 extra/month toward Credit Card 1 (20% APR)
   saves $847 in interest and pays it off 14 months sooner.
Solo sugiere optimizaciones en categorías variable. Nunca sugiere "reduce your rent."

7. DRIFT PROTECTION + RETENTION
Problema real: el usuario empieza motivado, usa el tracker 2 semanas, y luego se olvida. Los datos se vuelven inconsistentes, el presupuesto pierde sentido.
Nudge de inactividad: Si no hay transacciones registradas en 5 días, el cron de daily cashflow incluye: "You haven't logged transactions in 5 days. Want me to help you catch up? Send a CSV or start logging."
Weekly balance reconciliation: Si el usuario acepta (configurable), una vez por semana el sistema pregunta: "Your tracked balance for Personal Checking is $4,532. What's your actual balance?" Si hay discrepancia > $50, el sistema identifica transacciones faltantes y ofrece reconciliar.
Monthly health score: Basado en: % de días con transacciones registradas, % de presupuesto categories con actividad, diferencia entre balance tracked vs reconciled. Esto aparece en el monthly report como motivador, no como castigo.

8. SISTEMA DE ERRORES TIPADOS
Cada error en el sistema tiene un código, un stage, y un flag de recuperabilidad:
json{
  "error_code": "SHEETS_AUTH_EXPIRED",
  "stage": "RUNTIME",
  "recoverable": true,
  "message": "Google Sheets token expired. Run 'reconnect-sheets' to refresh.",
  "suggested_action": "reconnect-sheets"
}
```

Códigos por stage:
```
INSTALL_*:     INSTALL_CORRUPT, INSTALL_MISSING_FILE, INSTALL_PERMISSIONS
PREFLIGHT_*:   AUTH_GOOGLE_MISSING, EXEC_DENIED, DEPS_INSTALL_FAILED, VERSION_MISMATCH
SETUP_*:       PARSE_FAILED, SCHEMA_INVALID, SHEETS_CREATE_FAILED, CRON_REGISTER_FAILED
RUNTIME_*:     SHEETS_AUTH_EXPIRED, SHEETS_SCHEMA_DRIFT, RATE_LIMIT, AI_PARSE_TIMEOUT
RECONCILE_*:   CSV_FORMAT_UNKNOWN, DUPLICATE_DETECTED, BALANCE_MISMATCH
```

Estos códigos se envían en telemetría (si habilitada) y se loguean localmente siempre. Permiten medir fallos reales, priorizar fixes, y automatizar recovery paths.

---

## 9. VERSIONING Y MIGRACIONES

El ZIP contiene un archivo `VERSION` con semver. Cuando el usuario instala una nueva versión sobre una existente, el script detecta la versión actual y ejecuta migraciones secuenciales:
```
migrations/
  001_add_businesses_tab.py
  002_add_savings_goals_tab.py
  003_migrate_rules_schema.py
  004_add_business_id_to_transactions.py
```

Cada migración es idempotente (puede ejecutarse dos veces sin romper). El `setup_state.json` registra qué migraciones ya se aplicaron. Si una migración falla, se detiene y reporta el error sin dejar datos en estado inconsistente.

Las migraciones aplican a: schema de `tracker_config.json`, schema del Google Sheet (nuevas columnas/tabs), y schema de `rules.json`. Los datos del usuario nunca se borran — solo se agregan campos o se reestructuran.

---

## 10. ESTRUCTURA FINAL DEL ZIP
```
finance-tracker/
├── SKILL.md                          ← Router delgado (~150 líneas)
├── VERSION                           ← "2.0.0"
├── requirements.txt                  ← Dependencias Python mínimas
├── install/
│   ├── manifest.json                 ← Versión, checksums, requisitos, changelog
│   ├── schemas/
│   │   ├── income.v1.json
│   │   ├── debt.v1.json
│   │   ├── budget.v1.json
│   │   └── bill.v1.json
│   ├── rulepacks/
│   │   ├── us-personal.v1.json
│   │   ├── us-rental-property.v1.json
│   │   ├── us-freelance.v1.json
│   │   └── us-small-business.v1.json
│   └── migrations/
│       ├── 001_initial.py
│       └── ...
├── config/                            ← Se genera durante setup
│   ├── tracker_config.json           ← Config unificada
│   ├── sheets_config.json            ← sheetIds + schema versions
│   ├── setup_state.json              ← Checkpoint del state machine
│   ├── rules.base.json               ← Del rulepack, read-only
│   ├── rules.user.json               ← Overlays del usuario
│   ├── merchant_rules.json            ← Auto-learned merchant → category
│   └── processed_receipts.json
├── scripts/
│   ├── finance.py                     ← CLI principal (setup + runtime)
│   └── lib/
│       ├── state_machine.py           ← Core: estados, transiciones
│       ├── ai_parser.py              ← LLM calls para texto → JSON
│       ├── sheets.py                  ← Google Sheets via gog (by sheetId)
│       ├── telemetry.py               ← Supabase anonymous events
│       ├── rules.py                   ← Two-tier rule engine
│       ├── merchant_rules.py          ← Auto-learning merchant mapping
│       ├── budget.py                  ← Budget tracking + alerts
│       ├── cashflow.py                ← Safe-to-spend calculator
│       ├── payments.py                ← Payment calendar + sinking funds
│       ├── reconcile.py               ← Bank CSV reconciliation
│       ├── reports.py                 ← Daily/weekly/monthly reports
│       ├── parser.py                  ← Receipt parsing (photo + text)
│       ├── csv_analyzer.py            ← Bank CSV auto-detection + setup
│       ├── debt_optimizer.py          ← Payoff strategy (avalanche/snowball)
│       ├── errors.py                  ← Typed error codes
│       ├── migrations.py              ← Version migration runner
│       └── config.py                  ← Unified config access
├── docs/
│   └── SYSTEM_GUIDE.md
└── templates/
    └── sheet_structure.json           ← Template para crear el Sheet

11. RESUMEN DE DECISIONES TOMADAS
DecisiónValorRazónOrquestación del setupPython state machine, no LLMDeterminismoGoogle Sheets requeridoSí, sin modo degradadoCore del productoGOG no instaladoSTOP + guiar a URLNo hay fallbackCron systemOpenClaw native cronPersistente, delivery nativoMerchant rulesTwo-tier: merchant + line-itemWalmart ≠ UberTax rulesPre-compiled rulepacks, no AI-generatedConsistencia fiscalConfirmación diariaImplícita + undo (high confidence)Anti-fatigaSheet referencesBy sheetId, not tab nameAnti-user-breaksTelemetríaZero PII, zero traceabilityPrivacidad radicalSetup pathQuick (2 min) + Full (10 min)AccesibilidadBudget categoriesFixed vs VariableOptimización realistaIncome typesRegular vs IrregularCashflow accuracy

Listo. Esta es la especificación final con todo consolidado. Cuando quieras empezar a construir, dime y arrancamos con state_machine.py + errors.py como foundation.