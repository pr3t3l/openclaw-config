# Meta-Workflow Planner — v3 Operational
## Documento de implementación final
### Lead Developer: Claude Opus 4.6 | Fecha: 2026-03-24
### Revisado por: GPT-5.4 (v1 draft + v2 review), Gemini 3.1 Pro, MiniMax M2.7
### Status: BUILD PHASE 1 COMPLETE — Phase 2 pending

---

## CHANGELOG

| Versión | Qué cambió |
|---------|-----------|
| v1 (Claude) | 10 agentes, 4 fases, debate siempre, ~$3.88/plan |
| v1 (GPT) | 12 fases, 4 rondas debate, principios P-01 a P-07 |
| v2 (merge) | 6 fijos + 4 condicionales, debate condicional, schemas, ~$0.90-2.50 |
| **v3 (esta)** | +4 fixes GPT: no symlink, debate configurable, model routing en config, gate persistence. Prompts por agente. Estructura de carpetas. Scripts. Implementable. |
| v3.1 (2026-03-24) | Build Phase 0+1 complete. Git unificado. Fase A probada con finance-test y declassified-marketing. Pendiente: upgrade debate multi-modelo para Gap Finder y Data Flow. |

### Fixes v2→v3 (de la revisión GPT sobre v2)

1. **No symlink a Declassified.** `spawn_agent.py` se copia a `~/.openclaw/shared/scripts/` como utilidad compartida, versionada y pinneada. El planner no depende del repo de Declassified.
2. **spawn_debate.py configurable.** Parallel por defecto (asyncio subprocess), fallback a sequential. Configurable en `planner_config.json`.
3. **Model routing en config, no hardcoded.** Archivo `models.json` con modelo por agente. Costos son "estimaciones preliminares", no compromisos.
4. **Human gates con persistencia.** Cada gate guarda: estado, quién aprobó, timestamp, comentario. Permite resume sin ambigüedad.

---

## BUILD STATUS

| Phase | Status | Date | Notes |
|-------|--------|------|-------|
| Phase 0: Setup | ✅ Complete | 2026-03-24 | Workspace, configs, schemas, scripts base. Commit 174ac87 |
| Phase 1: Clarify (A1+A2+A3) | ✅ Complete | 2026-03-24 | spawn_planner_agent.py + 3 SKILL.md + run_phase_a.sh. Commit 50cb985 |
| Git Unification | ✅ Complete | 2026-03-24 | Todo bajo openclaw-config. Commit 66bd183 |
| Phase 2: Design (B1+B2+B3) | ⏳ Next | — | Data Flow, Contracts, Architecture (con spawn_debate.py) |
| Phase 3: Buildability (C1+C2+C3) | ⬜ Pending | — | Implementation Plan, Cost Script, Lessons Validator |
| Phase 4: E2E Test | ⬜ Pending | — | Full run con idea nueva |
| Phase 5: Optional Modules | ⬜ Future | — | Market Research, Capability Map, Compliance, Red Team |
| Telegram Bot Integration | ⬜ Future | — | Bot dedicado por workflow (no CEO como router) |

### Test Runs

| Run | Idea | Status | Gate #1 | Notes |
|-----|------|--------|---------|-------|
| finance-test | Personal finance tracker via Telegram | Fase A complete | ✅ Approved | 12 gaps, 6 blockers, score 38. MVP: $0/run sin LLM |
| declassified-marketing | Marketing workflow para vender casos | Fase A complete | ✅ Approved | 9 blockers, score 22. MVP: $0.12/run, 4 agentes, ~18h build |

### PENDING UPGRADES (post-Phase 2)

Decisión tomada 2026-03-24: Todas las ideas de Alfredo serán complex/critical. Ajustes pendientes:

1. **Gap Finder (A2) → debate multi-modelo siempre.** 2-3 modelos buscando gaps independientemente + consolidador. Diferentes modelos encuentran diferentes blind spots.
2. **Eliminar nivel "simple" del debate.** El piso es "complex" (2 modelos + juez).
3. **Data Flow Mapper (B1) → considerar debate.** Para ideas grandes, múltiples perspectivas en el mapeo de data flow evitan orphan outputs.
4. **Architecture Planner (B3) → mínimo 2 modelos siempre.** Complex como piso, critical para los más grandes.
5. **Impacto en costo:** Plan pasa de ~$0.90 a ~$2.50-3.50 por ejecución. Sigue siendo barato vs rework evitado.

Estos upgrades se implementan DESPUÉS de que el pipeline completo (Fases A-C) funcione end-to-end. Primero feo pero funcional (L-04), después mejorar.

---

## 1. OBJETIVO DE v1

Tomar una idea cruda y producir un plan buildable con suficiente claridad para empezar a construir sin rehacer el pipeline después.

No es una empresa simulada. No es un generador de departamentos. Es un sistema que fuerza decisiones estructurales antes de implementar.

---

## 2. WORKSPACE STRUCTURE

