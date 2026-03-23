# OpenClaw Optimization Master Plan v2.2
## Sistema Agéntico de Alfredo Pretel — Arquitectura a Largo Plazo
### Autor: Claude Opus 4.6 | Fecha: 2026-03-23
### Revisiones: v1→v2 (feedback GPT+Gemini), v2→v2.1 (4 fixes GPT), v2.1→v2.2 (2 blockers GPT)
### Status: APPROVED IN PRINCIPLE — pending backup fix validation and memory-source validation

---

## EXECUTION TRACKER

### Fase 0: Backup y Protección
- [x] Workspaces muertos archivados a ~/openclaw-archive/
- [x] Agentes muertos archivados (9 agentes legacy removidos)
- [x] .gitignore endurecido (secrets, sessions, identity, media excluidos)
- [x] Config subida a github.com/pr3t3l/openclaw-config (caba56b)
- [x] Auth tokens verificados y excluidos de git
- [x] openclaw.json verificado sin secrets
- [x] sync_keys.sh creado (no existía)
- [x] LiteLLM reiniciado y verificado (gpt52 respondiendo)
- [x] OpenClaw gateway reiniciado y verificado (@Robotin1620_Bot responde)
- [x] Snapshot local (tar.gz con .env, solo almacenamiento local) — 2026-03-23, 295MB en Downloads

### Fase 1: Medir Línea Base de Costos
- [x] Reconciliar LiteLLM /spend/logs — /spend/logs requiere PostgreSQL (no disponible). Habilitado JSON logs + x-litellm-response-cost headers como alternativa. 2026-03-23
- [x] Medir heartbeat overhead (tokens/día) — sin datos aún, tracking iniciado. 2026-03-23
- [x] Documentar cost_baseline.md — creado workspace/cost_baseline.md con estructura y precios. 2026-03-23
- [ ] **GATE: Mínimo 3-7 días de datos CEO + 2 corridas Declassified** (earliest: 2026-03-30)

### Fase 2: Renovar Gemini Key
- [ ] Generar nueva key en aistudio.google.com
- [ ] Actualizar .env + sync_keys.sh + restart LiteLLM
- [ ] Verificar modelos Gemini responden en LiteLLM

### Fase 3: Memoria — Solo en CEO
- [ ] Crear estructura memory/ en workspace CEO
- [ ] Crear MEMORY.md inicial
- [ ] Instalar Bun + QMD
- [ ] **GATE: Validar config keys contra docs oficiales**
- [ ] Configurar QMD en openclaw.json
- [ ] Configurar memory flush (pre-compaction)
- [ ] Probar: pedir al CEO "busca en memoria qué lessons learned tenemos"
- [ ] **GATE (Obsidian): Test WSL↔Windows symlink permisos antes de adoptar**

### Fase 4: Optimizar Heartbeat
- [ ] **GATE: Verificar opciones reales en docs (isolatedSession, lightContext)**
- [ ] CEO: Configurar isolatedSession + lightContext + frecuencia 30m (NO 0m)
- [ ] Confirmar si CEO tiene cron jobs o wakeups que dependan de heartbeat
- [ ] Solo si no hay dependencias → bajar a 0m
- [ ] Declassified: Mantener heartbeat condicional via HEARTBEAT.md (ya funciona)

### Fase 5: Sesiones y Compaction
- [ ] **GATE: Verificar keys exactas contra docs oficiales**
- [ ] Configurar session scope, maintenance, pruning
- [ ] Verificar compaction mode safeguard activo

### Fase 6: OpenRouter + A/B Test M2.7 en CEO
- [ ] 6A: Crear cuenta OpenRouter, obtener API key
- [ ] 6A: Agregar OPENROUTER_API_KEY a .env
- [ ] 6A: Agregar M2.7, Step 3.5 Flash, Kimi K2.5 a LiteLLM config
- [ ] 6A: Restart LiteLLM, verificar nuevos modelos responden
- [ ] 6B: Documentar 1 semana de CEO con GPT-5.2 (línea base de Fase 1)
- [ ] 6B: Cambiar CEO a M2.7, documentar 1 semana
- [ ] 6B: Comparar: costo/día, calidad respuesta, fallos
- [ ] **GATE: Resultados documentados antes de tocar Declassified**

