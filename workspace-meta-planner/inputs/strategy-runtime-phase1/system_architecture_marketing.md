# SYSTEM ARCHITECTURE — Marketing Multi-Producto
## Documento de Contexto Compartido para el Meta-Workflow Planner
### Fecha: 2026-03-26 | Status: CONGELADO
### Este documento NO es una idea. Es CONTEXTO que acompaña cada idea.

---

## PROPÓSITO DE ESTE DOCUMENTO

Cuando el meta-planner diseña un workflow, necesita saber cómo encaja en el sistema completo. Este documento describe:
- Los 3 workflows operativos y qué hace cada uno
- El runtime que los coordina
- Cómo fluyen los datos entre ellos
- Los manifests y contratos que los conectan
- Las reglas que no se pueden romper

**Instrucción para el meta-planner:** Lee este documento como contexto. No lo implementes — implementa solo la idea específica que te pasen. Pero asegúrate de que tu diseño sea compatible con todo lo descrito aquí.

---

## MAPA DEL SISTEMA COMPLETO

```
                    ┌──────────────────────────────────┐
                    │     RUNTIME / ORCHESTRATOR        │
                    │  Controla dependencias, versiones, │
                    │  gates, invalidación, Telegram     │
                    └──────┬──────────┬──────────┬──────┘
                           │          │          │
              ┌────────────▼──┐  ┌────▼────────┐ │  ┌───────────────────┐
              │  STRATEGY     │  │ MARKETING   │ │  │ GROWTH            │
              │  WORKFLOW     │  │ WEEKLY      │ │  │ INTELLIGENCE      │
              │               │  │ WORKFLOW    │ │  │ SYSTEM            │
              │ Una vez por   │  │ Semanal     │ └──► Semanal           │
              │ producto      │  │             │    │ (post-ejecución)  │
              └──────┬────────┘  └──────┬──────┘    └────────┬──────────┘
                     │                  │                     │
                     │    ALIMENTA ►    │    ◄ RETROALIMENTA  │
                     └─────────────────►│◄────────────────────┘
```

### Flujo de datos entre workflows

```
product_brief.json
    │
    ▼
STRATEGY WORKFLOW (una vez)
    │ produce:
    │   market_analysis.json
    │   buyer_persona.json
    │   brand_strategy.json
    │   seo_architecture.json
    │   channel_strategy.json
    │   strategy_manifest.json
    │
    ▼ alimenta ──────────────────────────────────────────┐
MARKETING WEEKLY WORKFLOW (semanal)                       │
    │ consume:                                            │
    │   buyer_persona.json (quién es el cliente)          │
    │   brand_strategy.json (tono, voz, claims)           │
    │   channel_strategy.json (dónde publicar)            │
    │   optimization_actions.json (qué mejorar)           │
    │   knowledge_base_marketing.json (qué funciona)      │
    │ produce:                                            │
    │   guiones, ad copy, emails, calendario              │
    │   run_manifest.json                                 │
    │                                                     │
    ▼ produce resultados                                  │
GROWTH INTELLIGENCE SYSTEM (semanal, post-ejecución)      │
    │ consume:                                            │
    │   metrics_input.json (métricas de la semana)        │
    │   run outputs (qué se publicó)                      │
    │   knowledge_base_marketing.json (historial)         │
    │   buyer_persona.json (para diagnosticar)            │
    │ produce:                                            │
    │   optimization_actions.json ──► Marketing Weekly ───┘
    │   knowledge_base_marketing.json (append)
    │   strategy_alert.json ──► Runtime
    │
    ▼ si alerta estratégica
RUNTIME decide:
    soft_invalid → Telegram → humano decide
    hard_invalid → bloquea marketing → fuerza Strategy re-run
```

---

## LOS 3 WORKFLOWS