```
~/.openclaw/workspace-meta-planner/
├── AGENTS.md                          ← Instrucciones del orquestador (si se promueve a agente)
├── planner_config.json                ← Config general del planner
├── models.json                        ← Model routing (NO hardcoded en scripts)
├── skills/                            ← SKILL.md por agente del planner
│   ├── intake-analyst/SKILL.md
│   ├── gap-finder/SKILL.md
│   ├── scope-framer/SKILL.md
│   ├── data-flow-mapper/SKILL.md
│   ├── contract-designer/SKILL.md
│   ├── architecture-planner/SKILL.md
│   ├── implementation-planner/SKILL.md
│   ├── lessons-validator/SKILL.md
│   ├── landscape-researcher/SKILL.md     ← Condicional
│   ├── capability-mapper/SKILL.md        ← Condicional
│   ├── compliance-reviewer/SKILL.md      ← Condicional
│   ├── creative-strategist/SKILL.md      ← Condicional
│   └── red-team/SKILL.md                 ← Condicional
├── schemas/                           ← JSON Schema por artefacto
│   ├── 00_intake_summary.schema.json
│   ├── 01_gap_analysis.schema.json
│   ├── 02_scope_decision.schema.json
│   ├── 03_data_flow_map.schema.json
│   ├── 04_contracts.schema.json
│   ├── 05_architecture_decision.schema.json
│   ├── 06_implementation_plan.schema.json
│   ├── 07_cost_estimate.schema.json
│   └── 08_plan_review.schema.json
├── scripts/
│   ├── start_plan.sh                  ← Inicializa un run
│   ├── spawn_planner_agent.py         ← Spawner adaptado (usa shared/scripts/spawn_core.py)
│   ├── spawn_debate.py                ← Multi-model debate (parallel/sequential configurable)
│   ├── cost_estimator.py              ← Script Python determinístico (NO LLM)
│   ├── validate_schema.py             ← Valida artefactos contra schemas/
│   └── resume_plan.sh                 ← Resume un run pausado en un gate
├── runs/                              ← Un subdirectorio por ejecución
│   └── <slug>/
│       ├── manifest.json              ← Estado, costos, gates, hashes
│       ├── 00_intake_summary.json
│       ├── 01_gap_analysis.json
│       ├── ...
│       └── 08_plan_review.json
└── README.md                          ← Cómo usar el planner

~/.openclaw/shared/                    ← NUEVO: utilidades compartidas (no depende de ningún workspace)
├── scripts/
│   ├── spawn_core.py                  ← Copia pinneada del patrón spawn_agent.py
│   └── VERSION                        ← Versión de los scripts compartidos
└── lessons_learned.md                 ← Referencia maestra de lessons learned
```

### Por qué `shared/` es nuevo

GPT identificó correctamente que hacer symlink de `spawn_agent.py` desde Declassified acopla el planner a un workspace protegido. La solución:

- `~/.openclaw/shared/scripts/spawn_core.py` — copia pinneada del patrón probado de spawn_agent.py
- Se actualiza manualmente y con versión explícita (`VERSION` file)
- Tanto el planner como Declassified pueden importar de aquí sin depender uno del otro
- Si Declassified cambia algo en su spawn, el planner no se rompe (y viceversa)

**Migración futura:** Cuando Declassified se estabilice post-v9, migrar su spawn_agent.py para que también use `shared/scripts/spawn_core.py`.

---

## 3. CONFIGURATION FILES

### planner_config.json

```json
{
  "version": "1.0.0",
  "workspace_root": "/home/robotin/.openclaw/workspace-meta-planner",
  "shared_scripts": "/home/robotin/.openclaw/shared/scripts",
  "lessons_learned_path": "/home/robotin/.openclaw/shared/lessons_learned.md",
  "debate": {
    "execution_mode": "parallel",
    "fallback_to_sequential": true,
    "parallel_max_concurrent": 3,
    "timeout_per_model_seconds": 300,
    "subprocess_timeout_seconds": 350
  },
  "defaults": {
    "max_tokens_standard": 8192,
    "max_tokens_debate": 12288,
    "curl_max_time": 300,
    "subprocess_buffer": 50
  },
  "cost_estimates_are": "preliminary — not commitments",
  "schema_validation": {
    "enabled": true,
    "fail_on_orphan_outputs": true,
    "fail_on_missing_consumer": true
  }
}
```

### models.json

```json
{
  "_note": "Model routing for the planner. Change here, not in scripts. Costs are estimates.",
  "agents": {
    "intake_analyst":        { "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.08 },
    "gap_finder":            { "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.12 },
    "scope_framer":          { "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.08 },
    "data_flow_mapper":      { "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.10 },
    "contract_designer":     { "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.12 },
    "architecture_planner":  { "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.15 },
    "implementation_planner":{ "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.12 },
    "lessons_validator":     { "model": "claude-sonnet-4-6", "route": "direct_api", "est_cost": 0.12 }
  },
  "debate_models": {
    "simple":   ["claude-sonnet-4-6"],
    "complex":  ["claude-opus-4-6", "gpt-5.4"],
    "critical": ["claude-opus-4-6", "gpt-5.4", "gemini-3.1-pro"]
  },
  "judge": {
    "simple":   null,
    "complex":  "claude-sonnet-4-6",
    "critical": "claude-opus-4-6"
  },
  "red_team": "claude-opus-4-6",
  "cost_estimator": "script",
  "conditional_modules": {
    "landscape_researcher":  { "model": "claude-sonnet-4-6", "route": "direct_api", "needs_web_search": true },
    "capability_mapper":     { "model": "claude-sonnet-4-6", "route": "direct_api" },
    "compliance_reviewer":   { "model": "claude-sonnet-4-6", "route": "direct_api" },
    "creative_strategist":   { "model": "claude-sonnet-4-6", "route": "direct_api" },
    "red_team":              { "model": "claude-opus-4-6",   "route": "direct_api" }
  }
}
```

