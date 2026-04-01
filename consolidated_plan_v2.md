# CONSOLIDACIÓN FINAL v2.1 — GAPS + AUDIT + BIBLE PLAN
## Incorpora feedback de GPT y Gemini (2 rondas)
## Fecha: 2026-03-29

---

# CAMBIOS vs v1 (resumen para GPT/Gemini ronda 2)

| # | Feedback | Fuente | Acción |
|---|----------|--------|--------|
| 1 | Script puede filtrar secrets (tokens, passwords) | GPT | ✅ Eliminado: `sudo cat sudoers` → solo `ls`. `grep TELEGRAM_OPS_TOKEN` → solo verifica existencia sin imprimir valor. `sync_keys.sh` → solo muestra estructura. LiteLLM config → filtra líneas con `api_key` |
| 2 | audit_report no debe commitearse a git | GPT | ✅ Prompt cambiado: "DO NOT commit". Solo Bible v2 sanitizado se commitea |
| 3 | Script es inventario, no prueba funcional | GPT | ✅ Añadido: `verify_db_parity.py` ejecución real, `curl` health checks funcionales, finance tracker smoke test, `claim_linter` integration check, LiteLLM `/v1/models` endpoint, `git status -sb` + dirty check + stash |
| 4 | Verificaciones perdidas del gap file al script | GPT | ✅ Añadido: `planner_config.json`, `models.json`, `model_routing.json`, `validate_art.py`, `ai_render.py` params, persona landing pages, UTM tracking |
| 5 | DB audit incompleto (13 de 24 tablas) | GPT | ✅ Cambiado: usa `pg_stat_user_tables` para listar TODAS las tablas del schema + FK count + CHECK count |
| 6 | Output demasiado grande | GPT | ✅ Script genera DOS salidas: `audit_report.md` (raw completo) + `audit_summary.json` (hechos estructurados) |
| 7 | Falta git status/branch/dirty/stash | GPT | ✅ Añadido a ambos repos |
| 8 | sudo puede colgar | GPT | ✅ Reemplazado por `ls` existence check |
| 9 | pip show puede usar pip equivocado | GPT+Gemini | ✅ Usa `/home/robotin/litellm-venv/bin/pip` explícitamente |
| 10 | Duplicación script en doc vs archivo | GPT | ✅ Plan v2 NO embebe el script, solo lo referencia |
| 11 | Faltan ai_render.py params | Gemini | ✅ grep MAX_TOKENS, timeout, model |
| 12 | Falta LiteLLM spend query | Gemini | ✅ Query a `LiteLLM_SpendLogs` últimas 4 semanas |
| 13 | Faltan HEARTBEAT.md, IDENTITY.md, cost_baseline.md | Gemini | ✅ Sección 3.4 dedicada |
| 14 | Falta tmux check | Gemini | ✅ Sección 1.9 |
| 15 | Falta QMD --version | Gemini | ✅ Corregido en sección 16 |
| 16 | Falta sección Cost Management en Bible v2 | Gemini | ✅ Añadida como sección 18 en estructura propuesta |
| 17 | Items no-auditables por filesystem (social media, IONOS, etc.) | GPT | ✅ Sección 19 "Manual Evidence" con confirmaciones directas de Alfredo |
| 18 | Bible mezcla infra + producto + secrets sin clasificar | GPT | ✅ Regla añadida: Bible es doc interno privado. Nunca publicar. Secrets van en .env, Bible solo referencia nombres |

## Ronda 2 fixes (GPT + Gemini)

| # | Feedback | Fuente | Acción |
|---|----------|--------|--------|
| 19 | systemctl --user para OpenClaw/LiteLLM | Gemini R2 | ✅ Añadido a sección 1.2 (check, no depender) |
| 20 | crontab completo, no solo grep backup | Gemini R2 | ✅ `crontab -l` sin filtro |
| 21 | git fetch antes de status | Gemini R2 | ✅ `git fetch --quiet` en ambos repos |
| 22 | stripe_sync.py missing check | Gemini R2 | ✅ Sección 7.7 añadida |
| 23 | Audit files ensucian git status | GPT R2 | ✅ Output movido a /tmp/ |
| 24 | audit_summary.json demasiado pobre | GPT R2 | ✅ Enriquecido: active models list, parity result, telegram status, env key names, ai_render params, structured per-subsystem |
| 25 | Instrucciones de output misaligned (plan vs script) | GPT R2 | ✅ Alineado: "show summary + errors only" |
| 26 | Hardcoded creds en script (sk-litellm-local, pg URL) | GPT R2 | ⬜ NO cambiar — son credenciales localhost-only sin riesgo real. Parametrizar añade complejidad sin beneficio |
| 27 | Raw report demasiado invasivo | GPT R2 | ⬜ NO cambiar — report es herramienta local, nunca se comparte raw. Necesitamos openclaw.json y AGENTS.md completos para resolver contradicciones |

