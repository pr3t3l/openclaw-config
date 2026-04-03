# WORKFLOW BIBLE — PLATFORM & ROBOTIN (CEO)
## Documento técnico autoritativo
### Last verified: 2026-03-29 (audit v2.1)
### Sources: 2 extractions + 10 library files + Bible v2 §2-7,§19,§22,§26,§27 + system audit

> **Source tags:** `[AUDIT]` = machine-verified 2026-03-29. `[EXT-OPT]` = optimization sprint.
> `[EXT-INFRA]` = infrastructure setup. `[SYSCONF]` = system_configuration_complete.
> `[MEM]` = memory_architecture_complete. `[BIBLE]` = from Project Bible v2.

---

# 1. PURPOSE & CONTEXT

OpenClaw is the multi-agent AI orchestration platform that runs everything else. The Platform workflow covers: infrastructure (WSL, services, networking), the CEO agent (Robotin), memory system, model routing, LiteLLM proxy, credentials, optimization, remote ops, and git.

**Robotin** is Alfredo's personal AI assistant and system orchestrator. He handles daily tasks, system admin, cost monitoring, finance tracking, and routes complex tasks to specialized agents or tools.

**Bot:** @Robotin1620_Bot (Telegram)
**Agent:** CEO (id: main)
**Workspace:** `~/.openclaw/workspace/` `[AUDIT]`

### Relationship to other workflows

| Workflow | Platform's role |
|----------|----------------|
| **Declassified Pipeline** | Platform provides the runtime (OpenClaw gateway, LiteLLM, Telegram bindings) |
| **Marketing System** | Platform provides model routing, DB (PostgreSQL), API keys |
| **Meta-Workflow Planner** | Platform provides dedicated bot binding + model routing |
| **Finance Tracker** | Finance is a SKILL inside the CEO workspace — runs through Robotin |

---

# 2. TIMELINE — INFRASTRUCTURE EVOLUTION

| Date | Event | Source |
|------|-------|--------|
| 2026-02-23 | OpenClaw initial install (v2026.2.22-2), LiteLLM setup, 16 models | [EXT-INFRA] |
| 2026-02-23 | Dual Windows/WSL install conflict discovered and resolved | [EXT-INFRA] |
| 2026-02-23 | Security audit: 🟢 GREEN (no services exposed to internet) | [EXT-INFRA] |
| 2026-02-23 | .bat in Windows Startup for WSL keepalive (first auto-start solution) | [EXT-INFRA] |
| 2026-02-23 | Model tier strategy designed (oc-aliases → later renamed to descriptive names) | [EXT-INFRA] |
| 2026-02-23 | Boot loop discovered: Gemini Flash hallucinating model names (oc-thinking-v35 to v43) | [EXT-INFRA] |
| 2026-02-24 | GOG (Google) OAuth configured for prettelv1@gmail.com | [EXT-INFRA] |
| 2026-02-24 | Two permission layers discovered (models.providers + agents.defaults.models) | [EXT-INFRA] |
| 2026-02-24 | GPT-5.2 medium set as default model | [EXT-INFRA] |
| 2026-03-01 | Tailscale installed, serve configured, remote dashboard working | [EXT-INFRA] |
| 2026-03-04 | OpenClaw v2026.3.2, models reorganized (18 with descriptive names) | [EXT-INFRA] |
| 2026-03-18 | OpenClaw v2026.3.13, multi-agent setup (CEO + Declassified) | [EXT-OPT] |
| 2026-03-23 | Optimization Plan v2.2 created (9 phases), cross-reviewed by GPT+Gemini | [EXT-OPT] |
| 2026-03-23 | Phases 0-6A executed in massive 12+ hour session | [EXT-OPT] |
| 2026-03-23 | Phase 0: git repo, archive dead agents/workspaces, snapshot 295MB | [EXT-OPT] |
| 2026-03-23 | Phase 1: Cost baseline measured ($43.36/week, 96% GPT-5.2) | [EXT-OPT] |
| 2026-03-23 | Phase 2: Gemini key renewed (18→21 models) | [EXT-OPT] |
| 2026-03-23 | Phase 3: QMD 2.0.1 + Bun installed, 3-layer memory configured | [EXT-OPT] |
| 2026-03-23 | Phase 4: CEO heartbeat 999999m → 30m | [EXT-OPT] |
| 2026-03-23 | Phase 5: Sessions/compaction/memoryFlush configured | [EXT-OPT] |
| 2026-03-23 | Phase 6A: OpenRouter (M2.7 + Step 3.5 + Kimi) added, 21→24 models | [EXT-OPT] |
| 2026-03-23 | LiteLLM auth crisis: master_key vs OpenClaw conflict. Resolution: no auth on dashboard | [EXT-OPT] |
| 2026-03-27 | Codex OAuth configured: openai-codex/gpt-5.4 as primary for ALL 3 agents | [EXT-OPT] |
| 2026-03-27 | ChatGPT subscription OAuth for LiteLLM (chatgpt-gpt54) | [EXT-OPT] |
| 2026-03-28 | wsl.conf fixed (duplicate [boot] sections), WSL.lnk + boot hook solution | [EXT-OPT] |
| 2026-03-29 | start_all_services.sh created (60 lines, idempotent) | [AUDIT] |
| 2026-03-29 | OpenClaw v2026.3.24 confirmed | [AUDIT] |