**Si quieres probar M2.7 para intake o gap finder:** cambias una línea en `models.json`, no tocas scripts ni prompts.

---

## 4. MANIFEST.JSON (por run)

```json
{
  "plan_id": "personal-finance-tracker",
  "created_at": "2026-03-25T10:00:00Z",
  "last_modified": "2026-03-25T12:30:00Z",
  "debate_level": "simple",
  "scope_selected": null,
  "artifacts": {
    "00_intake_summary":        { "status": "fresh", "hash": "abc123", "cost_usd": 0.08, "timestamp": "..." },
    "01_gap_analysis":          { "status": "fresh", "hash": "def456", "cost_usd": 0.11, "timestamp": "..." },
    "02_scope_decision":        { "status": "stale", "hash": null,     "cost_usd": null,  "timestamp": null },
    "03_data_flow_map":         { "status": "missing","hash": null,     "cost_usd": null,  "timestamp": null },
    "04_contracts":             { "status": "missing","hash": null,     "cost_usd": null,  "timestamp": null },
    "05_architecture_decision": { "status": "missing","hash": null,     "cost_usd": null,  "timestamp": null },
    "06_implementation_plan":   { "status": "missing","hash": null,     "cost_usd": null,  "timestamp": null },
    "07_cost_estimate":         { "status": "missing","hash": null,     "cost_usd": null,  "timestamp": null },
    "08_plan_review":           { "status": "missing","hash": null,     "cost_usd": null,  "timestamp": null }
  },
  "gates": {
    "gate_1": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null },
    "gate_2": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null },
    "gate_3": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null }
  },
  "total_cost_usd": 0.19,
  "conditional_modules_activated": []
}
```

### Invalidation rule

Cuando un artefacto se re-genera, todo downstream se marca `stale`:

```
00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08
```

Si re-generas `01_gap_analysis`, artefactos `02` a `08` se marcan stale. El script solo re-ejecuta los stale, no todo.

### Gate persistence (fix GPT #4)

Cada gate guarda quién aprobó, cuándo, y con qué comentario. Si Alf para entre Fase B y Fase C, `resume_plan.sh` lee manifest.json, encuentra el último gate aprobado, y continúa desde ahí.

---

## 5. PIPELINE FLOW

```
[Input: Idea cruda — texto libre del usuario]
    │
    ▼
╔═══════════════════════════════════════════════════════╗
║  FASE A — CLARIFY                                     ║
║                                                       ║
║  [A1: Intake Analyst] → 00_intake_summary.json        ║
║     Si status = NEEDS_CLARIFICATION → preguntas → loop║
║                                                       ║
║  [A2: Gap Finder] → 01_gap_analysis.json              ║
║     Si blocker_gaps > 0 → pausa + preguntas           ║
║                                                       ║
║  [A3: Scope Framer] → 02_scope_decision.json          ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
    │
    ▼
🚧 GATE #1: ¿Idea clara? ¿Gaps resueltos? ¿Scope elegido?
    │ ←── Si cambios: re-run A1/A2/A3 con contexto previo
    ▼
╔═══════════════════════════════════════════════════════╗
║  FASE B — DESIGN                                      ║
║                                                       ║
║  [B1: Data Flow Mapper] → 03_data_flow_map.json       ║
║     FAIL si orphan_outputs no vacío (L-01)            ║
║                                                       ║
║  [B2: Contract Designer] → 04_contracts.json          ║
║                                                       ║
║  [B3: Architecture Planner] → 05_architecture.json    ║
║     Nivel debate según debate_level:                  ║
║       simple  → 1 modelo                              ║
║       complex → 2 modelos + juez                      ║
║       critical→ 3 modelos + juez + red team opcional  ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
    │
    ▼
🚧 GATE #2: ¿Arquitectura aprobada? ¿Contratos completos?
    │ ←── Si cambios: re-run B1/B2/B3
    ▼
╔═══════════════════════════════════════════════════════╗
║  FASE C — BUILDABILITY                                ║
║                                                       ║
║  [C1: Implementation Planner] → 06_impl_plan.json     ║
║                                                       ║
║  [C2: Cost Estimator] → 07_cost_estimate.json         ║
║     (Script Python, NO LLM)                           ║
║                                                       ║
║  [C3: Lessons Validator] → 08_plan_review.json        ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
    │
    ▼
🚧 GATE #3: GO / NEEDS_REVISION / DO_NOT_BUILD_YET
    │
    ▼
[Output: Buildable planning package en runs/<slug>/]
```