### Fase 7: Benchmark Compaction + Failover
- [ ] Benchmark compaction: Step 3.5 Flash vs Gemini Flash Lite vs actual
- [ ] Configurar compaction.model con ganador
- [ ] Configurar failover chain

### Fase 8: Reducir AGENTS.md
- [ ] **GATE: Confirmar que orchestrator model mantiene skill adherence con AGENTS.md reducido**
- [ ] Reducir de 461 a ~80-100 líneas (router + spawn preamble)
- [ ] Probar primero en CEO
- [ ] Solo migrar a Declassified con evidencia

### Fase 9: Meta-Workflow Planner (proyecto separado)
- [ ] Diseño detallado (documento separado)
- [ ] Implementación (proyecto separado)

---

## PRINCIPIOS RECTORES

1. **Declassified V9 es intocable.** Toda optimización se prueba primero en CEO.
2. **Medir antes de optimizar.** No prometer ahorros sin línea base real.
3. **Validar config contra docs.** Ningún snippet JSON se aplica sin verificar keys reales.
4. **Una variable a la vez.** No meter múltiples cambios simultáneos.
5. **Gates antes de avanzar.** Si una fase falla, se itera ahí — no se salta.
6. **Git repo boundaries.** `~/.openclaw/` → openclaw-config (Claude Code scope). `workspace/` y `workspace-declassified/` → NUNCA hacer git add/commit/push ahí. Esos repos los maneja Alfredo. Crear archivos en workspace/ está OK, pero sin operaciones git.

---

## DETALLE POR FASE

### FASE 0: BACKUP Y PROTECCIÓN ✅ COMPLETADA

**Pendiente: Snapshot local**
```bash
tar czf /mnt/c/Users/robot/Downloads/openclaw-backup-$(date +%Y%m%d).tar.gz \
  --exclude='agents/*/sessions' \
  --exclude='node_modules' \
  --exclude='workspace-declassified/cases/exports' \
  ~/.openclaw/
```

**Nota sobre snapshot:** Este backup es de configuración, no de disaster-recovery completo. Las sessions se excluyen porque son regenerables y pesadas. Si se necesita restore operacional completo, hacer un tar sin exclusiones.

**Backup automático con protección de concurrencia (mirror repo, NO árbol activo):**

⚠️ **Fix v2.2:** El script v2.1 tenía un bug crítico: rsync copiaba a staging pero el commit salía del árbol activo, dejando la race condition intacta. Ahora el commit sale del mirror.

```bash
cat > ~/.openclaw/safe_backup.sh << 'SCRIPT'
#!/bin/bash
LOCKFILE="/tmp/openclaw-git-backup.lock"
MIRROR="/home/robotin/openclaw-backup-mirror"

# Si hay lock activo, salir
[ -f "$LOCKFILE" ] && exit 0
touch "$LOCKFILE"

# Snapshot a mirror repo (commit sale de AQUÍ, no del árbol activo)
mkdir -p "$MIRROR"
rsync -a --delete \
  --exclude='agents/*/sessions' \
  --exclude='node_modules' \
  --exclude='.env' \
  --exclude='agents/*/agent/auth*.json' \
  --exclude='identity/' \
  --exclude='media/' \
  --exclude='memory/*.sqlite' \
  --exclude='browser/' \
  --exclude='canvas/' \
  --exclude='completions/' \
  --exclude='delivery-queue/' \
  --exclude='devices/' \
  --exclude='logs/' \
  --exclude='subagents/' \
  --exclude='credentials/' \
  /home/robotin/.openclaw/ "$MIRROR/"

# Commitear DESDE el mirror, no desde el árbol activo
cd "$MIRROR"
if [ ! -d .git ]; then
  git init
  git remote add origin https://github.com/pr3t3l/openclaw-config.git
fi
git add -A
if ! git diff --cached --quiet; then
  git commit -m "auto: backup $(date +%Y-%m-%d-%H%M)"
  git push origin main --force 2>/dev/null
fi

rm -f "$LOCKFILE"
SCRIPT

chmod +x ~/.openclaw/safe_backup.sh
```

