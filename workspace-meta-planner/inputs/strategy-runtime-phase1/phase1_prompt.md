# PHASE 1 — Strategy Workflow + Runtime/Orchestrator

Diseña conjuntamente:
1. Strategy Workflow
2. Runtime / Orchestrator

## Contexto obligatorio
Lee y respeta estos dos documentos como fuente de verdad:
- /home/robotin/.openclaw/workspace-meta-planner/inputs/strategy-runtime-phase1/system_architecture_marketing.md
- /home/robotin/.openclaw/workspace-meta-planner/inputs/strategy-runtime-phase1/idea_estrategia_fundacional_con_runtime.md

## Instrucciones críticas
- NO rediseñar Marketing Weekly desde cero; asumir que ya existe como `marketing-workflow-1` y es dependencia aguas abajo.
- Tu diseño debe ser 100% compatible con los manifests, ownership, enums, gates, directorios y reglas no negociables del system architecture congelado.
- Debes diseñar tanto el workflow operativo de Strategy como la infraestructura Runtime que decide cuándo Strategy o Marketing pueden correr.
- Marketing nunca corre sin estrategia válida y aprobada.
- Version pinning es obligatorio y debe quedar reflejado en `run_manifest.json`.
- Invalidación hard/soft debe quedar operacionalizada.
- El resultado debe ser producto-agnóstico, multi-producto y basado en JSON local.
- Telegram se usa para gates, bloqueos, estado y decisiones humanas.
- Los agentes de investigación deben usar web search real.

## Alcance esperado
Produce un plan completo buildable que cubra:
- Outputs de Strategy: market_analysis.json, buyer_persona.json, brand_strategy.json, seo_architecture.json, channel_strategy.json, strategy_manifest.json
- Runtime contracts: product_manifest.json, runtime_state.json, invalidation_log.json
- Gates S1 y S2
- Comandos mínimos de Telegram para strategy/runtime/marketing status
- Lógica de bloqueo de marketing, aprobación, versionado, reanudación e invalidación
- Directorios exactos bajo ~/.openclaw/products/<product_id>/
- Conexión explícita con marketing-workflow-1

## Requisitos de calidad
- Si detectas inconsistencias entre idea y system architecture, prevalece system architecture congelado y anota la reconciliación.
- Debes especificar ownership claro por artefacto, estados válidos, dependencias y flujo de datos.
- Debe quedar listo para luego diseñar Growth Intelligence sin romper contratos.

## Nivel
Análisis: deep