---

## 6. AGENT PROMPTS (SKILL.md por agente)

### A1: Intake Analyst

```markdown
# Intake Analyst — SKILL.md

## Rol
Convertir una idea cruda en una especificación mínima estructurada.

## Input
- Texto libre del usuario describiendo una idea de proyecto/workflow
- (Opcional) Restricciones conocidas

## Output
- `00_intake_summary.json` — debe cumplir el schema en schemas/00_intake_summary.schema.json

## Instrucciones

1. Lee el texto del usuario con atención.
2. Extrae: problema central, quién se beneficia, qué inputs existen hoy, qué outputs se esperan.
3. Clasifica el proyecto: internal_tool | commercial_product | marketing | content_factory | research | software | operations | hybrid.
4. Evalúa el nivel de debate recomendado:
   - simple: herramienta interna, dominio conocido, <5 agentes probables, bajo riesgo
   - complex: múltiples artefactos, APIs externas, trade-offs arquitectónicos significativos
   - critical: dominio nuevo, inversión alta (>$50/mes), producto con clientes reales
5. Si faltan datos CRÍTICOS para avanzar (no sabes qué inputs existen, no sabes qué output se espera, no hay forma de evaluar el scope), marca status = NEEDS_CLARIFICATION y genera MÁXIMO 3 preguntas de alto impacto.
6. Si tienes suficiente para avanzar (aunque haya incertidumbre menor), marca status = READY.

## NUNCA
- Diseñes agentes o departamentos en esta fase
- Propongas soluciones técnicas
- Asumas inputs o outputs que el usuario no mencionó
- Generes más de 3 preguntas de clarificación

## Ejemplo de output parcial
{
  "project_name": "Personal Finance Tracker",
  "core_problem": "No hay forma automatizada de trackear gastos enviados por Telegram",
  "target_beneficiary": "Alfredo (uso personal)",
  "project_category": "internal_tool",
  "known_inputs": ["mensaje de Telegram con monto y descripción"],
  "desired_outputs": ["balance actualizado", "categoría asignada", "respuesta en Telegram"],
  "activation_mode": "telegram_message",
  "frequency": "por transacción (~10/día)",
  "budget_monthly_max": 5,
  "known_constraints": ["debe correr en OpenClaw/WSL", "sin base de datos externa"],
  "critical_missing_data": [],
  "debate_level_recommendation": "simple",
  "status": "READY"
}
```

### A2: Gap Finder

```markdown
# Gap Finder — SKILL.md

## Rol
Encontrar todo lo que el usuario NO pensó. Este agente es implacable, no complaciente.

## Input
- 00_intake_summary.json
- lessons_learned.md (referencia maestra)

## Output
- 01_gap_analysis.json — debe cumplir el schema

## Instrucciones

Actúa como un ingeniero de sistemas que ha visto docenas de pipelines fallar.
Revisa el intake_summary y busca activamente:

1. **Orfandad de datos:** ¿Hay outputs pedidos sin fuente de datos clara? ¿Hay inputs mencionados que nadie consume?
2. **Decisiones de infraestructura faltantes:**
   - Almacenamiento: ¿dónde persisten los datos entre ejecuciones?
   - Frecuencia: ¿cron, event-driven, manual?
   - Human gates: ¿dónde la automatización es demasiado arriesgada?
   - Privacy: ¿hay datos sensibles?
   - Rollback: ¿qué pasa si algo falla a mitad?
   - Observability: ¿cómo sabes que funcionó?
   - Fallbacks: ¿qué pasa si un API falla?
   - Mantenimiento: ¿quién actualiza el workflow cuando cambian los requisitos?
3. **Criterio de éxito:** ¿cómo sabe el usuario que el workflow terminó bien? Si no está definido, es un gap CRITICAL.
4. **Anti-patterns conocidos:** Revisa lessons_learned.md. ¿Alguna lección L-01 a L-32 aplica? Marca cada anti-pattern detectado con su L-XX correspondiente.

Para cada gap, clasifica:
- blocker: impide avanzar, DEBE resolverse antes de Gate #1
- advisory: conviene resolver pero no bloquea

Genera un readiness_score de 0-100.
- 80-100: listo para Scope
- 50-79: tiene gaps advisory, puede avanzar con precaución
- <50: tiene blockers, necesita clarificación

## NUNCA
- Diseñes soluciones (solo expones problemas)
- Seas complaciente (si no encuentras al menos 5 dimensiones a revisar, no estás haciendo tu trabajo)
- Ignores las lessons learned
```

### A3: Scope Framer