### Workflow 1: Strategy (una vez por producto)
- **Trigger:** Producto nuevo, o estrategia invalidada
- **Input:** product_brief.json
- **Output:** 5 JSON estratégicos + strategy_manifest.json
- **Agentes:** Investigación de mercado (web search), buyer persona, propuesta de valor, SEO, canales
- **Gates:** S1 (buyer persona ok?), S2 (estrategia completa ok?)
- **Costo:** <$2 por ejecución
- **Documento de diseño:** `idea_estrategia_fundacional_con_runtime.md`

### Workflow 2: Marketing Weekly (semanal)
- **Trigger:** Cron semanal o comando manual
- **Input:** weekly_case_brief.json + 5 JSON estratégicos + optimization_actions + knowledge_base
- **Output:** Guiones, ad copy, emails, calendario, quality reports
- **Agentes:** script_generator (Sonnet), ad_copy_generator (Sonnet), email_generator (Sonnet), calendar_generator (GPT-5 Mini), semantic_quality_reviewer (GPT-5 Mini)
- **Gates:** M1 (scripts), M2 (ads+emails), M3 (calendario)
- **Costo:** ~$0.09/run
- **Estado:** Ya diseñado por meta-planner (marketing-workflow-1, NEEDS_REVISION con 13 items)

### Workflow 3: Growth Intelligence (semanal, post-ejecución)
- **Trigger:** Después de que Marketing Weekly complete y se tengan métricas
- **Input:** metrics_input.json + run outputs + knowledge_base + strategy files
- **Output:** performance_report, diagnosis, optimization_actions, experiments_log updates, KB updates, strategy_alert si aplica
- **Componentes:** metrics_calculator (script), Metrics Interpreter (GPT-5 Mini), Diagnosis Agent (Sonnet), Learning Extractor (GPT-5 Mini), experiment_manager (script), pattern_promoter (script)
- **Gates:** Humano aprueba acciones, experimentos, promociones de patterns
- **Costo:** ~$0.042/run
- **Documento de diseño:** `growth_intelligence_system_v2.1_frozen.md`

---

## RUNTIME / ORCHESTRATOR

El runtime es un script central que coordina los 3 workflows. No es un workflow — es infraestructura.

### Responsabilidades
- Verificar si existe estrategia válida y aprobada antes de correr marketing
- Fijar version de estrategia al inicio de cada run semanal (version pinning)
- Leer strategy_alerts y actualizar product_manifest
- Gestionar invalidación hard/soft
- Enviar notificaciones y gates por Telegram
- Permitir reanudar desde estado persistido

### Regla no negociable
**Marketing no corre sin estrategia válida.** Si falta cualquiera de los 5 JSON estratégicos, si la estrategia no está aprobada, o si está hard_invalid → marketing bloqueado.

### Lógica de ejecución
```
Caso A — Producto nuevo (no existe estrategia)
  → Runtime lanza Strategy Workflow
  → Gate S1/S2 → humano aprueba
  → Actualiza product_manifest.json
  → Marketing puede correr

Caso B — Producto con estrategia válida
  → Runtime verifica: aprobada + válida
  → Fija strategy_version_used en run_manifest
  → Lanza Marketing Weekly
  → Después de marketing: lanza Growth (cuando humano ingresa métricas)

Caso C — Estrategia invalidada
  → hard_invalid: marketing bloqueado, Telegram notifica
  → soft_invalid: Telegram pregunta, humano decide
```

---

## SISTEMA DE MANIFESTS

### 3 niveles de manifests

| Manifest | Scope | Quién lo escribe | Qué contiene |
|----------|-------|------------------|--------------|
| `product_manifest.json` | Por producto | Runtime | Estrategia activa, versión, validity, files |
| `strategy_manifest.json` | Por versión de estrategia | Strategy Workflow | Hash del brief, outputs, reglas de invalidación |
| `run_manifest.json` | Por ejecución semanal | Marketing orchestrator | Strategy version pinned, status, gates, outputs |
| `growth_run_manifest.json` | Por ejecución de Growth | Growth system | Marketing run analizado, outputs, cost |