---

# 3. INFRASTRUCTURE `[AUDIT]`

### WSL Configuration

```
[boot]
systemd=true
command = service ssh start; sudo -u robotin bash /home/robotin/.openclaw/start_all_services.sh >> /home/robotin/logs/startup.log 2>&1
```

**NOTE:** Despite `systemd=true`, the audit found systemd may not always initialize as PID 1. Services start reliably via `start_all_services.sh` regardless. `[AUDIT]`

### Services

| Service | Port | Startup method | Health check |
|---------|------|---------------|--------------|
| PostgreSQL 16 | 5432 | `sudo service postgresql start` | `pg_isready` |
| LiteLLM | 4000 | `nohup litellm --config config.yaml` | `curl :4000/health` |
| OpenClaw Gateway | 18789 | `nohup openclaw gateway` | `curl :18789` |

**Master startup:** `bash ~/.openclaw/start_all_services.sh` (60 lines, idempotent) `[AUDIT]`

### Auto-start chain

```
Windows boot → WSL.lnk (in shell:startup) → WSL starts
WSL boot → wsl.conf [boot] command → start_all_services.sh
start_all_services.sh → PostgreSQL → LiteLLM → OpenClaw Gateway
```

Sudoers: `/etc/sudoers.d/robotin-services` allows passwordless PostgreSQL start. `[AUDIT]`

### Logs

`~/logs/`: startup.log, openclaw-gateway.log `[AUDIT]`

---

# 4. OPENCLAW CONFIGURATION

### Version: 2026.3.24 (cff6dc9) `[AUDIT]`

**Binary:** `/home/robotin/.npm-global/bin/openclaw`
**Config:** `~/.openclaw/openclaw.json`

### Key sections of openclaw.json `[AUDIT]`

| Section | What it controls |
|---------|-----------------|
| `meta` | Version tracking |
| `auth.profiles` | Codex OAuth profile |
| `models.providers.litellm` | Available models with capabilities |
| `agents.defaults` | Default model, fallbacks, compaction, heartbeat, timeouts, subagents |
| `agents.list` | 3 agents: main (CEO), declassified, planner |
| `tools` | Agent-to-agent communication, sessions visibility |
| `bindings` | Telegram account → agent mapping |
| `channels.telegram` | 3 accounts: default, declassified, planner |
| `gateway` | Port 18789, loopback, Tailscale serve, auth token, controlUi origins |
| `memory` | QMD backend config |
| `session` | dmScope, maintenance, pruning |
| `skills.entries` | goplaces, nano-banana-pro, openai-image-gen, openai-whisper-api, sag |
| `hooks` | boot-md, bootstrap-extra-files, command-logger, session-memory |