Crontab (cada 6 horas):
```
0 */6 * * * /home/robotin/.openclaw/safe_backup.sh
```

---

### FASE 1: MEDIR LÍNEA BASE DE COSTOS
**Status: TRACKING ACTIVE — waiting for data (gate: 2026-03-30)**
**Duración: Mínimo 3-7 días de recolección + 2 corridas Declassified**

Sin datos reales, cualquier promesa de ahorro es ficción.

**1.1 — Reconciliar costos LiteLLM**
```bash
curl -s http://127.0.0.1:4000/spend/logs | python3 -m json.tool | tail -50
curl -s http://127.0.0.1:4000/spend/logs?group_by=model | python3 -m json.tool
```

**1.2 — Medir heartbeat overhead**
```bash
grep -c "heartbeat" /tmp/litellm.log 2>/dev/null || echo "No log available"
```

**1.3 — Documentar en workspace CEO**

Crear `~/.openclaw/workspace/cost_baseline.md`:
```markdown
# Cost Baseline — Measured [START_DATE] to [END_DATE]

## LiteLLM Total Spend
- Period: [X] days
- Total: $___

## Spend by model (daily average)
- gpt52-medium (orchestrator CEO): $___/day
- gpt52-medium (orchestrator Declassified): $___/day
- claude-sonnet46 (spawn direct): $___/case

## Heartbeat overhead
- CEO frequency: every ___
- Declassified frequency: every 2 min
- Estimated CEO heartbeat cost/day: $___
- Estimated Declassified heartbeat cost/day: $___

## Per-case cost (from manifest.json, last 2-3 cases)
- Case 1 (slug): $___
- Case 2 (slug): $___
- Case 3 (slug): $___
- Average: $___

## Orchestrator overhead per case
- Estimated from LiteLLM: $___

## TOTAL monthly estimate: $___

## Breakdown
- Orchestration: ___% 
- Content generation: ___%
- Rendering: ___%
- Images: ___%
```

**GATE:** No avanzar a Fase 6 (modelos) sin estos números completos.

---

### FASE 2: RENOVAR GEMINI KEY
**Status: GO NOW (5 minutos)**

```bash
# 1. https://aistudio.google.com/apikey → generar nueva key
# 2. Actualizar .env
nano ~/.openclaw/.env  # Cambiar GEMINI_API_KEY y NANO_BANANA_API_KEY

# 3. Sync + restart
~/.openclaw/sync_keys.sh
source ~/litellm-venv/bin/activate && pkill -f litellm && sleep 3
nohup litellm --config ~/.config/litellm/config.yaml --port 4000 > /tmp/litellm.log 2>&1 &
sleep 15 && deactivate

# 4. Verificar
curl -s http://127.0.0.1:4000/models | python3 -m json.tool | grep gemini
```

---

### FASE 3: MEMORIA — Solo en CEO
**Status: GO NOW (CEO only) — NO TOCAR workspace-declassified**

⚠️ **Todos los snippets JSON deben validarse contra https://docs.openclaw.ai/reference/memory-config antes de aplicar.**

**3.1 — Estructura de memoria CEO**
```bash
mkdir -p ~/.openclaw/workspace/memory

cat > ~/.openclaw/workspace/MEMORY.md << 'EOF'
# Robotin CEO — Long-Term Memory

## Identity
- Owner: Alfredo Pretel (Alf)
- Languages: Spanish, English
- Agent name: Robotin 🤖

## Active Projects
- Declassified Cases Pipeline: V9, production, @APVDeclassified_bot
- Meta-Workflow Planner: Design phase

## Technical Preferences
- Python requests FAILS in WSL >30s. ALWAYS use curl via subprocess.
- Budget-conscious. Always mention cost implications.
- Direct communication. No filler.

## Key Decisions
- [se irá llenando automáticamente]
EOF
```

**3.2 — Instalar QMD**
```bash
which bun || (curl -fsSL https://bun.sh/install | bash && source ~/.bashrc)
bun install -g https://github.com/tobi/qmd
which qmd
```

**3.3 — Configurar QMD en openclaw.json**

⚠️ VALIDAR KEYS CONTRA DOCS PRIMERO.