### Version pinning
Cuando un run semanal arranca, queda fijado a una versión de estrategia. Si aparece v3 mientras corre W14, W14 sigue con v2. Inmutable una vez iniciado.

---

## INVALIDACIÓN DE ESTRATEGIA

### Hard invalid (bloquea marketing)
- Cambio de precio >20%
- Cambio de buyer persona / target audience
- Cambio de país o idioma
- Cambio de posicionamiento / propuesta de valor

### Soft invalid (Telegram pregunta, humano decide)
- Ventas caen >30%
- CPA insostenible 2+ semanas
- Engagement cae persistentemente
- Estrategia tiene >90 días
- Growth emite strategy_alert con cooldown cumplido

---

## ESTRUCTURA DE DIRECTORIOS

```
~/.openclaw/products/
├── misterio-semanal/
│   ├── product_brief.json                  ← input del usuario
│   ├── product_manifest.json               ← contrato maestro (Runtime)
│   ├── knowledge_base_marketing.json       ← PERSISTENTE (Growth append)
│   ├── experiments_log.json                ← PERSISTENTE (Experiment Manager)
│   ├── metrics_model.json                  ← PERSISTENTE (setup manual)
│   ├── strategies/
│   │   ├── v1/
│   │   │   ├── strategy_manifest.json
│   │   │   ├── market_analysis.json
│   │   │   ├── buyer_persona.json
│   │   │   ├── brand_strategy.json
│   │   │   ├── seo_architecture.json
│   │   │   └── channel_strategy.json
│   │   └── v2/
│   │       └── ...
│   ├── weekly_runs/
│   │   └── 2026-W14/
│   │       ├── run_manifest.json           ← Marketing run
│   │       ├── weekly_case_brief.json      ← briefing del caso
│   │       ├── drafts/                     ← outputs de Marketing
│   │       ├── approved/                   ← post human gate
│   │       ├── reports/
│   │       └── growth/                     ← outputs de Growth
│   │           ├── metrics_input.json
│   │           ├── calculated_metrics.json
│   │           ├── performance_report.json
│   │           ├── diagnosis.json
│   │           ├── optimization_actions.json
│   │           ├── growth_run_manifest.json
│   │           └── strategy_alert.json     ← solo si aplica
│   └── runtime/
│       ├── runtime_state.json
│       └── invalidation_log.json
└── velas-artesanales/                      ← otro producto, misma estructura
    └── ...
```

---

## ARTEFACTOS QUE FLUYEN ENTRE WORKFLOWS

### Strategy → Marketing
| Artefacto | Productor | Consumidor | Cómo se usa |
|-----------|-----------|------------|-------------|
| buyer_persona.json | Strategy | script_generator, ad_copy_generator, email_generator | Define a quién le hablas |
| brand_strategy.json | Strategy | Todos los agentes de contenido | Define tono, voz, claims |
| channel_strategy.json | Strategy | calendar_generator, orchestrator | Define dónde y cuándo publicar |
| seo_architecture.json | Strategy | blog_writer (Standard) | Keywords y estructura SEO |

### Growth → Marketing
| Artefacto | Productor | Consumidor | Cómo se usa |
|-----------|-----------|------------|-------------|
| optimization_actions.json | Growth Diagnosis Agent | Marketing orchestrator | Inyectado como contexto en prompts |
| knowledge_base_marketing.json | Growth Learning Extractor | Agentes de contenido | Patterns confirmed = usar, tentative = sugerir |

### Growth → Runtime → Strategy
| Artefacto | Productor | Consumidor | Cómo se usa |
|-----------|-----------|------------|-------------|
| strategy_alert.json | Growth evaluador | Runtime | soft/hard invalidation → Telegram → humano decide |

---

## TELEGRAM — COMANDOS UNIFICADOS (v1)