### Two permission layers (BOTH must be updated together) `[EXT-INFRA]`

1. `models.providers.litellm.models` — declares available models with capabilities (22 models)
2. `agents.defaults.models` — authorizes models for agent use (format: `litellm/model-id`)

**If you add a model to LiteLLM but forget to add it to both layers in openclaw.json, the agent can't use it.**

---

# 5. CEO AGENT — ROBOTIN `[AUDIT]`

### Core files

| File | Purpose | Lines |
|------|---------|-------|
| AGENTS.md | Orchestrator instructions: role, memory, meta-planner routing, red lines, communication style | ~120 |
| SOUL.md | Personality: "Be genuinely helpful, not performatively helpful." Alf-specific rules | ~30 |
| IDENTITY.md | Name: Robotin 🤖, Role: CEO, Model: openai-codex/gpt-5.4, Born: 2026-02-22 | ~15 |
| USER.md | User info: Alfredo Pretel | ? |
| MEMORY.md | Long-term curated memory: system state, projects, decisions, rules | ~30 |
| TOOLS.md | Tools reference | ~20 |
| HEARTBEAT.md | Every 30m (08:00-23:00): check pending tasks, update MEMORY.md periodically | ~15 |

### Session startup sequence (from AGENTS.md) `[AUDIT]`

1. Read `SOUL.md` — who you are
2. Read `USER.md` — who you're helping
3. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context
4. If in main session: read `MEMORY.md`

### Meta-Planner integration `[AUDIT]`

CEO routes "Planifica:" or "Plan:" prefixed messages → `start_plan.sh` → Fase A (intake → gap finder → scope framer) → Gate #1.

**⚠️ STALE:** CEO AGENTS.md says "NO ejecutes Fase B o C — aún no están implementadas." Git shows they ARE implemented (commits ff75f65, 30ebae2). Need to update. `[AUDIT]`

### Finance Tracker Skill
The finance-tracker skill is auto-discovered by OpenClaw from `workspace/skills/finance-tracker/SKILL.md`. It handles:
- Receipt photos and text expense entries
- Budget monitoring and payment reminders
- Daily cashflow calculations
- Tax deduction tracking (Airbnb)
- Bank CSV and PDF reconciliation
- Batch receipt processing (Walmart w-mt.co links)

Reference added to AGENTS.md for explicit routing of finance-related messages.

### Memory directory `[AUDIT]`

`workspace/memory/`: 8 daily notes (2026-03-20 to 2026-03-28) + lessons_summary.md

### ⚠️ Stale info in CEO files `[AUDIT]`

| File | Wrong | Correct |
|------|-------|---------|
| AGENTS.md | OpenClaw v2026.3.13 | v2026.3.24 |
| AGENTS.md | 21 models | 24 models |
| AGENTS.md | M2.7 primary | openai-codex/gpt-5.4 primary |
| AGENTS.md | workspace-declassified → declassified-cases-pipeline | unified in openclaw-config |
| MEMORY.md | Same stale info | Same corrections needed |

---

# 6. MEMORY SYSTEM `[MEM]` `[AUDIT]`

### 3-Layer architecture `[MEM]`

| Layer | What | Where | Loaded when |
|-------|------|-------|-------------|
| Daily notes | Raw logs of what happened | `workspace/memory/YYYY-MM-DD.md` | Every session (today + yesterday) |
| Long-term memory | Curated decisions, preferences, key facts | `workspace/MEMORY.md` | Main sessions only |
| QMD search | Semantic search across all memory files | Via QMD 2.0.1 | On demand (direct chats only) |

### QMD Configuration `[AUDIT]`

- **QMD:** 2.0.1, **Bun:** 1.3.11
- Backend: qmd, searchMode: search
- Paths: `workspace/memory/*.md`
- Update: 5m interval, 15s debounce, onBoot: true
- Limits: 6 results, 700 chars/snippet, 4s timeout
- Scope: default deny, allow direct chats only

