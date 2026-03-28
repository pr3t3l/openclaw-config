# IDEA: Sistema de Marketing Multi-Producto — Estrategia Fundacional + Runtime

## Contexto del sistema completo

Este documento describe DOS cosas que el meta-planner debe diseñar juntas:
1. **Strategy Workflow** — genera la base estratégica por producto
2. **Runtime/Orchestrator** — coordina Strategy y Marketing, controla dependencias, versiones y gates

El Marketing Weekly Workflow ya está diseñado (marketing-workflow-1). Este documento completa el sistema.

## Arquitectura de 3 capas

```
CAPA 1: Meta-Planner (diseña workflows — YA EXISTE, NO TOCAR)

CAPA 2: Workflows operativos
  ├── Strategy Workflow (este documento)
  │   Input:  product_brief.json
  │   Output: 5 JSON estratégicos + strategy_manifest.json
  │   Frecuencia: una vez por producto, re-ejecución si se invalida
  │
  └── Marketing Weekly Workflow (YA DISEÑADO — marketing-workflow-1)
      Input:  5 JSON estratégicos + weekly_case_brief.json
      Output: guiones, ads, emails, calendario, quality reports
      Frecuencia: semanal

CAPA 3: Runtime/Orchestrator (este documento)
  Coordina ambos workflows, controla dependencias, versiones,
  invalidación, gates humanos y comunicación por Telegram
```

---

## PARTE 1: Strategy Workflow

### Qué hace
Dado un producto nuevo, investiga y genera toda la base estratégica de marketing. Se ejecuta UNA VEZ por producto (o se re-ejecuta si la estrategia se invalida).

### Fases

#### Fase S1: Análisis del mercado y competencia
- Investigar el mercado usando web search (datos reales, no inventados)
- Cuantificar demanda: volumen de búsquedas, tendencias, tamaño estimado
- Identificar 5-10 competidores con fortalezas/debilidades
- Analizar contenido de competidores (tono, formato, frecuencia, plataformas)
- **Output:** market_analysis.json

#### Fase S2: Buyer Persona y Avatar
- Método PCR (Público, Contexto, Reto)
- Avatar concreto: nombre ficticio, edad, ocupación, rutina, hábitos digitales
- 5-8 puntos de dolor específicos
- 3-5 activadores de compra (momentos receptivos)
- 3-5 barreras de compra (objeciones comunes)
- **Output:** buyer_persona.json

#### Fase S3: Propuesta de Valor y Marca
- CPM: "Ayudo a [cliente ideal] a [logro deseado] a través de [producto] sin [dolor principal]"
- Voz y tono de marca
- Claims permitidos y restricciones legales/éticas
- **Output:** brand_strategy.json

#### Fase S4: Arquitectura SEO
- Keywords agrupadas por intención (informacional, transaccional, mixta)
- Una página/artículo por intención (sin canibalización)
- Long-tail keywords con oportunidad
- **Output:** seo_architecture.json

#### Fase S5: Estrategia de Canales y Funnel
- Canales prioritarios basados en buyer persona
- Funnel 3 etapas: Conciencia → Consideración → Compra
- Lead magnet apropiado
- KPIs objetivo: CPA máximo, CPL objetivo, tasa de conversión esperada
- **Output:** channel_strategy.json

### Human Gates del Strategy Workflow
- **Gate S1** (después de S2): ¿El buyer persona representa a mi cliente real? ¿Los competidores están bien?
- **Gate S2** (después de S5): ¿Toda la estrategia es coherente? ¿Lista para alimentar al workflow semanal?

### Input
```json
// product_brief.json
{
  "product_id": "misterio-semanal",
  "product_name": "Caso de misterio semanal",
  "description": "Experiencias de misterio detectivesco...",
  "price": 19.99,
  "currency": "USD",
  "billing": "per-case",
  "platform_url": "https://theclassifiedcases.shop",
  "target_audience_hint": "Adultos 25-45 que buscan entretenimiento inteligente",
  "monthly_marketing_budget": 50,
  "language": "es",
  "country": "global-hispanic"
}
```

### Output
5 archivos JSON validados + strategy_manifest.json (ver sección de manifests)

---

## PARTE 2: Runtime / Orchestrator

### Qué hace
Script central que coordina Strategy y Marketing. Controla dependencias, versiones, invalidez y gates. Es el único punto de entrada para ejecutar cualquier workflow.