```jsonc
{
  "memory": {
    "backend": "qmd",
    "citations": "auto",
    "qmd": {
      "includeDefaultMemory": true,
      "searchMode": "search",
      "update": { "interval": "5m", "debounceMs": 15000, "onBoot": true, "waitForBootSync": false },
      "limits": { "maxResults": 6, "maxSnippetChars": 700, "timeoutMs": 4000 },
      "scope": {
        "default": "deny",
        "rules": [{ "action": "allow", "match": { "chatType": "direct" } }]
      },
      "paths": [
        { "name": "lessons", "path": "/home/robotin/.openclaw/workspace-declassified/cases/config", "pattern": "*.json" }
      ]
    }
  }
}
```

⚠️ **Fix v2.2 — JSON indexing es HIPÓTESIS, no hecho confirmado:**
La documentación de OpenClaw `memory_search` describe indexación sobre Markdown (`MEMORY.md`, `memory/**/*.md`). QMD `paths[]` permite archivos arbitrarios, pero `memory_get` está limitado a Markdown. Los `*.json` en paths son una hipótesis a validar.

**Plan de validación (ejecutar en Fase 3):**
1. Configurar paths con `*.json` como arriba
2. Probar: `memory_search` con query sobre lessons learned
3. Si retorna resultados de JSON → funciona, mantener
4. Si NO retorna → convertir `lessons_learned.json` a `lessons_summary.md` (resumen Markdown canónico) y cambiar pattern a `*.md`

**Qué se indexa (definición explícita):**
- ✅ CONFIRMADO: `workspace/MEMORY.md` (long-term CEO memory)
- ✅ CONFIRMADO: `workspace/memory/*.md` (daily notes CEO)
- ⚠️ HIPÓTESIS: `workspace-declassified/cases/config/*.json` (lessons learned, config) — validar en Fase 3
- ❌ NO se indexan: sessions, exports, scripts, HTML/PDF renders
- ❌ NO se indexa: workspace-declassified/MEMORY.md (memoria de otro agente, evitar contaminación)

**Fallback si JSON no se indexa:** Crear `~/.openclaw/workspace/memory/lessons_summary.md` con resumen curado de lessons_learned.json en formato Markdown. Actualizar manualmente o via script después de cada caso.

**3.4 — Memory flush (pre-compaction)**

⚠️ VALIDAR contra docs: ubicación exacta dentro de agents.defaults.

```jsonc
{
  "agents": {
    "defaults": {
      "compaction": {
        "reserveTokensFloor": 20000,
        "memoryFlush": {
          "enabled": true,
          "softThresholdTokens": 6000,
          "systemPrompt": "Session nearing compaction. Write critical context to memory/YYYY-MM-DD.md NOW.",
          "prompt": "Write lasting notes to memory/YYYY-MM-DD.md. Reply NO_REPLY if nothing to store."
        }
      }
    }
  }
}
```

**3.5 — Obsidian (VALIDATE FIRST)**

Gate obligatorio:
1. Crear symlink Windows → WSL
2. Escribir desde Obsidian, leer desde WSL
3. Escribir desde WSL, leer desde Obsidian
4. **Si falla → NO usar Obsidian. Editar con nano/VS Code desde WSL.**

---

### FASE 4: OPTIMIZAR HEARTBEAT
**Status: VALIDATE FIRST**

⚠️ **Cambio v2.1:** NO desactivar heartbeat CEO ciegamente. OpenClaw usa heartbeat para cron jobs y wakeups en sesión principal. Apagarlo puede romper funcionalidad silenciosamente.

**Estrategia revisada:**
1. Verificar en docs: `isolatedSession`, `lightContext` existen y reducen costo
2. CEO: `isolatedSession: true` + `lightContext: true` + `every: "30m"` 
3. Confirmar que CEO no tiene cron jobs dependientes de heartbeat
4. **Solo si confirmado sin dependencias** → bajar a `0m`
5. Declassified: mantener heartbeat condicional via HEARTBEAT.md (ya funciona)

---

### FASE 5: SESIONES Y COMPACTION
**Status: VALIDATE FIRST**

⚠️ Verificar keys exactas contra docs antes de aplicar.