### Compaction `[AUDIT]`

```
mode: safeguard
memoryFlush.enabled: true
softThresholdTokens: 6000
```

When approaching compaction, agents flush context to `memory/YYYY-MM-DD.md`.

### Session management `[AUDIT]`

```
dmScope: per-channel-peer
maintenance.mode: enforce
pruneAfter: 14d
maxEntries: 200
contextPruning.mode: cache-ttl
```

---

# 7. MODEL ROUTING — COMPLETE TABLE `[AUDIT]`

### Orchestrators (openclaw.json)

| Agent | Primary | Fallback 1 | Fallback 2 | Heartbeat |
|-------|---------|------------|------------|-----------|
| CEO | openai-codex/gpt-5.4 | litellm/gpt52-medium | litellm/minimax-m27 | 30m |
| Declassified | openai-codex/gpt-5.4 | litellm/gpt52-medium | litellm/minimax-m27 | 120m |
| Planner | openai-codex/gpt-5.4 | litellm/gpt52-medium | litellm/minimax-m27 | 5m |

### Pipeline skills (model_routing.json)

thinking → chatgpt-gpt54-thinking ($0), medium/none → chatgpt-gpt54 ($0), render → claude-sonnet-4-6 (direct API)

### Planner skills (models.json)

All agents → claude-sonnet46. Debate uses opus46 + chatgpt-gpt54 + gemini31pro-none.

### Marketing skills

Default LiteLLM model. Quality reviewer → claude-sonnet46 (GPT timed out at 75K+ context).

---

# 8. LITELLM — 24 MODELS `[AUDIT]`

**Version:** 1.81.14
**Config:** `~/.config/litellm/config.yaml`
**Env:** `~/.config/litellm/litellm.env` (6 keys: 4 API + UI_USERNAME + UI_PASSWORD)
**Dashboard:** http://127.0.0.1:4000/ui/ (has auth via litellm.env) `[AUDIT]`
**DB:** `postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db`

All 24 models were active at time of audit. See Bible v2 §7 for complete model list.

### Codex OAuth `[EXT-OPT]`

- OpenAI Pro subscription ($200/mo) provides $0/token for all GPT models
- Orchestrators: `openai-codex/gpt-5.4` direct OAuth
- Pipeline/planner skills: `chatgpt-gpt54` via LiteLLM device-code OAuth
- **NOTE:** `chatgpt/gpt-5.4-pro` (thinking variant) is NOT available on Pro subscription. Only `chatgpt/gpt-5.4` works. `[EXT-OPT]`

---

# 9. CREDENTIALS `[AUDIT]`

**Master:** `~/.openclaw/.env` — 21 keys (see Bible v2 §3 for full list)
**LiteLLM:** `~/.config/litellm/litellm.env` — 6 keys
**Files:** `~/.openclaw/credentials/` — 7 files (OAuth tokens, Telegram ACLs)
**Sync:** `~/.openclaw/sync_keys.sh` (10 lines) — copies .env → litellm.env

**IMPORTANT:** litellm.env only needs API keys + UI creds. Extra variables (TELEGRAM_*, GATEWAY_*) crash LiteLLM. (TL-35) `[EXT-OPT]`

### Google Sheets credentials (Finance Tracker)

| File | Path | Purpose |
|------|------|---------|
| Google Sheets OAuth token | `~/.openclaw/credentials/finance-tracker-token.json` | Finance tracker read/write |
| Google OAuth client config | `~/.openclaw/credentials/google-client.json` | OAuth flow for Sheets |

---

# 10. OPTIMIZATION PLAN v2.2 `[AUDIT]`

**File:** `~/.openclaw/OPTIMIZATION_PLAN.md` (523 lines) `[AUDIT]`