### Regla no negociable
**Marketing no corre sin estrategia válida.** Si faltan archivos, si la estrategia no está aprobada, o si está invalidada → marketing queda bloqueado y Telegram notifica con acciones concretas.

### Flujo maestro
```
product_brief.json
    ↓
[Runtime Check] ¿Existe estrategia válida y aprobada?
    ├─ NO → ejecutar Strategy Workflow → Gate S1/S2 → aprobar
    └─ SÍ → continuar
    ↓
[Marketing Runtime Check] estrategia aprobada + válida?
    ├─ SÍ → fijar strategy_version_used → ejecutar Marketing Weekly
    └─ NO → bloquear → notificar por Telegram
    ↓
[Human Gates M1/M2/M3]
    ↓
Assets aprobados + action list
```

### Version Pinning (CRÍTICO)
Cuando un run semanal arranca, queda fijado a una versión concreta de estrategia. Si aparece v3 mientras corre W14, W14 sigue usando v2. Esto evita inconsistencias.

```json
// En run_manifest.json
"strategy_version_used": "v2"  // inmutable una vez iniciado
```

### Invalidación de Estrategia

**Hard invalid** — bloquea marketing automáticamente:
- Cambio de precio significativo (>20%)
- Cambio de buyer persona / target audience
- Cambio de país o idioma
- Cambio de posicionamiento / propuesta de valor

**Soft invalid** — notifica por Telegram, pide decisión humana:
- Ventas caen >30%
- CPA insostenible por 2+ semanas
- Engagement cae persistentemente
- Estrategia tiene >90 días
- Cambios fuertes en mercado/competencia

**Regla operativa:**
- hard_invalid → marketing bloqueado hasta regenerar estrategia
- soft_invalid → Telegram avisa, humano decide: usar actual o regenerar

**Para v1:** Invalidación manual vía Telegram. Automatización en v2.

---

## PARTE 3: Sistema de Manifests

### A. product_manifest.json (contrato maestro)
```json
{
  "product_id": "misterio-semanal",
  "product_name": "Caso de misterio semanal",
  "active_strategy_version": "v2",
  "latest_strategy_version": "v2",
  "strategy_status": "approved",
  "strategy_validity": "valid",
  "approved_at": "2026-03-26T16:10:00Z",
  "current_weekly_run": "2026-W14",
  "files": {
    "product_brief": "product_brief.json",
    "market_analysis": "strategies/v2/market_analysis.json",
    "buyer_persona": "strategies/v2/buyer_persona.json",
    "brand_strategy": "strategies/v2/brand_strategy.json",
    "seo_architecture": "strategies/v2/seo_architecture.json",
    "channel_strategy": "strategies/v2/channel_strategy.json",
    "strategy_manifest": "strategies/v2/strategy_manifest.json"
  },
  "last_updated_at": "2026-03-26T16:10:00Z"
}
```

### B. strategies/vN/strategy_manifest.json (por versión)
```json
{
  "product_id": "misterio-semanal",
  "strategy_version": "v2",
  "source_brief_hash": "abc123def456",
  "created_at": "2026-03-26T15:40:00Z",
  "created_by_workflow": "strategy-workflow",
  "status": "approved",
  "validity": "valid",
  "approved_by": "Alfredo",
  "approved_at": "2026-03-26T16:10:00Z",
  "outputs": {
    "market_analysis": "market_analysis.json",
    "buyer_persona": "buyer_persona.json",
    "brand_strategy": "brand_strategy.json",
    "seo_architecture": "seo_architecture.json",
    "channel_strategy": "channel_strategy.json"
  },
  "invalidation_rules": {
    "price_change_pct": 20,
    "target_audience_changed": true,
    "positioning_changed": true,
    "country_or_language_changed": true,
    "sales_drop_pct": 30,
    "max_age_days": 90
  }
}
```

### C. weekly_runs/<week>/run_manifest.json (por ejecución)
```json
{
  "product_id": "misterio-semanal",
  "run_id": "2026-W14",
  "started_at": "2026-03-26T18:00:00Z",
  "strategy_version_used": "v2",
  "status": "awaiting_gate_1",
  "gates": {
    "scripts_gate": {"status": "pending", "approved_by": null},
    "ads_emails_gate": {"status": "not_started"},
    "calendar_gate": {"status": "not_started"}
  },
  "outputs": {
    "scripts": "drafts/scripts.json",
    "ads": "drafts/ads.json",
    "emails": "drafts/emails.json",
    "calendar": "drafts/calendar.json"
  },
  "cost_usd": 0.0
}
```