```markdown
# Scope Framer — SKILL.md

## Rol
Forzar una decisión entre MVP / Standard / Advanced.

## Input
- 00_intake_summary.json
- 01_gap_analysis.json

## Output
- 02_scope_decision.json — debe cumplir el schema

## Instrucciones

1. Propón 3 versiones del proyecto:
   - **MVP:** Lo mínimo que entrega valor. Feo pero funcional (L-04).
   - **Standard:** MVP + las mejoras más pedidas.
   - **Advanced:** La visión completa.

2. Para cada versión, define:
   - features incluidas
   - features EXPLÍCITAMENTE excluidas
   - número estimado de agentes/scripts
   - esfuerzo estimado en horas
   - costo estimado por ejecución
   - riesgo de under-scoping (qué se pierde)
   - riesgo de over-scoping (qué se desperdicia)

3. Recomienda cuál implementar primero y por qué.
4. Define el upgrade path: cómo pasar de MVP a Standard sin rehacer todo (L-04, L-05).

## NUNCA
- Recomiendes empezar por Advanced
- Propongas un MVP que no entrega valor real al usuario
- Ignores los gaps identificados en 01_gap_analysis
```

### B1: Data Flow Mapper

```markdown
# Data Flow Mapper — SKILL.md

## Rol
Definir CADA artefacto que el workflow producirá, quién lo produce, quién lo consume, y por qué existe.

## Input
- 00_intake_summary.json
- 01_gap_analysis.json
- 02_scope_decision.json (scope seleccionado)

## Output
- 03_data_flow_map.json — debe cumplir el schema

## Instrucciones

1. Para el scope seleccionado, lista TODOS los artefactos (archivos) que se producirán durante la ejecución del workflow.
2. Para cada artefacto, define:
   - Quién lo produce (agente, script, humano, API externa)
   - Quién lo consume (puede ser más de uno)
   - Formato (json, md, csv, pdf, image, etc.)
   - Por qué existe (qué valor aporta)
   - Si es fuente de verdad o artefacto intermedio
   - Si debe persistir o puede eliminarse después

3. REGLA DURA (L-01): Si un artefacto no tiene consumidor, NO lo incluyas. Pon una nota en orphan_outputs explicando por qué se descartó.
4. REGLA DURA (L-01): Si un consumidor necesita un artefacto que nadie produce, ponlo en missing_required_artifacts.
5. Si orphan_outputs o missing_required_artifacts no están vacíos, el planner FALLA y no avanza.

## NUNCA
- Incluyas artefactos "por si acaso"
- Dejes un output sin consumidor explícito
- Dejes un consumidor sin productor explícito
```

### B2: Contract Designer

```markdown
# Contract Designer — SKILL.md

## Rol
Para cada par productor-consumidor, definir el contrato exacto: schema JSON, campos requeridos, validaciones.

## Input
- 03_data_flow_map.json

## Output
- 04_contracts.json — debe cumplir el schema

## Instrucciones

1. Para cada artefacto en el data flow map que tenga formato JSON, define:
   - Schema completo con tipos, campos requeridos, descripciones
   - Ejemplo con valores realistas
   - Reglas de validación (min_length, patterns, allowed_values)
   - Si necesita un script de validación (validate_*.py)

2. Para artefactos markdown/CSV, define: estructura esperada, secciones requeridas, campos clave.

3. Aplica L-02: este contrato debe existir ANTES de que se construya el agente que lo produce.
4. Aplica L-20: si un artefacto es la spec completa para un agente downstream, debe ser self-contained.
5. Aplica L-08: si un artefacto es demasiado grande para producirse en una sola API call, recomienda dividirlo.

## NUNCA
- Dejes un contrato sin ejemplo
- Definas campos ambiguos (e.g., "data": "any")
- Ignores la estimación de tamaño en tokens (importa para MAX_TOKENS)
```

### B3: Architecture Planner

```markdown
# Architecture Planner — SKILL.md

## Rol
Diseñar la arquitectura técnica del workflow: agentes, scripts, modelos, patterns de ejecución.

## Input
- Todos los artefactos anteriores (00 a 04)
- system_configuration_complete.md (infraestructura real)
- models.json (modelos disponibles y costos)

## Output
- 05_architecture_decision.json — debe cumplir el schema

## Instrucciones

### Si debate_level = simple (1 modelo):
Propón directamente la arquitectura óptima.

### Si debate_level = complex o critical:
Este prompt se usa como system prompt para CADA modelo en el debate.
Cada modelo produce independientemente una propuesta con el mismo schema.
Después, el juez compara.

1. Define los componentes del workflow:
   - Agentes (qué hace cada uno, qué modelo usa, spawn method)
   - Scripts determinísticos (validadores, calculadoras, formatters)
   - Human gates (dónde y por qué)
   - Storage (archivos, SQLite, JSON)

2. Para cada agente:
   - Justifica por qué es un agente y no un script (L-22: si es determinístico, usa script)
   - Asigna modelo de models.json con justificación
   - Define spawn method: spawn_core.py (para direct API) o script Python
   - Estima input/output tokens y costo

3. Valida contra infraestructura real:
   - ¿Los modelos existen en LiteLLM? (check models.json)
   - ¿El spawn method es compatible con WSL? (TL-01: curl obligatorio)
   - ¿Las rutas son absolutas? (TL-10)
   - ¿El presupuesto mensual del usuario lo soporta?

4. Define el patrón de ejecución:
   - Trigger: ¿cómo arranca? (Telegram message, cron, manual)
   - Workflow: ¿secuencial, condicional, parallel?
   - Retry policy: máximo 2 retries antes de diagnóstico (L-26)
   - Rollback: ¿qué pasa si falla a mitad?

## Criterios de evaluación (para el juez en debates):
| Criterio | Peso |
|----------|------|
| Factibilidad con infraestructura actual | 25% |
| Costo eficiencia | 25% |
| Tiempo a MVP | 20% |
| Cobertura de gaps identificados | 15% |
| Simplicidad (menos agentes = mejor, a igual calidad) | 15% |

## NUNCA
- Uses sessions_spawn para escribir archivos (TL-04)
- Asumas modelos que no están en models.json
- Propongas Python requests para API calls en WSL (TL-01)
- Mezcles infraestructura con calidad (L-05)
```