| Phase | Description | Status |
|-------|------------|--------|
| 0 | Backup & Protection | ✅ Complete (2026-03-23) |
| 1 | Cost Baseline | ✅ Tracking active — GATE pending (need 3-7 days data) |
| 2 | Renew Gemini | ✅ Complete |
| 3 | Memory (CEO) | ✅ QMD configured — memoryFlush partially blocked |
| 4 | Heartbeat | ✅ CEO 30m — isolatedSession needs gateway ≥v2026.4 |
| 5 | Sessions & Compaction | ✅ Complete |
| 6A | OpenRouter setup | ✅ M2.7 + Step 3.5 + Kimi active |
| 6B | A/B test M2.7 | ⏳ Pending cost baseline data |
| 7 | Compaction benchmark | ⏳ Pending |
| 8 | Reduce AGENTS.md | ⏳ Pending A/B results |
| 9 | Meta-planner integration | ⏳ Future |

### Cost baseline (measured) `[EXT-OPT]`

- Week of 2026-03-23: $43.36 (96% = GPT-5.2 medium at $41.49)
- Post-Codex OAuth: GPT calls now $0/token → expected massive reduction
- Week of 2026-03-23 (from LiteLLM SpendLogs): $74.13 `[AUDIT]`

**NOTE:** The $43.36 and $74.13 figures may cover different periods or include different API keys. Need clean post-OAuth week to establish new baseline. `[INCONCLUSIVE]`

---

# 11. REMOTE OPERATIONS `[AUDIT]`

### Tailscale

- Device: pretel-laptop
- Tailnet: tail600a27.ts.net
- Gateway controlUi origin: `https://pretel-laptop.tail600a27.ts.net` `[AUDIT]`
- `tailscale serve`: **NOT configured** at time of audit `[AUDIT]`

### Termius (phone)

SSH via Tailscale IP → dispatch Claude Code tasks remotely

### Claude Code `[AUDIT]`

- Version: 2.1.86
- Workspace scope: `~/.openclaw/`
- Used for all implementation tasks

### tmux

Pattern: `tmux new -s <name>` / `tmux attach -t <name>`
No active sessions at time of audit. `[AUDIT]`

---

# 12. GIT REPOSITORIES `[AUDIT]`

### openclaw-config (primary)

- Remote: `github.com/pr3t3l/openclaw-config`
- Branch: main
- Contains: ALL workspaces, marketing-system, products, configs
- Status at audit: 11 dirty files (5 modified, 6 untracked)
- No nested .git in workspace/ ✅

### declassifiedcase (web store)

- Remote: `github.com/pr3t3l/declassifiedcase`
- Branch: main
- Status at audit: clean

### declassified-cases-pipeline (DEPRECATED)

Old separate repo. All content now in openclaw-config/workspace-declassified/.

---

# 13. BACKUP `[AUDIT]`

- `safe_backup.sh`: **NOT FOUND** `[AUDIT]`
- Cron backup job: **NOT configured** (only finance tracker crons exist)
- Last manual backup: 2026-03-23, 295MB tar.gz in Windows Downloads `[EXT-OPT]`

**⚠️ This is a gap.** Need to recreate backup script + cron.

---

# 14. TELEGRAM `[AUDIT]`

| Account | Bot | Agent | Token var | Policy |
|---------|-----|-------|-----------|--------|
| default | @Robotin1620_Bot | CEO (main) | TELEGRAM_BOT_TOKEN | pairing, streaming: partial |
| declassified | @APVDeclassified_bot | Declassified | TELEGRAM_DECLASSIFIED_TOKEN | pairing, streaming: partial |
| planner | @Super_Workflow_Creator_bot | Planner | TELEGRAM_PLANNER_TOKEN | pairing, streaming: partial |

**Planned 4th bot:** Marketing ops (telegram_ops.py exists but uses shared CEO token — needs dedicated TELEGRAM_OPS_TOKEN via BotFather). `[AUDIT]`

Agent-to-agent: enabled between main ↔ declassified only. Planner is isolated. `[AUDIT]`

---

# 15. KEY DESIGN DECISIONS