```
# Strategy
/strategy status <product_id>
/strategy run <product_id>
/strategy approve <product_id>

# Marketing
/marketing run <product_id>
/marketing approve <run_id>

# Growth
/growth run <product_id> <week>
/growth approve <week>
/growth adjust <week>
/growth escalate <week>

# Knowledge Base
/kb confirm <pattern_id>
/kb reject <pattern_id>

# Metrics (auxiliar)
/metrics <product_id> spend=X clicks=X conversions=X revenue=X

# Runtime
/product status <product_id>
/invalidate strategy <product_id> <reason>
```

---

## COSTOS MENSUALES DEL SISTEMA COMPLETO

| Componente | Frecuencia | Costo/ejecución | Mensual |
|-----------|-----------|-----------------|---------|
| Strategy Workflow | ~1 vez/trimestre | ~$2.00 | ~$0.67 |
| Marketing Weekly | 4 veces/mes | ~$0.09 | ~$0.36 |
| Growth Intelligence | 4 veces/mes | ~$0.042 | ~$0.17 |
| Runtime scripts | Continuo | $0 | $0 |
| **TOTAL** | | | **~$1.20/mes** |

Bien dentro del presupuesto de $50/mes.

---

## CONTRACT FREEZE — Nombres canónicos, ownership y estados válidos

### Ownership por archivo (quién crea, quién lee, quién modifica)

| Archivo | Creado por | Leído por | Modificado por | Tipo |
|---------|-----------|-----------|----------------|------|
| `product_brief.json` | Humano | Strategy, Runtime | Humano | Per-product, manual |
| `product_manifest.json` | Runtime | Todos | Runtime | Per-product, auto |
| `strategy_manifest.json` | Strategy Workflow | Runtime, Marketing | Strategy Workflow | Per-version, auto |
| `market_analysis.json` | Strategy Workflow | Marketing, Growth | Nunca (inmutable por versión) | Per-version |
| `buyer_persona.json` | Strategy Workflow | Marketing, Growth | Nunca (inmutable por versión) | Per-version |
| `brand_strategy.json` | Strategy Workflow | Marketing, Growth | Nunca (inmutable por versión) | Per-version |
| `seo_architecture.json` | Strategy Workflow | Marketing | Nunca (inmutable por versión) | Per-version |
| `channel_strategy.json` | Strategy Workflow | Marketing, Growth | Nunca (inmutable por versión) | Per-version |
| `weekly_case_brief.json` | Humano | Marketing | Humano | Per-run |
| `run_manifest.json` | Marketing orchestrator | Growth, Runtime | Marketing orchestrator | Per-run |
| `metrics_input.json` | Humano | Growth | Humano | Per-run |
| `calculated_metrics.json` | metrics_calculator.py | Growth agents | Nunca (inmutable por run) | Per-run |
| `performance_report.json` | Metrics Interpreter | Humano, Telegram | Nunca | Per-run |
| `diagnosis.json` | Diagnosis Agent | Growth scripts, Telegram | Nunca | Per-run |
| `optimization_actions.json` | Diagnosis Agent | Marketing orchestrator | Nunca (humano aprueba/rechaza, no edita) | Per-run |
| `growth_run_manifest.json` | Growth scripts | Runtime | Growth scripts | Per-run |
| `strategy_alert.json` | Growth evaluador | Runtime | Runtime (cooldown tracking) | Per-run, condicional |
| `knowledge_base_marketing.json` | Learning Extractor (append) | Marketing agents, Diagnosis Agent | Pattern Promoter (status) | Per-product, PERSISTENTE |
| `experiments_log.json` | Experiment Manager | Diagnosis Agent, Telegram | Experiment Manager | Per-product, PERSISTENTE |
| `metrics_model.json` | Humano (setup) | metrics_calculator, Diagnosis Agent | Humano | Per-product, PERSISTENTE |
| `runtime_state.json` | Runtime | Runtime | Runtime | Per-product |
| `invalidation_log.json` | Runtime | Humano | Runtime (append) | Per-product |

### Estados válidos (enums canónicos)

