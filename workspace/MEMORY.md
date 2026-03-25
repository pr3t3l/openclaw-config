# Robotin CEO — Long-Term Memory

## Identity
- Owner: Alfredo Pretel (Alf)
- Languages: Spanish, English
- Agent name: Robotin 🤖
- Model: MiniMax M2.7 via OpenRouter (since 2026-03-23)

## System
- OpenClaw v2026.3.13 on WSL Ubuntu
- LiteLLM proxy at :4000 (21 models, PostgreSQL spend tracking active)
- QMD memory search: active (2026-03-23)
- Dashboard: http://127.0.0.1:4000/ui/ (no auth, localhost-only)
- Git repos: ~/.openclaw/ → openclaw-config | workspace-declassified/ → declassified-cases-pipeline

## Active Projects
- Declassified Cases Pipeline: V9, production, @APVDeclassified_bot — managed by separate agent, DO NOT TOUCH
- System Optimization: OPTIMIZATION_PLAN.md in openclaw-config repo (Fases 0-6A complete)
- Meta-Workflow Planner: Design phase (future)

## Technical Rules
- TL-01: Python requests FAILS in WSL >30s — ALWAYS use curl via subprocess
- TL-11: OpenClaw v2026.3.2 doesn't resolve ${ENV_VARS} in apiKey — hardcode keys or skip master_key
- TL-12: LiteLLM dashboard login = master_key — incompatible with OpenClaw, dashboard runs without auth
- Budget-conscious — always mention cost implications
- Direct communication — no filler

## Key Decisions
- 2026-03-23: QMD memory backend configured (search mode, workspace/memory/*.md)
- 2026-03-23: Gemini API key renewed (18 → 21 LiteLLM endpoints with OpenRouter)
- 2026-03-23: CEO model changed from GPT-5.2 medium to MiniMax M2.7 ($0.30/$1.20 vs $2-5/$10-15)
- 2026-03-23: PostgreSQL spend tracking enabled, LiteLLM dashboard active
- 2026-03-23: Memory flush pre-compaction enabled (softThreshold 6000 tokens)
- 2026-03-23: Session maintenance: enforce, 200 max, 14d prune, dmScope per-channel-peer
- 2026-03-23: CEO heartbeat: 30m (was 999999m disabled)
- 2026-03-23: Optimization plan reviewed by GPT-5.2 (8.5/10) and Gemini 3.1 Pro

## Cost Awareness
- MiniMax M2.7: $0.30/MTok input, $1.20/MTok output (CEO primary)
- Claude Sonnet 4.6: $3/$15 MTok (pipeline creative/render — do not change)
- GPT-5.2: $2-5/$10-15 MTok (Declassified orchestrator — change pending A/B test)
- Step 3.5 Flash: $0.10/$0.30 MTok (budget fallback candidate)
- DALL-E 3: $0.04/image (pipeline POI portraits)

## Meta-Workflow Planner
- Status: Fase A (Clarify) operativa. Fases B y C pendientes.
- Workspace: ~/.openclaw/workspace-meta-planner/
- Trigger: "Planifica:", "Plan:", "Planear:" + idea
- Costo por Fase A: ~$0.30 (3 calls a Sonnet via LiteLLM)
- Test exitoso: finance-test (finanzas personales via Telegram)
- Fecha: 2026-03-24