### C1: Implementation Planner

```markdown
# Implementation Planner — SKILL.md

## Rol
Traducir la arquitectura aprobada en fases de construcción ejecutables.

## Input
- 05_architecture_decision.json
- 04_contracts.json

## Output
- 06_implementation_plan.json — debe cumplir el schema

## Instrucciones

1. Divide la construcción en fases secuenciales con dependencias.
2. Para cada fase define:
   - Tareas concretas (crear archivo X, escribir script Y, configurar Z)
   - Test mínimo: single-item E2E test (L-03)
   - Human gate: sí/no con justificación (L-28)
   - Definition of Done
   - Esfuerzo estimado en horas

3. La primera fase SIEMPRE es setup: workspace, directories, configs, bootstrap script.
4. La segunda fase SIEMPRE prueba file I/O del spawn method (L-06).
5. Lista explícitamente qué NO se construye todavía (deferred to v2).

## NUNCA
- Propongas construir todo de golpe
- Omitas el single-item test por fase
- Ignores las dependencias entre fases
```

### C3: Lessons Learned Validator

```markdown
# Lessons Learned Validator — SKILL.md

## Rol
Validar el plan completo contra las lecciones aprendidas y producir el veredicto final.

## Input
- Todos los artefactos (00 a 07)
- lessons_learned.md

## Output
- 08_plan_review.json — debe cumplir el schema

## Instrucciones

1. Para cada lección L-01 a L-32, verifica:
   - ¿El plan actual la aborda? (yes / no / partial)
   - Si no: ¿qué falta?
   - Si partial: ¿qué se debe reforzar?

2. Genera risk register:
   - Riesgos técnicos, de costo, de timeline, de calidad, de dependencias, de mantenimiento
   - Probabilidad e impacto por riesgo
   - Mitigación propuesta

3. Valida contra infraestructura:
   - ¿Modelos disponibles en LiteLLM?
   - ¿Spawn method compatible con OpenClaw?
   - ¿Rutas absolutas?
   - ¿Presupuesto realista?
   - ¿WSL constraints abordados?

4. Produce el veredicto:
   - GO: el plan es buildable y los riesgos son manejables
   - NEEDS_REVISION: hay gaps que deben cerrarse (lista revision_items)
   - DO_NOT_BUILD_YET: hay problemas fundamentales (explica por qué)

## NUNCA
- Des GO si hay lecciones CRITICAL no abordadas
- Ignores el costo del orquestador (L-09, L-25)
- Seas complaciente — mejor un NEEDS_REVISION honesto que un GO falso
```

---

## 7. SCRIPTS

### start_plan.sh

```bash
#!/bin/bash
# Usage: bash start_plan.sh <slug> "<idea text>"
# Example: bash start_plan.sh personal-finance "Quiero un workflow que cuando envíe un gasto por Telegram..."

set -euo pipefail

SLUG="$1"
IDEA="$2"
WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
RUN_DIR="$WORKSPACE/runs/$SLUG"

if [ -d "$RUN_DIR" ]; then
  echo "ERROR: Run '$SLUG' already exists. Use resume_plan.sh to continue."
  exit 1
fi

mkdir -p "$RUN_DIR"

# Initialize manifest
cat > "$RUN_DIR/manifest.json" << EOF
{
  "plan_id": "$SLUG",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_modified": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "raw_idea": $(python3 -c "import json; print(json.dumps('$IDEA'))"),
  "debate_level": null,
  "scope_selected": null,
  "artifacts": {
    "00_intake_summary":        { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "01_gap_analysis":          { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "02_scope_decision":        { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "03_data_flow_map":         { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "04_contracts":             { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "05_architecture_decision": { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "06_implementation_plan":   { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "07_cost_estimate":         { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null },
    "08_plan_review":           { "status": "missing", "hash": null, "cost_usd": null, "timestamp": null }
  },
  "gates": {
    "gate_1": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null },
    "gate_2": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null },
    "gate_3": { "status": "pending", "approved_by": null, "timestamp": null, "comment": null }
  },
  "total_cost_usd": 0,
  "conditional_modules_activated": []
}
EOF

echo "✅ Plan initialized: $RUN_DIR"
echo "Next: run Fase A (Clarify)"
echo "  python3 $WORKSPACE/scripts/spawn_planner_agent.py $SLUG intake_analyst"
```

### spawn_debate.py (pseudocódigo operativo)