| # | Decision | Why | Source |
|---|----------|-----|--------|
| 1 | Two permission layers for models | Prevents accidental model use. Must update both. | [EXT-INFRA] |
| 2 | GPT-5.2 medium → Codex OAuth gpt-5.4 | Codex OAuth = $0/token. Massive cost savings | [EXT-OPT] |
| 3 | Tailscale serve (not port forwarding) | OpenClaw rejects bind:0.0.0.0. Tailscale is native integration | [EXT-INFRA] |
| 4 | No master_key on LiteLLM | Breaks OpenClaw auth. Dashboard runs without auth (localhost-only) | [EXT-OPT] |
| 5 | Descriptive model names (not OC aliases) | oc-default → gpt52-medium. Clearer for humans | [EXT-INFRA] |
| 6 | 3-layer memory (daily + long-term + QMD search) | Each layer serves different retention need | [MEM] |
| 7 | compaction: safeguard + memoryFlush | Agents save context before compaction happens | [EXT-OPT] |
| 8 | WSL.lnk + wsl.conf boot hook (not .bat keepalive) | More reliable than .bat, native WSL solution | [EXT-OPT] |
| 9 | CEO workspace isolation | NEVER modify workspace-declassified/ from CEO context | [BIBLE] |
| 10 | No mini/nano models for content or QA | Quality floor. Budget models only for mechanical tasks | [BIBLE] |

---

# 16. TECHNICAL LESSONS (Platform-specific)

| ID | Lesson | Source |
|----|--------|--------|
| TL-11 | OpenClaw doesn't resolve ${ENV_VARS} in apiKey | [EXT-OPT] |
| TL-12 | LiteLLM dashboard: UI_USERNAME/UI_PASSWORD in litellm.env | [AUDIT] |
| TL-15 | LiteLLM model names ≠ provider names | [EXT-INFRA] |
| TL-20 | WSL auto-start: WSL.lnk + wsl.conf boot hook | [AUDIT] |
| TL-22 | `echo >>` for .env creates duplicates — edit with nano | [EXT-OPT] |
| TL-23 | isolatedSession + lightContext need gateway ≥v2026.4 | [EXT-OPT] |
| TL-24 | CEO MEMORY.md must be CEO-specific — never copy from Declassified | [EXT-OPT] |
| TL-28 | Git: identity Alfredo Pretel, email 30666965+pr3t3l@users.noreply.github.com | [EXT-INFRA] |
| TL-33 | LiteLLM Prisma duplicate model warning (not blocking) | [AUDIT] |
| TL-35 | litellm.env: only API keys + UI creds. Extra vars crash LiteLLM | [EXT-OPT] |
| PL-10 | Boot loop: Gemini Flash hallucinated model names in loop, burning credits | [EXT-INFRA] |
| PL-11 | When LiteLLM can't bind to port, silently falls back to random high port | [EXT-OPT] |
| PL-12 | chatgpt/gpt-5.4-pro NOT available on ChatGPT Pro via Codex | [EXT-OPT] |

---

# 17. CURRENT STATE `[AUDIT]`

### Working ✅
- OpenClaw v2026.3.24 (gateway HTTP 200) `[AUDIT]`
- LiteLLM 1.81.14 (24/24 models active) `[AUDIT]`
- PostgreSQL accepting connections `[AUDIT]`
- start_all_services.sh (60 lines, idempotent) `[AUDIT]`
- WSL.lnk + wsl.conf boot hook `[AUDIT]`
- Codex OAuth active for all 3 agents `[AUDIT]`
- QMD 2.0.1 + Bun 1.3.11 configured `[AUDIT]`
- Claude Code 2.1.86 installed `[AUDIT]`
- Git repo (openclaw-config) on GitHub `[AUDIT]`
- **Finance Tracker skill deployed and operational** (9 modules + batch receipts) `[CHANGES]`
- **Google Sheets "Robotin Finance 2026" connected** (7 tabs + Cashflow_Ledger) `[CHANGES]`
- **AI batch classification for unknown merchants** `[CHANGES]`
- **87+ auto-categorization rules in rules.json** `[CHANGES]`