Intención:
- Session scope: per-channel-peer para DMs
- Maintenance: habilitar, ~200 sesiones max, purgar ~14 días idle
- Pruning: cache-ttl mode
- Compaction: mode safeguard + memory flush (Fase 3.4)

---

### FASE 6: OPENROUTER + A/B TEST M2.7 EN CEO
**Status: LATER (semana 2+)**

**Cambio v2.1:** Fase 6 ahora incluye OpenRouter setup PRIMERO (6A), luego A/B test (6B). No puedes testear M2.7 sin tener OpenRouter configurado.

**6A — Habilitar OpenRouter**
1. Crear cuenta https://openrouter.ai/
2. Agregar `OPENROUTER_API_KEY` a .env
3. Agregar modelos a LiteLLM config:
   - `minimax-m27` → openrouter/minimax/minimax-m2.7
   - `step35-flash` → openrouter/stepfun/step-3.5-flash
   - `kimi-k25` → openrouter/moonshotai/kimi-k2.5
4. Sync keys, restart LiteLLM, verificar

**6B — A/B Test**
1. Ya tienes 1 semana de datos CEO con GPT-5.2 (de Fase 1)
2. Cambiar CEO a M2.7
3. Documentar 1 semana: costo/día, calidad, fallos
4. Comparar y decidir

**GATE:** Resultados documentados antes de considerar migrar Declassified.

---

### FASE 7: BENCHMARK COMPACTION + FAILOVER
**Status: LATER**

Benchmark con prompts reales: Step 3.5 Flash vs Gemini Flash Lite vs modelo actual.
Métricas: fidelidad de resumen, costo por 100 compactions, latencia.
Configurar `compaction.model` y failover chain con ganadores.

---

### FASE 8: REDUCIR AGENTS.MD
**Status: LATER**

GATE: Confirmar que orchestrator model mantiene skill adherence con AGENTS.md reducido.
Probar primero en CEO. Solo migrar a Declassified con evidencia.

---

### FASE 9: META-WORKFLOW PLANNER
**Status: LATER — proyecto separado, no contaminar estabilización**

---

## MODELO ROUTING (Estado actual → Objetivo)

### Intocables (unanimidad 3/3 revisores)
| Tarea | Modelo | Status |
|-------|--------|--------|
| AI Render (HTML→PDF) | Claude Sonnet 4.6 (direct API) | NO CAMBIAR |
| Narrative Architect | Claude Sonnet 4.6 (direct API) | NO CAMBIAR |
| Quality Auditor | Claude Sonnet 4.6 (direct API) | NO CAMBIAR |
| TTS Script Writer | Claude Sonnet 4.6 (direct API) | NO CAMBIAR |
| Art Director | Claude Sonnet 4.6 (direct API) | NO CAMBIAR |
| Experience Designer | Claude Sonnet 4.6 (direct API) | NO CAMBIAR |
| Production Engine | Claude Sonnet 4.6 (direct API) | NO CAMBIAR |
| Image Generation | DALL-E 3 (direct API) | NO CAMBIAR |

### En evaluación (requieren A/B test)
| Tarea | Actual | Candidato | Status |
|-------|--------|-----------|--------|
| CEO Orchestrator | GPT-5.2 medium | MiniMax M2.7 | BENCHMARK (Fase 6) |
| Declassified Orchestrator | GPT-5.2 medium | MiniMax M2.7 | LATER (solo si CEO valida) |
| Compaction model | (default del orchestrator) | Step 3.5 Flash / Gemini Lite | BENCHMARK (Fase 7) |
| Memory embeddings | N/A | Gemini Embedding / local GGUF | CONFIGURAR (Fase 3) |