```python
#!/usr/bin/env python3
"""
Multi-model debate for architecture decisions.
Calls N models (parallel or sequential), collects proposals, runs judge.

Usage: python3 spawn_debate.py <slug> <debate_level>
  debate_level: simple | complex | critical
"""

import json, sys, os, hashlib, asyncio, subprocess
from pathlib import Path

WORKSPACE = "/home/robotin/.openclaw/workspace-meta-planner"

def load_config():
    with open(f"{WORKSPACE}/planner_config.json") as f:
        return json.load(f)

def load_models():
    with open(f"{WORKSPACE}/models.json") as f:
        return json.load(f)

def call_model_via_curl(model, system_prompt, user_prompt, max_tokens, timeout):
    """
    Uses streaming curl via subprocess (TL-01: Python requests fails in WSL).
    Returns: { "content": str, "input_tokens": int, "output_tokens": int, "cost": float }
    """
    # Same pattern as spawn_core.py:
    # 1. Write prompt to tempfile (ensure_ascii=True)
    # 2. Call curl --data-binary @tempfile with stream: True
    # 3. Parse SSE events, detect message_stop
    # 4. Extract content and token usage
    # ... (implementation inherits from spawn_core.py)
    pass

async def call_model_async(model, system_prompt, user_prompt, max_tokens, timeout):
    """Async wrapper around curl subprocess for parallel execution."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, call_model_via_curl, model, system_prompt, user_prompt, max_tokens, timeout
    )

def run_debate(slug, debate_level):
    config = load_config()
    models_config = load_models()

    debate_models = models_config["debate_models"][debate_level]
    judge_model = models_config["judge"][debate_level]

    # Load skill and context
    skill = open(f"{WORKSPACE}/skills/architecture-planner/SKILL.md").read()
    context = load_upstream_artifacts(slug)  # 00 through 04

    proposals = []
    total_cost = 0

    # --- EXECUTION MODE ---
    execution_mode = config["debate"]["execution_mode"]

    if len(debate_models) == 1:
        # Simple: single model, no debate
        result = call_model_via_curl(
            model=debate_models[0],
            system_prompt=skill,
            user_prompt=context,
            max_tokens=config["defaults"]["max_tokens_debate"],
            timeout=config["defaults"]["curl_max_time"]
        )
        write_artifact(slug, "05_architecture_decision", result["content"], result["cost"])
        return

    if execution_mode == "parallel":
        try:
            loop = asyncio.new_event_loop()
            tasks = [
                call_model_async(m, skill, context,
                    config["defaults"]["max_tokens_debate"],
                    config["defaults"]["curl_max_time"])
                for m in debate_models
            ]
            results = loop.run_until_complete(asyncio.gather(*tasks))
            loop.close()
            proposals = [{"model": m, "response": r["content"], "cost": r["cost"]}
                        for m, r in zip(debate_models, results)]
        except Exception as e:
            print(f"Parallel failed ({e}), falling back to sequential")
            if config["debate"]["fallback_to_sequential"]:
                proposals = run_sequential(debate_models, skill, context, config)
            else:
                raise
    else:
        proposals = run_sequential(debate_models, skill, context, config)

    total_cost = sum(p["cost"] for p in proposals)

    # --- JUDGE ---
    judge_prompt = build_judge_prompt(proposals, debate_level)
    judge_result = call_model_via_curl(
        model=judge_model,
        system_prompt="You are a fair judge comparing structured architecture proposals. "
                      "Evaluate using the criteria weights in the prompt. "
                      "Output valid JSON matching 05_architecture_decision.schema.json.",
        user_prompt=judge_prompt,
        max_tokens=config["defaults"]["max_tokens_debate"],
        timeout=config["defaults"]["curl_max_time"]
    )
    total_cost += judge_result["cost"]

    # --- RED TEAM (critical only) ---
    if debate_level == "critical" and models_config.get("red_team"):
        red_team_result = call_model_via_curl(
            model=models_config["red_team"],
            system_prompt="You are a red team attacker. Find every way this architecture can fail. "
                          "Be ruthless. Output a JSON array of risks.",
            user_prompt=f"Architecture decision:\n{judge_result['content']}",
            max_tokens=8192,
            timeout=config["defaults"]["curl_max_time"]
        )
        total_cost += red_team_result["cost"]
        # Merge red team findings into architecture decision

    write_artifact(slug, "05_architecture_decision", judge_result["content"], total_cost)

def run_sequential(models, skill, context, config):
    proposals = []
    for m in models:
        result = call_model_via_curl(m, skill, context,
            config["defaults"]["max_tokens_debate"],
            config["defaults"]["curl_max_time"])
        proposals.append({"model": m, "response": result["content"], "cost": result["cost"]})
    return proposals

def write_artifact(slug, artifact_name, content, cost):
    run_dir = f"{WORKSPACE}/runs/{slug}"
    filepath = f"{run_dir}/{artifact_name}.json"

    # Write content
    with open(filepath, 'w') as f:
        f.write(content)

    # Update manifest
    manifest_path = f"{run_dir}/manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)

    file_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    manifest["artifacts"][artifact_name] = {
        "status": "fresh",
        "hash": file_hash,
        "cost_usd": round(cost, 4),
        "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z"
    }
    manifest["total_cost_usd"] = round(
        sum((v.get("cost_usd") or 0) for v in manifest["artifacts"].values()), 4
    )
    manifest["last_modified"] = __import__('datetime').datetime.utcnow().isoformat() + "Z"

    # Invalidate downstream
    artifact_order = ["00_intake_summary", "01_gap_analysis", "02_scope_decision",
                      "03_data_flow_map", "04_contracts", "05_architecture_decision",
                      "06_implementation_plan", "07_cost_estimate", "08_plan_review"]
    idx = artifact_order.index(artifact_name)
    for downstream in artifact_order[idx+1:]:
        if manifest["artifacts"][downstream]["status"] == "fresh":
            manifest["artifacts"][downstream]["status"] = "stale"

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    slug = sys.argv[1]
    level = sys.argv[2] if len(sys.argv) > 2 else "simple"
    run_debate(slug, level)
```