### Issues ⚠️
- **CEO AGENTS.md + MEMORY.md stale** — version, model count, model primary, repo name all wrong `[AUDIT]`
- **Tailscale serve NOT configured** — was assumed configured `[AUDIT]`
- **safe_backup.sh NOT FOUND** — no automated backup `[AUDIT]`
- **cost_baseline.md NOT FOUND** — mentioned in optimization plan but doesn't exist `[AUDIT]`
- **verify_db_parity.py broken** — needs psycopg2 `[AUDIT]`
- **11 dirty files in git** `[AUDIT]`
- **workspace-content-distribution + workspace-image-generator** still in root (should be archived) `[AUDIT]`
- **GOG_KEYRING_PASSWORD duplicated in .env** `[AUDIT]`

---

# 18. PENDING ITEMS (prioritized)

| Priority | Item | Blocker |
|----------|------|---------|
| 🔴 | Update CEO AGENTS.md + MEMORY.md (stale info) | None |
| 🔴 | Clean git: commit or gitignore 11 dirty files | None |
| 🔴 | Install psycopg2 for verify_db_parity.py | `pip install psycopg2-binary` |
| 🔴 | Recreate safe_backup.sh + configure cron | None |
| 🟡 | Archive stale workspaces (content-distribution, image-generator) | None |
| 🟡 | Fix GOG_KEYRING_PASSWORD duplicate in .env | None |
| 🟡 | Configure Tailscale serve (`tailscale serve --bg 18789`) | None |
| 🟡 | Optimization Phase 6B: A/B test M2.7 as CEO model | Need post-OAuth cost data |
| 🟡 | Optimization Phase 7: Compaction benchmark | After A/B test |
| 🟡 | Optimization Phase 8: Reduce AGENTS.md size | After compaction |
| 🟡 | Create dedicated TELEGRAM_OPS_TOKEN | BotFather |
| 🟢 | Optimization Phase 9: Meta-planner integration | Future |
| 🔴 | Configure finance tracker cron jobs | None |
| 🟡 | Add finance-tracker reference to CEO AGENTS.md | None |

---

# 19. DIRECTORY OVERVIEW `[AUDIT]`

```
~/.openclaw/                              — 612 MB total
├── .env                                  — 21 API keys (master)
├── openclaw.json                         — Platform config
├── start_all_services.sh                 — Service startup (60 lines)
├── sync_keys.sh                          — Key sync (10 lines)
├── OPTIMIZATION_PLAN.md                  — v2.2 (523 lines)
├── credentials/                          — 7 files (OAuth, Telegram ACLs)
├── workspace/                            — CEO agent (8.8 MB)
│   ├── AGENTS.md, SOUL.md, IDENTITY.md, etc.
│   ├── memory/                           — Daily notes + lessons
│   └── skills/finance-tracker/           — Finance Tracker skill
├── workspace-declassified/               — Pipeline agent (460 MB)
├── workspace-meta-planner/               — Planner agent (2.6 MB)
├── workspace-content-distribution/       — ⚠️ STALE
├── workspace-image-generator/            — ⚠️ STALE
├── marketing-system/                     — 15 skills + 24 scripts (712 KB)
├── marketing-hub/                        — Legacy marketing
├── products/misterio-semanal/            — Product data + weekly runs
├── shared/scripts/                       — spawn_core.py (pinned copy)
├── agents/                               — Agent registry
├── browser/                              — Chromium config
├── media/                                — Inbound media
├── telegram/                             — Telegram state
└── .git/                                 — openclaw-config repo
```

---

**END OF WORKFLOW BIBLE — PLATFORM & ROBOTIN**

*Consolidates: 2 extractions (infrastructure setup 2026-02-23, optimization sprint 2026-03-23), system_configuration_complete.md, memory_architecture_complete.md, OPTIMIZATION_PLAN.md, 7 CEO workspace files, and Project Bible v2 §2-7,§19,§22,§26,§27. Verified against system audit 2026-03-29.*