### Tabla de referencia de modelos
| Modelo | In $/MTok | Out $/MTok | Intelligence | Velocidad | Fortaleza |
|--------|-----------|------------|-------------|-----------|-----------|
| Claude Opus 4.6 | $15.00 | $75.00 | 53 | ~30 t/s | Deep reasoning |
| Claude Sonnet 4.6 | $3.00 | $15.00 | ~45 | ~60 t/s | HTML render, creatividad |
| GPT-5.2 | $2-5 | $10-15 | 57 | ~50 t/s | Versátil |
| GPT-5 Mini | $0.15 | $0.60 | ~25 | ~100 t/s | Ultra barato |
| MiniMax M2.7 | $0.30 | $1.20 | 50 | ~60 t/s | 97% skill adherence, agentic |
| Kimi K2.5 | $0.60 | $3.00 | 47 | ~42 t/s | Multimodal, Agent Swarm |
| Step 3.5 Flash | $0.10 | $0.30 | 38 | ~143 t/s | Ultra rápido, ultra barato |
| Gemini 3.1 Pro | $1.25+ | $10+ | 57 | ~50 t/s | 1M context |
| Gemini 3.1 Flash Lite | Free | Free | ~30 | ~100 t/s | Gratis |

---

## RIESGOS IDENTIFICADOS

| # | Riesgo | Fuente | Mitigación | Status |
|---|--------|--------|------------|--------|
| R1 | Config JSON con keys incorrectas | GPT | Validar contra docs | ⏳ |
| R2 | Degradación silenciosa al cambiar modelos contenido | GPT | NO migrar Art/Prod/Exp | ✅ Eliminado |
| R3 | Ahorro prometido sin línea base | GPT | Fase 1 medición | ⏳ |
| R4 | Symlink WSL↔Windows permisos | Gemini | Test gate Obsidian | ⏳ |
| R5 | Git backup corrompe archivo en escritura | GPT+Gemini | Mirror repo, commit desde snapshot | ✅ Corregido v2.2 |
| R6 | Demasiadas variables simultáneas | GPT | Ejecución por fases con gates | ✅ Diseño |
| R7 | OpenRouter dependencia prematura | GPT | Movido a Fase 6 (semana 2+) | ✅ Corregido |
| R8 | Compaction model sin benchmark | GPT | Benchmark obligatorio Fase 7 | ⏳ |
| R9 | spawn_debate.py secuencial timeout | Gemini | Paralelo obligatorio | ⏳ (Fase 9) |
| R10 | Prompt caching invalidation | Claude | Mantener archivos estables | ⏳ |
| R11 | Heartbeat CEO 0m rompe cron/wakeups | GPT v2.1 | isolatedSession+lightContext primero | ✅ Corregido v2.1 |
| R12 | Línea base insuficiente (snapshot vs período) | GPT v2.1 | Mínimo 3-7 días + 2 corridas | ✅ Corregido v2.1 |
| R13 | JSON indexing en memory_search no confirmado | GPT v2.2 | Hipótesis a validar; fallback a .md | ✅ Corregido v2.2 |
| R14 | Backup script v2.1 commiteaba árbol activo, no snapshot | GPT v2.2 | Mirror repo approach | ✅ Corregido v2.2 |

---

## CHECKSUMS DE VALIDACIÓN (después de cada fase)

- [ ] `openclaw gateway status` → running
- [ ] `curl http://127.0.0.1:4000/health` → ok
- [ ] @Robotin1620_Bot responde en Telegram
- [ ] @APVDeclassified_bot responde con estado correcto
- [ ] `git -C ~/.openclaw status` → clean
- [ ] Memory search funciona (post Fase 3)

---

## USO DE CLAUDE CODE PARA EJECUCIÓN

Claude Code (`~/.openclaw/ → claude`) puede ejecutar directamente:
- Edición de openclaw.json (validación incluida)
- Edición de MEMORY.md, AGENTS.md
- Ejecución de scripts (sync_keys.sh, safe_backup.sh)
- Git commits y pushes
- Verificación de LiteLLM health
- Lectura de docs de OpenClaw para validación de config keys

**Workflow recomendado:**
1. Planificar en este chat (Claude.ai) — decisiones estratégicas
2. Ejecutar en Claude Code (terminal WSL) — cambios de archivos, scripts, git
3. Actualizar tracker en este archivo → git push

---

*Plan v2.2 — 2026-03-23. Revisado con GPT-5.2 (8.5/10 en v2.1, "near-final pending 2 blockers") y Gemini 3.1 Pro. Fixes v2.1: orden Fase 6/7, backup snapshot, heartbeat, línea base. Fixes v2.2: backup mirror repo (commit ya no sale del árbol activo), JSON indexing marcado como hipótesis con fallback a Markdown.*