---

## PARTE 4: Estructura de Directorios

```
~/.openclaw/products/
├── misterio-semanal/
│   ├── product_brief.json              ← input del usuario
│   ├── product_manifest.json           ← contrato maestro
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
│   │   ├── 2026-W14/
│   │   │   ├── run_manifest.json
│   │   │   ├── drafts/
│   │   │   ├── approved/
│   │   │   └── reports/
│   │   └── 2026-W15/
│   └── runtime/
│       ├── runtime_state.json
│       └── invalidation_log.json
└── velas-artesanales/
    └── ... (misma estructura)
```

---

## PARTE 5: Telegram como Panel de Decisión

### Comandos v1 (mínimos)
```
/strategy status <product_id>     — estado actual de la estrategia
/strategy run <product_id>        — ejecutar Strategy Workflow
/strategy approve <product_id>    — aprobar estrategia actual
/marketing run <product_id>       — ejecutar run semanal
/marketing approve <run_id>       — aprobar gate actual
```

### Mensajes de ejemplo

**Marketing bloqueado:**
```
🛑 Marketing bloqueado
Producto: misterio-semanal

Razón: No existe estrategia aprobada y válida

Faltan:
- buyer_persona.json
- brand_strategy.json
- channel_strategy.json

Acciones:
1. /strategy run misterio-semanal
2. /strategy status misterio-semanal
```

**Strategy lista para revisión:**
```
✅ Strategy v1 lista para revisión
Producto: misterio-semanal

Resumen:
- Buyer persona: parejas y grupos 25-45 que buscan entretenimiento inteligente
- Pain points: aburrimiento, poco tiempo, planes repetitivos
- Value prop: experiencia semanal inmersiva sin preparación
- Canales: Instagram, TikTok, Email
- SEO: keywords informacionales + transaccionales

Decisión:
1. /strategy approve misterio-semanal
2. /strategy reject misterio-semanal
```

**Run semanal listo:**
```
🚀 Weekly Run 2026-W14
Producto: misterio-semanal
Strategy: v2

Outputs generados:
- 3 guiones (TikTok/Reels)
- 3 ad copies (Meta Ads)
- 3 emails (nurturing)
- Calendario semanal

Gate actual: Scripts
1. /marketing approve 2026-W14
2. /marketing reject 2026-W14
```

---

## PARTE 6: Requisitos Técnicos

### Infraestructura
- OpenClaw en WSL Ubuntu
- Bot de Telegram dedicado para este sistema (separado del CEO y de Declassified)
- Modelos vía LiteLLM: Sonnet 4.6, Opus 4.6, GPT-5.2, GPT-5.4, Gemini 3.1 Pro, GPT-5 Mini
- Los agentes de investigación necesitan web search real
- Storage: JSON local

### Presupuesto
- Máximo $50/mes total para todo el ecosistema de marketing
- Strategy Workflow: <$2 por ejecución (pocas veces)
- Marketing Weekly: ~$0.09/run (~$0.36/mes)
- Runtime/Orchestrator: costo negligible (scripts sin LLM)

### Escalabilidad
- Agnóstico del producto: solo cambia product_brief.json
- Un bot de Telegram para todos los productos de marketing
- Productos aislados por directorio (~/.openclaw/products/<product_id>/)

### Conexión con marketing-workflow-1
El workflow de marketing semanal ya diseñado espera estos archivos:
- buyer_persona.json → script_generator, ad_copy_generator, email_generator
- brand_strategy.json → tono, voz, claims para todo el contenido
- channel_strategy.json → plataformas y formatos
- seo_architecture.json → artículos de blog (Standard)
- product_manifest.json → preflight check del runtime

### Fases de implementación recomendadas
1. **Fase 1 — Runtime mínimo:** manifests, preflight checks, bloqueo sin estrategia, Gate S1 por Telegram
2. **Fase 2 — Versionado:** strategies/v1, v2, active_strategy_version, compare
3. **Fase 3 — Invalidación:** hash del brief, reglas hard/soft, invalidation log
4. **Fase 4 — UX Telegram:** comandos completos, reportes útiles, reanudación