---

## 8. COST SUMMARY

| Nivel de debate | Costo planner | Cuándo |
|----------------|--------------|--------|
| Simple | ~$0.90 | Herramienta interna, dominio conocido |
| Complex | ~$1.60 | Múltiples artefactos, APIs externas |
| Critical | ~$2.50 | Dominio nuevo, producto comercial |
| + Módulos opcionales | +$0.10-0.40/módulo | Según proyecto |

**Estos son estimaciones preliminares.** Los costos reales se medirán en las primeras ejecuciones.

---

## 9. BUILD PHASES

### Build Phase 0: Setup (estimado 1-2 horas)

**Objetivo:** Crear workspace, shared scripts, configs, y verificar que el patrón de ejecución funciona.

**Tareas:**
1. Crear `~/.openclaw/workspace-meta-planner/` con toda la estructura de directorios
2. Crear `~/.openclaw/shared/scripts/` y copiar spawn_core.py (copia pinneada de spawn_agent.py)
3. Escribir `planner_config.json` y `models.json`
4. Escribir `start_plan.sh`
5. Escribir los 9 schema files en `schemas/`
6. Escribir `validate_schema.py`
7. **Test:** `bash start_plan.sh test-idea "Test idea"` → verifica que crea `runs/test-idea/manifest.json` correctamente
8. **Test:** Llamar spawn_core.py con un prompt trivial ("say hello") → verifica que direct API + curl funciona
9. Commit a git (decidir: ¿nuevo repo `meta-planner` o bajo `openclaw-config`?)

**Definition of Done:** workspace existe, configs son válidos, spawn_core.py produce output, manifest.json se crea correctamente.

### Build Phase 1: Clarify (A1 + A2 + A3) — estimado 3 horas
### Build Phase 2: Design (B1 + B2 + B3) — estimado 5 horas
### Build Phase 3: Buildability (C1 + C2 + C3) — estimado 2.5 horas
### Build Phase 4: End-to-end test — estimado 2 horas
### Build Phase 5: Optional modules — según necesidad

---

## 10. TESTING STRATEGY

| Test | Qué valida | Cuándo |
|------|-----------|--------|
| T-01: Known case | Correr planner con Declassified (respuesta conocida) | Después de Build Phase 3 |
| T-02: New internal tool | Correr planner con finanzas personales | Después de T-01 |
| T-03: New commercial | Correr planner con marketing Declassified | Después de T-02 |
| T-04: Single-item discipline | Después de cualquier cambio de infra, 1 run antes de batch | Siempre |
| T-05: Comparison | "¿Construiría desde este plan? ¿Redujo rework vs proceso normal?" | Después de T-01/T-02/T-03 |

---

## 11. WHAT THIS PLANNER MUST AVOID

1. Departamentos falsos sin impacto operativo (GPT, Gemini)
2. Debates siempre activos para ideas simples (M2.7, GPT)
3. Schemas después del hecho (todos)
4. Artefactos sin consumidor (L-01)
5. Inflación de agentes antes de probar valor (GPT)
6. Mezclar "funciona" con "es bueno" (L-05)
7. sessions_spawn para file writes (TL-04)
8. Symlinks a workspaces protegidos (GPT v2 review)
9. Hardcodear modelos en scripts (GPT v2 review)
10. Human gates sin persistencia (GPT v2 review)

---

## 12. DECISIONES PENDIENTES PARA BUILD PHASE 0

1. ¿Nuevo repo git (`meta-planner`) o subdirectorio de `openclaw-config`?
   - Recomendación: subdirectorio de openclaw-config por ahora (un solo repo de config). Repo separado si crece.
2. ¿spawn_core.py se copia textual de spawn_agent.py o se refactoriza?
   - Recomendación: copia textual primero. Refactorizar después de que funcione.
3. ¿Los SKILL.md se escriben todos en Phase 0 o se van escribiendo por fase?
   - Recomendación: escribir solo los de Phase 1 (A1, A2, A3) en Phase 0. Los demás se escriben en su fase.

---

## SIGUIENTE PASO

**GO condicional para Build Phase 0.** Solo setup, no agentes todavía.

Alf revisa este documento → lo pasa a GPT para validación rápida ("¿ves algo roto?") → si OK → Build Phase 0 en Claude Code.