---

# LOS 32 GAPS (sin cambios vs v1)

Referencia: archivo `consolidated_gaps_and_audit_plan.md` v1, Parte 2.
Los gaps siguen siendo los mismos 32. Lo que cambió es cómo se auditan.

---

# SCRIPT DE AUDITORÍA

**Archivo:** `openclaw_audit_script_v2.sh` (v2.1 — final)
**NO está embebido en este documento** (evitar duplicación — feedback GPT #10).

Mejoras vs v1:
- 19 secciones (vs 18 original)
- Pruebas funcionales: health checks HTTP, verify_db_parity, finance smoke test, claim_linter integration
- Verificación de modelos vía API (`/v1/models`) no solo config file
- DB: todas las tablas via `pg_stat_user_tables` + FK + CHECK constraints
- Git: branch, status, dirty, stash, nested .git
- Seguridad: no vuelca secrets, no ejecuta sudo, filtra api_keys de config
- Doble output: `audit_report.md` (raw) + `audit_summary.json` (structured)
- Sección 19: manual evidence (social media, IONOS, web deploy, etc.)

Mejoras R2 (v2.1):
- Output a `/tmp/` para no ensuciar git
- `systemctl --user` checks para gateway/litellm
- `crontab -l` completo (no solo backup)
- `git fetch --quiet` antes de status en ambos repos
- `stripe_sync.py` existence check (sección 7.7)
- `audit_summary.json` enriquecido: active models list, parity result, env key names, telegram status, ai_render MAX_TOKENS, structured per-subsystem

---

# PROMPT PARA CLAUDE CODE

```
Ejecuta el script openclaw_audit_script_v2.sh que está en ~/.openclaw/ (cópialo ahí primero si no está).

Cuando termine:
1. Muéstrame el contenido COMPLETO de audit_summary.json (está en /tmp/)
2. Del audit_report.md (también en /tmp/), muéstrame solo las secciones donde encuentres:
   - Errores o "NOT FOUND"
   - Conteos que difieran de lo esperado (ej: model count ≠ 23, tables ≠ 24)
   - Cualquier WARNING
3. NO hagas git add/commit de nada en /tmp/

Contexto: Estoy auditando el estado real de mi sistema OpenClaw para crear 
un Project Bible v2 que sea la fuente única de verdad.
```

---

# 10 CONTRADICCIONES A RESOLVER (con audit)

| # | Contradicción | Se resuelve con sección | Evidencia esperada |
|---|--------------|------------------------|-------------------|
| 1 | OpenClaw version v2026.3.13 vs v2026.3.24 | 1.3 | `openclaw --version` output |
| 2 | Case numbering (Miracle Withdrawal = case 3 vs Cyber Ghost = case 3) | 8.2 | manifest.json de cada export |
| 3 | TL numbering conflict (pipeline TL-05 vs optimization TL-23) | N/A — manual renumbering | Decisión: renumerar todo secuencialmente en Bible v2 |
| 4 | Orchestrator model (M2.7 vs GPT-5.2) | 2.1 + 5.3 | openclaw.json agent model + active models |
| 5 | LiteLLM model count (23 vs 18) | 5.2 + 5.3 | config count vs API count |
| 6 | Cost baseline ($50/mo vs $43/wk) | 6.6 | SpendLogs query |
| 7 | Repo (openclaw-config vs declassified-cases-pipeline) | 11.1 + 11.2 | git remote -v de ambos |
| 8 | telegram_ops.py (not executed vs implemented+conflict) | 7.5 | file exists + process + token |
| 9 | Web redesign (planned vs deployed) | Manual Evidence | **CONFIRMED LIVE by Alfredo** |
| 10 | WSL startup (.bat vs wsl.conf) | 1.1 + 1.6 | wsl.conf content + startup dir |

---

# ESTRUCTURA BIBLE v2 (actualizada con feedback Gemini)

```
# OPENCLAW — COMPLETE SYSTEM DOCUMENTATION
## Pipeline + Marketing + Meta-Planner + Finance + Infrastructure
### Version: 2.0 | Last updated: YYYY-MM-DD
### Classification: INTERNAL — DO NOT PUBLISH

1.  Project Overview (OpenClaw platform, 3 products, people, accounts)
2.  Architecture & Infrastructure (systemd, wsl.conf, services, Tailscale, Claude Code)
3.  Credentials & API Keys (inventory names + locations, sync process — NO VALUES)
4.  OpenClaw Configuration (openclaw.json, workspaces, agent lifecycle)
5.  QMD/Memory System (QMD, Bun, compaction, heartbeat, context pruning)
6.  Model Routing (complete table: who uses what, why, cost tier)
7.  LiteLLM Configuration (full model list, Codex OAuth, OpenRouter)
8.  Declassified Pipeline V9 (phases, spawn, [IMAGE:] tags, ai_render, doc_type_catalog)
9.  Marketing System (skills, scripts, runners, claim linter, weekly cycle)
10. Meta-Workflow Planner (agents, debate, costs, upgrade plan)
11. Finance Tracker (modules, Google Sheets, configs, commercialization)
12. PostgreSQL Database v2.1 (tables, constraints, db.py, parity)
13. Integrations (Veo3, DALL-E, Resend, Stripe, Google Sheets)
14. Social Media Accounts (Meta, TikTok, YouTube — current status)
15. Web Store (Supabase, React components, pages, Lovable deployment)
16. Brand Identity (logo system, colors, typography, social templates)
17. Quality Assurance (quality framework 6 pillars, claim linter)
18. Cost Tracking & Budget (baseline, spend by model, pipeline costs, budget targets) ← NEW per Gemini
19. Optimization Plan v2.2 (phases 0-9, status)
20. All Files & Paths (every workspace, script, config)
21. Git Repositories (openclaw-config + declassifiedcase, commit history)
22. Technical Lessons (renumbered TL-01 to TL-XX sequentially)
23. Design Principles (architecture + model + quality + planning)
24. Session History (all sessions chronologically)
25. Current State & Pending Items (all subsystems)
26. Operational Playbook (startup, weekly cycle, troubleshooting, backup)
27. Remote Operations (Tailscale, Termius, tmux, Claude Code dispatch)
```

---

# REGLAS BIBLE v2 (actualizadas)

1. **Solo hechos verificados** — audit_report o confirmación manual de Alfredo
2. **Estado actual, no historial** — Session History para el pasado, el resto es HOY
3. **Paths absolutos** — todo desde /home/robotin/
4. **Costos reales verificados** — SpendLogs, no estimaciones
5. **TLs renumerados** — un solo sistema TL-01 a TL-XX
6. **Dos repos documentados** — openclaw-config + declassifiedcase
7. **Contradicciones resueltas** — audit_report es verdad, no los chats
8. **NO secrets en Bible** — solo nombres de variables, nunca valores
9. **Bible = doc interno privado** — nunca publicar, nunca commitear con audit raw
10. **Separar machine-verified de manual-confirmed** — marcar cada fact con su fuente
11. **No duplicar contenido** — scripts referenciados, no copiados dentro del Bible

---

# FLUJO POST-AUDITORÍA

```
PASO 1: [AHORA] Alfredo pasa este doc + script v2 a GPT/Gemini ronda 2
PASO 2: [DESPUÉS] Si hay ajustes, aplicarlos
PASO 3: Copiar script a ~/.openclaw/openclaw_audit_script_v2.sh
PASO 4: Ejecutar via Claude Code con el prompt de arriba
PASO 5: Compartir audit_summary.json + errores del report con este chat
PASO 6: Cruzar 32 gaps + 10 contradicciones contra evidencia real
PASO 7: Producir Bible v2
PASO 8: Alfredo revisa y aprueba
PASO 9: Claude Code: git add declassified_project_bible_v2.md && git commit
PASO 10: De aquí en adelante, cada sesión actualiza el Bible como primer paso
```

---

*Fin del plan v2.*