**Strategy status:**
`missing` → `generating` → `awaiting_approval` → `approved` → `invalid` → `superseded`

**Strategy validity:**
`valid` | `soft_invalid` | `hard_invalid`

**Marketing run status:**
`blocked_no_strategy` | `blocked_invalid_strategy` | `ready` | `running` | `awaiting_gate_1` | `awaiting_gate_2` | `awaiting_gate_3` | `completed` | `rejected`

**Growth run status:**
`pending_metrics` | `running` | `completed` | `failed`

**Experiment status:**
`proposed` → `running` → `completed` | `cancelled`

**Pattern status:**
`tentative` → `confirmed` → `deprecated`

**Gate decisions:**
`pending` | `approved` | `rejected` | `adjust`

### Nombres canónicos de directorios (no inventar otros)

```
~/.openclaw/products/<product_id>/
├── product_brief.json
├── product_manifest.json
├── knowledge_base_marketing.json
├── experiments_log.json
├── metrics_model.json
├── strategies/v<N>/
│   ├── strategy_manifest.json
│   ├── market_analysis.json
│   ├── buyer_persona.json
│   ├── brand_strategy.json
│   ├── seo_architecture.json
│   └── channel_strategy.json
├── weekly_runs/<YYYY-WNN>/
│   ├── run_manifest.json
│   ├── weekly_case_brief.json
│   ├── drafts/
│   ├── approved/
│   ├── reports/
│   └── growth/
│       ├── metrics_input.json
│       ├── calculated_metrics.json
│       ├── performance_report.json
│       ├── diagnosis.json
│       ├── optimization_actions.json
│       ├── growth_run_manifest.json
│       └── strategy_alert.json
└── runtime/
    ├── runtime_state.json
    └── invalidation_log.json
```

---

## ORDEN DE IMPLEMENTACIÓN (aprobado por GPT + Claude)

```
PASO 0:   Implementar upgrade v3.1 del meta-planner (gates, debate, report generator)
PASO 0.5: Congelar contratos globales (este documento — ya hecho)
PASO 1:   Correr meta-planner para Strategy + Runtime (deep)
PASO 2:   Correr meta-planner para Growth Intelligence (deep)
PASO 3:   Resolver 13 NEEDS_REVISION de Marketing + reconciliar ownership con Growth
PASO 3.5: Integration audit de manifests, estados, gates y outputs entre los 3 diseños
PASO 4A:  Implementar Runtime mínimo (manifests, preflight, bloqueo, Telegram, version pinning)
PASO 4B:  Implementar Strategy Workflow (5 JSON estratégicos, gates S1/S2, product_manifest)
PASO 4C:  Implementar Marketing Weekly (corregido, lee estrategia, usa run_manifest)
PASO 4D:  Implementar Growth Intelligence (métricas, diagnosis, KB, experiments, alerts)
PASO 5:   Test end-to-end con 1 producto y 1 semana
```

**Nota técnica:** Para corridas del planner con archivos grandes, NO usar `bash start_plan.sh slug "$(cat archivo.md)" deep`. Usar un wrapper file-based que copie el markdown al run como `raw_idea.md` y lo lea desde ahí.

---

## REGLAS NO NEGOCIABLES

1. **Marketing no corre sin estrategia válida y aprobada**
2. **Version pinning:** run semanal fija versión de estrategia al inicio, inmutable
3. **Growth no ejecuta:** diagnostica, propone, alerta. Humano decide.
4. **Artefactos persistentes no se regeneran:** KB, experiments_log, metrics_model son append/update only
5. **Promoción de patterns nunca automática** en v1: propuesta + validación determinística + human gate
6. **Cooldown en alertas estratégicas:** no re-alertar antes de 14 días salvo hard_invalid
7. **JSON como fuente principal de métricas:** Telegram es auxiliar
8. **Cada workflow tiene su propio bot de Telegram** pero comparten el directorio de producto
9. **Scripts determinísticos para cálculos:** LLMs interpretan y diagnostican, no calculan
