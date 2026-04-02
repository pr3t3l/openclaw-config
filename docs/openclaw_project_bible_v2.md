# OPENCLAW — COMPLETE SYSTEM DOCUMENTATION
## Pipeline + Marketing + Meta-Planner + Finance + Infrastructure
### Version: 2.1 | Last verified: 2026-04-02 (audit v2.2)
### Classification: INTERNAL — DO NOT PUBLISH

---

> **Verification policy:** Each fact is tagged with its source.
> `[AUDIT]` = machine-verified via audit script 2026-03-29.
> `[MANUAL]` = confirmed directly by Alfredo.
> `[INCONCLUSIVE]` = audit data contradictory or incomplete — needs re-verification.
> Facts without tags are architectural decisions or design documentation.

---

# TABLE OF CONTENTS

1. Project Overview
2. Architecture & Infrastructure
3. Credentials & API Keys
4. OpenClaw Configuration
5. QMD / Memory System
6. Model Routing
7. LiteLLM Configuration
8. Declassified Pipeline V9
9. Marketing System
10. Meta-Workflow Planner
11. Finance Tracker
12. PostgreSQL Database v2.1
13. Integrations
14. Social Media Accounts
15. Web Store
16. Brand Identity
17. Quality Assurance
18. Cost Tracking & Budget
19. Optimization Plan v2.2
20. All Files & Paths
21. Git Repositories
22. Technical Lessons Learned
23. Design Principles
24. Session History
25. Current State & Pending Items
26. Operational Playbook
27. Remote Operations

---

# 1. PROJECT OVERVIEW

## What we're building

**OpenClaw** is a multi-agent AI orchestration platform running on WSL Ubuntu. It operates via 3 Telegram bots, each with a dedicated agent and workspace:

| Bot | Agent | What it does |
|-----|-------|-------------|
| @Robotin1620_Bot | **CEO (Robotin)** | Personal assistant, system orchestrator, finance tracking, and marketing operations |
| @APVDeclassified_bot | **Declassified** | Mystery case creation: from concept to finished PDF product |
| @Super_Workflow_Creator_bot | **Planner** | Idea validation and workflow planning via multi-model debate |

### Products & Systems

1. **Declassified Cases** (declassified.shop) — weekly AI-generated mystery detective game sold as digital download. Managed by the Declassified agent.

2. **Marketing System** — automated content generation with 3 layers:
   - **Strategy Layer** — market analysis, buyer personas, brand strategy, SEO, channel strategy (run once, updated periodically)
   - **Marketing Weekly** — scripts, ads, emails, calendar, quality review (run per case/week)
   - **Growth Intelligence** — metrics interpretation, diagnosis, pattern learning (run after metrics collected)
   
   All marketing runs via scripts in `~/.openclaw/marketing-system/`. Planned to be operated via a dedicated Telegram ops bot (Phase 4A code exists, needs dedicated token — currently not operational).

3. **Finance Tracker** — personal expense tracking, budget monitoring, tax deduction tracking for Airbnb. Runs as a skill inside the CEO bot (@Robotin1620_Bot). Data stored in Google Sheets.

4. **Meta-Workflow Planner** — takes raw ideas through multi-model analysis and produces buildable workflow plans. Managed by the Planner agent.

## Key People & Accounts

- **Owner:** Alfredo Pretel (Alf)
- **Target audience:** Americans in USA (English-first, Spanish secondary)
- **Store:** declassified.shop (React + Vite + Supabase + Stripe) `[MANUAL]`
- **GitHub:** pr3t3l/openclaw-config (unified repo), pr3t3l/declassifiedcase (web store) `[AUDIT]`
- **Stripe:** acct_1SqwSeAcsyW8mQQC (Declassified Case)
- **Email domain:** declassified.shop (verified in Resend) `[MANUAL]`
- **Business email:** support@declassified.shop (IONOS Mail Basic) `[MANUAL]`

## Pricing

- Single case (e.g., Linda Oward): $12.00 USD
- Pack 4 cases: $59.00 USD
- Future target: $19.99 per case

---

# 2. ARCHITECTURE & INFRASTRUCTURE

## Hardware & OS

- Dedicated laptop running Windows with WSL Ubuntu `[AUDIT]`
- Username: robotin (WSL) / robot (Windows)
- Home: /home/robotin/
- Windows Downloads: /mnt/c/Users/robot/Downloads/

## WSL Configuration `[AUDIT]`

```
[boot]
systemd=true
command = service ssh start; sudo -u robotin bash /home/robotin/.openclaw/start_all_services.sh >> /home/robotin/logs/startup.log 2>&1
```

**NOTE:** Despite `systemd=true` in wsl.conf, the audit detected that systemd may not always initialize as PID 1. Services start reliably via `start_all_services.sh` regardless. `[AUDIT]`

## Services Running `[AUDIT]`

| Service | Port | How it starts | Health check |
|---------|------|--------------|--------------|
| PostgreSQL 16 | 5432 | `sudo service postgresql start` (via startup script) | `pg_isready` |
| LiteLLM Proxy | 4000 | `nohup litellm --config config.yaml` (via startup script) | `curl :4000/health` |
| OpenClaw Gateway | 18789 | `nohup openclaw gateway` (via startup script) | `curl :18789` |

All three managed by `~/.openclaw/start_all_services.sh` (60 lines, idempotent). `[AUDIT]`

| Google Sheets API | — | Finance tracker data store ("Robotin Finance 2026") |

## Auto-Start `[AUDIT]`

- `WSL.lnk` in Windows Startup folder (`shell:startup`) launches WSL
- `/etc/wsl.conf` boot command runs `start_all_services.sh` on WSL boot
- Sudoers file `/etc/sudoers.d/robotin-services` allows passwordless PostgreSQL start

## Logs `[AUDIT]`

Location: `~/logs/`
- `startup.log` — service startup output
- `openclaw-gateway.log` — gateway runtime
- `litellm.log` — LiteLLM runtime (separate: `~/.config/litellm/` or `~/logs/`)

## Telegram Bots `[AUDIT]`

| Bot | Token Variable | Agent | What it handles |
|-----|---------------|-------|----------------|
| @Robotin1620_Bot | TELEGRAM_BOT_TOKEN | CEO (main) | Personal assistant, finance tracking, marketing operations, system admin |
| @APVDeclassified_bot | TELEGRAM_DECLASSIFIED_TOKEN | Declassified | Case pipeline: narrative → render → package → distribute |
| @Super_Workflow_Creator_bot | TELEGRAM_PLANNER_TOKEN | Planner | Idea analysis, multi-model debate, workflow planning |

**NOTE:** A 4th bot for marketing operations (telegram_ops.py) was planned but uses the shared CEO token — needs its own bot via BotFather before it can run.

## Disk Usage `[AUDIT]`

| Directory | Size |
|-----------|------|
| ~/.openclaw/ (total) | 612 MB |
| workspace/ (CEO) | 8.8 MB |
| workspace-declassified/ | 460 MB |
| workspace-meta-planner/ | 2.6 MB |
| marketing-system/ | 712 KB |
| ~/declassifiedcase/ (web store) | 393 MB |

---

# 3. CREDENTIALS & API KEYS

## Master file: `~/.openclaw/.env` — 21 keys `[AUDIT]`

| Variable | Purpose |
|----------|---------|
| ANTHROPIC_API_KEY | Direct API for Sonnet renders (ai_render.py) |
| ELEVENLABS_API_KEY | TTS via OpenClaw skill |
| GATEWAY_AUTH_TOKEN | OpenClaw gateway auth |
| GEMINI_API_KEY | Gemini models via LiteLLM |
| GOG_KEYRING_PASSWORD | Google OAuth keyring (⚠️ DUPLICATED in .env — fix) |
| GOOGLE_API_KEY | Veo 3 video generation |
| GOPLACES_API_KEY | GoPlaces skill |
| LITELLM_API_KEY | LiteLLM proxy auth (sk-litellm-local) |
| NANO_BANANA_API_KEY | Image generation skill |
| OPENAI_API_KEY | OpenAI direct (fallback) |
| OPENAI_IMAGE_GEN_KEY | DALL-E skill |
| OPENAI_WHISPER_KEY | Whisper transcription skill |
| OPENROUTER_API_KEY | OpenRouter (M2.7, Step 3.5, Kimi) |
| RESEND_API_KEY | Email sending |
| SAG_API_KEY | SAG skill |
| STRIPE_API_KEY | Stripe live payments |
| STRIPE_WEBHOOK_SECRET | Stripe webhook verification |
| TELEGRAM_BOT_TOKEN | CEO bot (@Robotin1620_Bot) |
| TELEGRAM_DECLASSIFIED_TOKEN | Pipeline bot (@APVDeclassified_bot) |
| TELEGRAM_PLANNER_TOKEN | Planner bot (@Super_Workflow_Creator_bot) |

## LiteLLM env: `~/.config/litellm/litellm.env` — 6 keys `[AUDIT]`

ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, UI_USERNAME, UI_PASSWORD

## Credential files: `~/.openclaw/credentials/` `[AUDIT]`

- `finance-tracker-token.json` — Google Sheets OAuth token
- `google-client.json` — Google OAuth client
- `moltbook-robotin.json` — Moltbook credential
- `telegram-declassified-allowFrom.json` — Declassified bot ACL
- `telegram-default-allowFrom.json` — CEO bot ACL
- `telegram-pairing.json` — Telegram pairing config
- `telegram-planner-allowFrom.json` — Planner bot ACL

**NOTE:** `google_client_secret.json` is MISSING. File is named `google-client.json` instead. `[AUDIT]`

## Key sync: `~/.openclaw/sync_keys.sh` (10 lines) `[AUDIT]`

Copies keys from `.env` → `litellm.env`. Run after any key rotation, then restart LiteLLM.

**IMPORTANT:** `litellm.env` only needs 4 API keys + 2 UI creds. DO NOT symlink to full `.env` — LiteLLM crashes on unrecognized variables.

---

# 4. OPENCLAW CONFIGURATION

## Version: 2026.3.24 (cff6dc9) `[AUDIT]`

Config file: `~/.openclaw/openclaw.json`

## Agents `[AUDIT]`

| ID | Name | Workspace | Primary Model | Heartbeat |
|----|------|-----------|--------------|-----------|
| main | CEO | workspace/ | openai-codex/gpt-5.4 | 30m (08:00-23:00) |
| declassified | Declassified | workspace-declassified/ | openai-codex/gpt-5.4 | 120m (06:00-02:00) |
| planner | Planner | workspace-meta-planner/ | openai-codex/gpt-5.4 | 5m (08:00-23:00) |

All agents share the same fallback chain: `[litellm/gpt52-medium, litellm/minimax-m27]` `[AUDIT]`

## Two permission layers (BOTH must be updated together)

1. `models.providers.litellm.models` — declares available models with capabilities
2. `agents.defaults.models` — authorizes models for agent use (format: `litellm/model-id`)

22 models authorized in `agents.defaults.models` (21 via LiteLLM + 1 openai-codex). `[AUDIT]`

## Gateway `[AUDIT]`

```
port: 18789
mode: local
bind: loopback
auth: token (${GATEWAY_AUTH_TOKEN})
controlUi.allowedOrigins: ["https://pretel-laptop.tail600a27.ts.net"]
trustedProxies: ["100.64.0.0/10"]
tailscale.mode: serve
```

## Agent-to-Agent communication `[AUDIT]`

Enabled between `main` and `declassified` only. Planner is isolated.

## Tools & Skills configured in openclaw.json `[AUDIT]`

- `sessions.visibility: all`
- Skills: goplaces, nano-banana-pro, openai-image-gen, openai-whisper-api, sag
- TTS: ElevenLabs (voice: CwhRBWXzGAHq8TQ4Fs17, model: eleven_multilingual_v2)
- Hooks: boot-md, bootstrap-extra-files, command-logger, session-memory (all enabled)

## Workspace files (standard per workspace) `[AUDIT]`

Each workspace contains: AGENTS.md, HEARTBEAT.md, IDENTITY.md, MEMORY.md, SOUL.md, TOOLS.md, USER.md, memory/ directory.

---

# 5. QMD / MEMORY SYSTEM

## QMD 2.0.1 + Bun 1.3.11 `[AUDIT]`

Paths: `/home/robotin/.bun/bin/qmd`, `/home/robotin/.bun/bin/bun`

## Memory configuration (openclaw.json) `[AUDIT]`

```
backend: qmd
searchMode: search
paths: [workspace/memory/*.md] (ceo-memory)
update: interval 5m, debounceMs 15000, onBoot true
limits: maxResults 6, maxSnippetChars 700, timeoutMs 4000
scope: default deny, allow direct chats only
```

## Compaction `[AUDIT]`

```
mode: safeguard
memoryFlush.enabled: true
softThresholdTokens: 6000
```

When approaching compaction, agents flush critical context to `memory/YYYY-MM-DD.md`.

## Session management `[AUDIT]`

```
dmScope: per-channel-peer
maintenance.mode: enforce
pruneAfter: 14d
maxEntries: 200
contextPruning.mode: cache-ttl
```

## CEO memory files `[AUDIT]`

- `MEMORY.md` — curated long-term decisions and system state
- `memory/` — daily notes (8 files from 2026-03-20 to 2026-03-28)
- `memory/lessons_summary.md` — pipeline lessons (read-only reference)

**WARNING:** CEO MEMORY.md and AGENTS.md contain stale info: version says v2026.3.13, model count says 21, mentions M2.7 as primary. These must be updated. `[AUDIT]`

### Fix required: CEO AGENTS.md + MEMORY.md

The following lines in CEO workspace files are stale and must be updated:

**In AGENTS.md (~line 954):**
- CHANGE: `OpenClaw v2026.3.13` → `OpenClaw v2026.3.24`
- CHANGE: `21 models` → `24 models`
- CHANGE: `Git repos: ~/.openclaw/ → openclaw-config, workspace-declassified/ → declassified-cases-pipeline` → `Git repo: ~/.openclaw/ → openclaw-config (unified)`
- REMOVE: `Model: MiniMax M2.7 via OpenRouter (primary)`
- ADD: `Model: openai-codex/gpt-5.4 (primary), fallbacks: gpt52-medium, minimax-m27`

**In MEMORY.md (~line 1005):**
- CHANGE: `OpenClaw v2026.3.13` → `OpenClaw v2026.3.24`
- CHANGE: `21 models` → `24 models`
- FIX: Git repo reference to unified openclaw-config

---

# 6. MODEL ROUTING

## Orchestrator routing (openclaw.json) `[AUDIT]`

| Agent | Primary | Fallback 1 | Fallback 2 |
|-------|---------|------------|------------|
| CEO | openai-codex/gpt-5.4 | litellm/gpt52-medium | litellm/minimax-m27 |
| Declassified | openai-codex/gpt-5.4 | litellm/gpt52-medium | litellm/minimax-m27 |
| Planner | openai-codex/gpt-5.4 | litellm/gpt52-medium | litellm/minimax-m27 |

## Pipeline routing (model_routing.json) `[AUDIT]`

| Task Type | Model | Cost |
|-----------|-------|------|
| Thinking (narrative, experience, production, QA) | chatgpt-gpt54-thinking | $0 (Codex OAuth) |
| Medium (art direction, image gen, QA depth) | chatgpt-gpt54 | $0 (Codex OAuth) |
| None (distribution, assembly) | chatgpt-gpt54 | $0 (Codex OAuth) |
| Document rendering | claude-sonnet-4-6 (direct API) | ~$0.03-0.10/doc |
| Image generation | nano-banana-2-gemini (primary), dall-e-3 (fallback) | $0.02/image, $0.08/HD |

## Planner routing (models.json) `[AUDIT]`

All agents use `claude-sonnet46` via LiteLLM.

| Debate Level | Models | Judge | Red Team |
|-------------|--------|-------|----------|
| Simple | claude-sonnet46 | none | none |
| Complex | claude-opus46, chatgpt-gpt54 | claude-sonnet46 | none |
| Critical | claude-opus46, chatgpt-gpt54, gemini31pro-none | claude-opus46 | claude-opus46 |

## Marketing routing

- Quality reviewer: Claude Sonnet 4.6 via LiteLLM (claude-sonnet46)
- All other marketing skills: use LiteLLM default model

## Model tiers

- **Tier S reasoning:** Gemini 3.1 Pro, GPT-5.4, Claude Opus 4.6
- **Tier A agentic/value:** MiniMax M2.7, Kimi K2.5, Step 3.5 Flash
- **Tier B budget:** Gemini 3.1 Lite, GPT-5 Mini
- **ABSOLUTE RULE: NO mini or nano models for content generation or QA**

---

# 7. LITELLM CONFIGURATION

## Version: 1.81.14 `[AUDIT]`

- Config: `~/.config/litellm/config.yaml`
- Env: `~/.config/litellm/litellm.env`
- Dashboard: http://127.0.0.1:4000/ui/ (auth: UI_USERNAME/UI_PASSWORD from litellm.env) `[AUDIT]`
- Database: `postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db`

## Models: 24 configured, 24 active `[AUDIT]`

| # | Model Name | Provider | Route |
|---|-----------|----------|-------|
| 1 | gpt52-none | OpenAI | LiteLLM |
| 2 | gpt52-medium | OpenAI | LiteLLM |
| 3 | gpt52-thinking | OpenAI | LiteLLM |
| 4 | gpt52-xhigh | OpenAI | LiteLLM |
| 5 | gpt53-codex | OpenAI | LiteLLM |
| 6 | gpt5-mini | OpenAI | LiteLLM |
| 7 | gpt41 | OpenAI | LiteLLM |
| 8 | gemini31pro-none | Google | LiteLLM |
| 9 | gemini31pro-medium | Google | LiteLLM |
| 10 | gemini31pro-thinking | Google | LiteLLM |
| 11 | gemini31lite-none | Google | LiteLLM |
| 12 | gemini31lite-low | Google | LiteLLM |
| 13 | gemini31lite-medium | Google | LiteLLM |
| 14 | gemini31lite-high | Google | LiteLLM |
| 15 | claude-sonnet46 | Anthropic | LiteLLM |
| 16 | claude-sonnet46-thinking | Anthropic | LiteLLM |
| 17 | claude-opus46 | Anthropic | LiteLLM |
| 18 | claude-opus46-thinking | Anthropic | LiteLLM |
| 19 | minimax-m27 | OpenRouter | LiteLLM |
| 20 | step35-flash | OpenRouter (StepFun) | LiteLLM |
| 21 | kimi-k25 | OpenRouter (Moonshot) | LiteLLM |
| 22 | dall-e-3 | OpenAI | LiteLLM |
| 23 | chatgpt-gpt54 | ChatGPT OAuth | LiteLLM |
| 24 | chatgpt-gpt54-thinking | ChatGPT OAuth | LiteLLM |

## Codex OAuth `[AUDIT]`

- OpenAI Pro subscription ($200/mo) `[MANUAL]`
- Orchestrators use `openai-codex/gpt-5.4` direct OAuth
- Pipeline skills use `chatgpt-gpt54` (model: chatgpt/gpt-5.4) via LiteLLM OAuth
- Thinking variant: `chatgpt-gpt54-thinking` (model: chatgpt/gpt-5.4-pro)
- Result: $0/token for all GPT usage

## OpenRouter models `[AUDIT]`

- minimax-m27 → openrouter/minimax/minimax-m2.7
- step35-flash → openrouter/stepfun/step-3.5-flash
- kimi-k25 → openrouter/moonshotai/kimi-k2.5

---

# 8. DECLASSIFIED PIPELINE V9

## Pipeline Phases (10 total)

1. **Init** — start_new_case.sh
2. **Narrative Architect** — case-plan.json + clue_catalog.json
3. **Art Director** — art_briefs.json (POI portraits ONLY) + scene_descriptions.json
4. **Experience Designer** — experience_design.json (emotional beats + detective annotations)
5. **Production Engine** — _content.md per document, one envelope at a time
6. **Playthrough QA** — simulated player walkthrough + benchmark scoring
7. **Image Generator** — POI portraits only, 4-6 per case
8. **AI Render** — ai_render.py: Claude Sonnet → HTML → Chromium → PDF
9. **Package + Validate** — merge PDFs per envelope, validate_final.py
10. **Distribution** — ZIP → Google Drive → Telegram

## Skills: 11 `[AUDIT]`

art-director, content-distribution, document-designer, experience-designer, image-generator, lessons-learned, nano-banana-2-gemini, narrative-architect, production-engine, quality-auditor, tts-script-writer

## Cases: 6 exports `[AUDIT]`

| # | Slug | Status | Notes |
|---|------|--------|-------|
| 1 | the-last-livestream | distributed ✅ | First case |
| 2 | the-influencer-who-erased-herself | distributed ✅ | Needs V9 re-render |
| 3 | medication-that-cures-too-well | stopped ⛔ | Original version, replaced by GPT re-run |
| 4 | medication-that-cures-too-well-gpt | distributed ✅ | "The Miracle Withdrawal" |
| 5 | cyber-ghost | paused ⏸️ | Missing: inject photos + merge + distribute |
| 6 | asalto-cronometrado | initialized 🆕 | New case, only initialized |

**NOTE:** Manifest.json for all cases returns `case_name: unknown` and `cost: unknown` — the manifest schema doesn't capture these fields reliably. `[AUDIT]`

## ai_render.py `[AUDIT]`

- Location: `~/.openclaw/workspace-declassified/cases/scripts/ai_render.py` (679 lines)
- DEFAULT_MODEL: `claude-sonnet-4-6` (direct Anthropic API, NOT via LiteLLM)
- MAX_TOKENS: 32000
- curl --max-time: 600 seconds
- subprocess timeout: 650 seconds (must exceed curl timeout)
- Two-tier system: Tier 1 (text docs) = short system prompt, Tier 2 (visual docs) = full design system prompt
- **RULE:** Background MUST be white/light — NEVER dark backgrounds

## [IMAGE:] tag system

Production Engine embeds visual placement tags in `_content.md`:
- Format: `[IMAGE: detailed description of what to render]`
- Every document gets at least 1 tag
- POI sheets get `[IMAGE: POI portrait...]` per POI
- Social media docs get phone/browser mockups
- ai_render.py reads these and creates visuals in HTML/CSS

## Spawn architecture `[AUDIT]`

AGENTS.md uses: `sessions_spawn` (2 occurrences), `spawn_agent` (11), `spawn_narrative` (5)

**Known issue:** `sessions_spawn` makes phases 2-7 cost tracking invisible in manifest.json. Only ai_render.py (phase 8) logs costs correctly.

## Config files `[AUDIT]`

- `design_system.json` — visual design rules
- `doc_type_catalog.json` — extensible document type specs (interrogation transcript, official memo, newspaper, social media, etc.)
- `lessons_learned.json` — pipeline lessons
- `model_routing.json` — per-phase model assignments
- `template_registry.json` — legacy (replaced by doc_type_catalog)
- `tier_definitions.json` — case complexity tiers

## Scripts `[AUDIT]`

ai_render.py, benchmark_scoring.py, cost_tracker.py, fix_case_plan_schema.py, inject_poi_photos.py, merge_clue_catalogs.py, normalize_output.py, spawn_agent.py, spawn_images.py, spawn_narrative.py, start_new_case.sh, validate_art.py (has known false-positive bug), validate_content.py, validate_experience.py, validate_final.py, validate_narrative.py, validate_placeholders.py

---

# 9. MARKETING SYSTEM

## Overview

Fully automated marketing content generation system with 3 operational layers, all managed via scripts in `~/.openclaw/marketing-system/`. The CEO bot (Robotin) currently triggers marketing runs manually. A dedicated Telegram ops bot was coded (Phase 4A) to allow command-driven operation, but is NOT operational due to a token conflict.

### The 3 Marketing Layers

| Layer | Purpose | Runner | Gates | Frequency |
|-------|---------|--------|-------|-----------|
| **Strategy** | Market analysis, buyer personas, brand strategy, SEO, channel strategy | `strategy_runner.py` | S1, S2 | Once per product, updated quarterly |
| **Marketing Weekly** | Scripts, ads, emails, calendar, quality review per case | `marketing_runner.py` | M1, M2 | Weekly per active case |
| **Growth Intelligence** | Metrics interpretation, root cause diagnosis, pattern learning | `growth_runner.py` | G1 | Weekly after metrics collected |

## Skills: 15 `[AUDIT]`

**Strategy Layer (5):** market-analysis, buyer-persona, brand-strategy, seo-architecture, channel-strategy
**Marketing Weekly (5):** script-generator, ad-copy-generator, email-generator, calendar-generator, quality-reviewer
**Growth Intelligence (3):** metrics-interpreter, diagnosis-agent, learning-extractor
**Additional (2):** video-prompt-generator, strategy-report-generator

## Scripts: 24 `[AUDIT]`

**Runners:** strategy_runner.py, marketing_runner.py, growth_runner.py, runtime_orchestrator.py
**DB:** db.py (926 lines), migrate_json_to_db.py, verify_db_parity.py
**QA:** claim_linter.py (316 lines — integrated in marketing_runner.py at phase M-lint) `[AUDIT]`
**Integrations:** case_to_brief.py, generate_marketing_videos.py, generate_marketing_images.py, send_marketing_emails.py, stripe_sync.py, telegram_ops.py (758 lines), telegram_sender.py
**Runtime:** llm_caller.py, preflight_check.py, state_lock_manager.py, artifact_validator.py, rollback_executor.py, gate_handler.py, metrics_calculator.py, experiment_manager.py, pattern_promoter.py

## Strategy v2 (Approved)

- 6 buyer segments: couples_date_night, game_night_hosts, true_crime_solo, gift_buyers, family_detectives, educators
- 105 SEO keywords across 5 pillar pages
- 25 creative angles
- 4-tier competitor matrix
- Segment × trigger × channel matrix

## Weekly runs: W14, W15, W16, W17 `[AUDIT]`

(Bible v1 said W16 was missing — it exists.)

## Telegram Operations Bot (planned 4th bot) `[AUDIT]`

- File: `telegram_ops.py` (758 lines) — EXISTS
- Process: NOT RUNNING
- TELEGRAM_OPS_TOKEN: NOT configured — currently uses shared TELEGRAM_BOT_TOKEN causing getUpdates conflict with CEO bot
- **Status:** Code implemented (Phase 4A), but not operationally safe. Needs dedicated bot token via BotFather.

**Phase 4A (code done, not operational):** Read-only — /status, /strategy report, /week brief, /growth report, /db queries
**Phase 4B (designed, not coded):** Operations — /week start, /week media, /week approve, /week emails, /sync stripe, /growth

## Weekly cycle (manual until Telegram ops is fixed)

Sunday: Prepare brief → Monday: AI generates → Human reviews → Approves → Tue-Fri: Manual publish → Saturday: Metrics + Growth Intelligence

---

# 10. META-WORKFLOW PLANNER

## Overview

Takes a raw idea and produces a buildable workflow plan through 3 phases with multi-model debate.

## Workspace: `~/.openclaw/workspace-meta-planner/` `[AUDIT]`

Bot: @Super_Workflow_Creator_bot

## Skills: 14 `[AUDIT]`

**Core (8):** intake-analyst, gap-finder, scope-framer, data-flow-mapper, contract-designer, architecture-planner, implementation-planner, lessons-validator
**Conditional (6):** capability-mapper, compliance-reviewer, creative-strategist, landscape-researcher, red-team, report-generator

## Scripts `[AUDIT]`

spawn_planner_agent.py, spawn_debate.py, cost_estimator.py, start_plan.sh, start_plan_from_file.sh, run_phase_a.sh, run_phase_b.sh, run_phase_c.sh, run_full_plan.sh, resume_plan.sh, validate_schema.py, human_gate.py, generate_report.py, json_repair.py, build_fact_pack.py, generate_contracts_atomic.py, generate_contracts_by_domain.py, generate_implementation_by_blocks.py, continue_contracts_with_retries.py, regenerate_one_contract.py, rerun_contracts_advanced.py, rescue_implementation_plan.py

## 9 JSON schemas `[AUDIT]`

00_intake_summary, 01_gap_analysis, 02_scope_decision, 03_data_flow_map, 04_contracts, 05_architecture_decision, 06_implementation_plan, 07_cost_estimate, 08_plan_review

## Debate config (planner_config.json) `[AUDIT]`

- execution_mode: sequential (parallel fails in WSL)
- rounds: 3
- timeout_per_model: 300s
- max_tokens_standard: 8192
- max_tokens_debate: 12288

## Runs `[AUDIT]`

| Run | Type | Status |
|-----|------|--------|
| declassified-marketing | E2E test (critical debate) | Complete |
| finance-test | E2E test (simple) | Complete |
| marketing-workflow-1 | Production run | 13 NEEDS_REVISION items |
| strategy-runtime-1 | Production run | Completed (triggered Marketing System) |

## Key files

- `MASTER_PLAN.md` — source of truth for planner design
- `planner_config.json` — debate settings, timeouts
- `models.json` — model routing with per-agent assignments
- `system_configuration.md` — infrastructure snapshot for agents

## CEO AGENTS.md integration `[AUDIT]`

CEO routes "Planifica:" or "Plan:" prefixed messages to the planner. Currently only Fase A is operational via CEO. CEO AGENTS.md explicitly says "NO ejecutes Fase B o C — aún no están implementadas."

**NOTE:** This contradicts the git history which shows commits for Phase B (ff75f65) and Phase C (30ebae2). The phases ARE implemented in code but the CEO hasn't been updated to use them. `[AUDIT]`
# 11. FINANCE TRACKER — v1.0.11

Personal finance automation system running as an OpenClaw skill on @Robotin1620_Bot.
Packaged as a ZIP product, sold at https://alfredopretelvargas.com/products/finance-tracker

## Core capabilities
- Receipt photo/text parsing with AI + Rule Engine
- Multi-category receipt splitting (one Walmart receipt → multiple category rows)
- Airbnb tax deduction tracking per line item
- Bank CSV reconciliation with exact amount matching
- Batch receipt link processing (Walmart w-mt.co, etc.)
- AI batch classification for unknown merchants (auto-creates rules)
- Daily cashflow calculation ("safe to spend today")
- Budget monitoring (80/95/100% alerts)
- Payment reminders (3-day, 1-day, day-of)
- Income tracking with auto-balance update
- Monthly AI-powered analysis report
- Setup wizard: auto-detect name/language, 3 questions one-at-a-time
- Telemetry: anonymous usage analytics to Supabase (opt-out)
- 38 CLI subcommands, numbered menu via /finance_tracker in Telegram

## Data
- Google Sheet: "Robotin Finance 2026" (ID: 1RcYfnreucTaRck9s_X65p190MSippBTimaFAdWl16pY)
- 8 tabs: Transactions, Budget, Payment Calendar, Monthly Summary, Debt Tracker, Rules, Reconciliation_Log, Cashflow_Ledger
- 18 spending categories + income type
- 87+ auto-categorization rules

## Files
- Skill: `~/.openclaw/workspace/skills/finance-tracker/`
- Config: `config/tracker_config.json` (unified), `config/rules.json`
- Scripts: `scripts/finance.py` (CLI) + `scripts/lib/` (13 modules)
- Docs: `docs/SYSTEM_GUIDE.md` (521 lines — complete reference)
- Credentials: `~/.openclaw/credentials/finance-tracker-token.json`
- Packaging: `~/finance-tracker-product/package.sh` (leak scanner + ZIP builder)

## Structure `[AUDIT v3.0]`

```
finance-tracker/
├── SKILL.md                    — 38-command menu + agent instructions
├── config/
│   ├── tracker_config.json     — Unified config
│   ├── rules.json
│   └── processed_receipts.json
├── docs/
│   └── SYSTEM_GUIDE.md
├── scripts/
│   ├── finance.py              — 38 CLI subcommands
│   ├── cron_runner.sh, setup_crons.sh, test_crons.sh, add_category.sh
│   └── lib/ (13 modules)
│       ├── analyst.py, budget.py, cashflow.py, config.py, logger.py
│       ├── parser.py, payments.py, reconcile.py, rules.py, sheets.py
│       ├── batch_receipts.py, setup_wizard.py, telemetry.py
│       └── __init__.py
├── logs/
└── templates/
```

## Google Sheets OAuth `[AUDIT]`

- Token: `~/.openclaw/credentials/finance-tracker-token.json` — EXISTS
- Client: `~/.openclaw/credentials/google-client.json` — EXISTS

## Cron jobs: 4 configured via setup_crons.sh

| Schedule | Job | Command |
|----------|-----|---------|
| 7:30 AM EST Mon-Fri | Daily cashflow | `cron_runner.sh cashflow cashflow` |
| 9:00 AM EST daily | Payment check | `cron_runner.sh payment-check payment-check` |
| 8:00 AM EST Sundays | Weekly summary | `cron_runner.sh weekly-summary weekly-summary` |
| 8:00 AM EST 1st | Monthly report | `cron_runner.sh monthly-report monthly-report` |

## Telemetry
- Supabase: `oetfiiatbzfydbtzozlz` (table: telemetry, `reviewed` column for triage)
- Events: install, setup_complete, setup_input, ai_call, setup_sheets, tax_profile, command, error, reconcile
- Every event includes version (`"v": "1.0.11"`)
- Opt-out: `finance.py telemetry off`

## Costs
- AI parsing: ~$0.002/receipt (only when Rule Engine has no match)
- AI batch classification: ~$0.01 per 50 merchants
- Total estimated: $1-3/month at normal usage

## Status (2026-04-02)
- v1.0.11 OPERATIONAL — packaged as 68K ZIP
- Website live with dynamic Stripe pricing via lookup keys
- Privacy policy published at /products/finance-tracker-privacy
- All v1.0.8–v1.0.11 bugs fixed (EOFError, KeyError, Schedule E, setup UX)
- Edge Functions deployed: `get-stripe-price` + `create-checkout`
- Pending: PDF support, AI tax retry logic

## Commercialization — LIVE

- Product page: https://alfredopretelvargas.com/products/finance-tracker
- Workflows page: https://alfredopretelvargas.com/workflows
- **Stripe lookup key:** `financial_tracker_standard` (no hardcoded price_id)
- **Dynamic Checkout Sessions** via `create-checkout` Edge Function
- Supabase project: `oetfiiatbzfydbtzozlz` (Edge Functions + telemetry)
- Deployment: Vercel (connected to GitHub `pr3t3l/alfredo-ai-factory-guide`)
- To change price: create new price in Stripe → same lookup key → "Transfer lookup key"
- Phase 1 (NOW): Personal use + first sales
- Phase 2 (Q3 2026): Scale marketing, collect testimonials
- Phase 3 (Q4 2026): SaaS via Telegram ($19/mo) — target Airbnb hosts

---

# 12. POSTGRESQL DATABASE v2.1

## Connection

```
postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db
Schema: marketing
```

## Tables: 24 `[AUDIT]`

Cross-reviewed with GPT-5.4 (2 rounds). All fixes applied.

| # | Table | Purpose |
|---|-------|---------|
| 1 | projects | Business/brand top-level |
| 2 | strategy_versions | Parent table for strategy versioning |
| 3 | product_catalog | Items with JSONB variants |
| 4 | strategy_outputs | 1 row per strategic artifact |
| 5 | buyer_segments | Reusable segments across campaigns |
| 6 | campaigns | Multi-week marketing campaigns |
| 7 | campaign_products | Normalized campaign ↔ product |
| 8 | campaign_target_segments | Normalized campaign ↔ segment |
| 9 | campaign_runs | Weekly execution within a campaign |
| 10 | assets | Creative pieces with structural IDs |
| 11 | asset_metrics_base | Universal metrics per asset |
| 12 | asset_metrics_video | Video metrics (hook_rate, hold_rate) |
| 13 | asset_metrics_email | Email metrics (open_rate, click_rate) |
| 14 | asset_metrics_search | Google Ads metrics |
| 15 | asset_metrics_landing | Landing page metrics |
| 16 | platform_metrics_weekly | Aggregated by platform |
| 17 | seo_metrics | Search Console data |
| 18 | orders | Stripe mirror for attribution |
| 19 | conversion_events | Generic events (purchase, lead, etc.) |
| 20 | growth_analyses | Growth Intelligence diagnoses |
| 21 | decisions | Post-Growth decision registry |
| 22 | knowledge_base | Winning/losing patterns |
| 23 | experiments | A/B test lifecycle |
| 24 | gates | Human decision log |

## Constraints `[AUDIT]`

- Foreign keys: 33
- CHECK constraints: 142

## Wrapper: db.py (926 lines) `[AUDIT]`

46 functions. CRUD for all tables + 4 analytics queries.

## Dual-write: DB = source of truth, JSON = backup `[AUDIT]`

All 3 runners write to PostgreSQL AND JSON. Safe wrapper: `_db_write()` logs errors, never blocks runner.

## verify_db_parity.py `[AUDIT]`

⚠️ **BROKEN** — `ModuleNotFoundError: No module named 'psycopg2'`. Fix: `/home/robotin/litellm-venv/bin/pip install psycopg2-binary`

## Schema: `~/.openclaw/marketing-system/scripts/sql/create_schema_v2.1.sql` (477 lines)

---

# 13. INTEGRATIONS

## Veo 3 (Video Generation)

- Script: `generate_marketing_videos.py` `[AUDIT]`
- SDK: `google-genai` (Gemini API)
- Model: `veo-3.0-fast-generate-001` ($0.15/sec = $1.20/8s video)
- API Key: GOOGLE_API_KEY

## DALL-E 3 (Image Generation)

- Script: `generate_marketing_images.py` `[AUDIT]`
- Model: dall-e-3 via LiteLLM `[AUDIT]`
- Status: NOT TESTED — config exists but no test run yet `[MANUAL]`

## Resend (Email)

- Script: `send_marketing_emails.py` `[AUDIT]`
- Domain: declassified.shop (verified) `[MANUAL]`
- From: cases@declassified.shop
- Test: 6/6 emails sent successfully

## Stripe (Payments)

- Script: `stripe_sync.py` `[AUDIT]`
- Account: acct_1SqwSeAcsyW8mQQC (Declassified Case)
- Syncs payment_intents → marketing.orders with UTM attribution
- Status: connected, 0 orders (no sales yet)

## Google Sheets (Finance Tracker)

- Library: gspread + google-auth
- OAuth: `~/.openclaw/credentials/finance-tracker-token.json` `[AUDIT]`
- Sheet: personal finance spreadsheet (tabs for transactions, summaries)

## ElevenLabs (TTS)

- Configured in openclaw.json `[AUDIT]`
- Voice ID: CwhRBWXzGAHq8TQ4Fs17
- Model: eleven_multilingual_v2

---

# 14. SOCIAL MEDIA ACCOUNTS

All items `[MANUAL]` — not filesystem-verifiable.

| Platform | Status | Account | Notes |
|----------|--------|---------|-------|
| Facebook Page | ✅ Created | Declassified Cases | Connected to IG |
| Instagram Business | ✅ Created | — | Connected to FB Page |
| FB Developer App | ⏳ Phase 3 | — | Need API tokens |
| TikTok | ⏳ Pending | — | — |
| YouTube | ⏳ Pending | — | — |
| Business Email | ✅ Live | support@declassified.shop | IONOS webmail |

**API tokens needed for auto-publishing:** pages_manage_posts, instagram_basic, instagram_content_publish, pages_read_engagement

**Goal:** Automated publishing via n8n/OpenClaw once tokens are obtained.

---

# 15. WEB STORE

## Repos & Deployment `[AUDIT]`

- Repo: `github.com/pr3t3l/declassifiedcase` (main branch)
- Local: `~/declassifiedcase/`
- Stack: React + Vite + Supabase + Stripe
- Deployment: **Vercel** (connected to GitHub, auto-deploy on push) — migrated from Lovable (2026-04-02)
- Personal site repo: `github.com/pr3t3l/alfredo-ai-factory-guide` (alfredopretelvargas.com)
- Status: **REDESIGN DEPLOYED AND LIVE** `[MANUAL]`

## Brand components: 14 `[AUDIT]`

RedactionBars, RedLine, ClassifiedStamp, CaseFileStamp, NavBar, HeroSection, CaseCard, PricingCard, TestimonialCard, SectionHeader, HowItWorks, WhatYouGet, Footer, EmailCapture

## Admin components `[AUDIT]`

AdminSidebar, AdminTable, DailyDetailTable, EmailAttemptsPanel, HourlyActivityChart, KpiCard, LeadsChart, ProductFilesManager, StatCard, StatusBadge

## Pages `[AUDIT]`

Home, Index, CaseCatalog, CaseLanding, CaseLindaSuccess, PersonaLanding, Blog, BlogPost, SolucionLindaOward, Privacy, Terms, NotFound, admin/*, cases/*

## 5 Persona Landing Pages `[AUDIT]`

Routes: /date-night-mystery-games, /game-night-mystery-activities, /true-crime-detective-experience, /mystery-gift-ideas, /family-detective-games. All use `PersonaLanding.tsx` template.

## UTM Tracking `[AUDIT]`

`useUtmTracking.ts` hook — captures utm params, stores in localStorage, passes to Stripe checkout.

## Brand SVG assets: 13 `[AUDIT]`

element_redaction_bars (light/dark), favicon, icon (light/dark/red), lockup_narrative, logo_primary_stamp (light/dark), stamp_classified, stamp_open, wordmark_horizontal (light/dark)

## Purchase flow (current)

Case page (all info + CTA) → Stripe checkout → Success page + Download

## Git commits `[AUDIT]`

| Commit | Description |
|--------|-------------|
| 117d9af | feat: complete redesign — 14 components, 6 pages, UTM |
| 9b1ebb2 | feat: admin panel redesign — classified operations room |
| 7924d24 | chore: save all current work before lovable sync |

---

# 16. BRAND IDENTITY

Reference document: `brand_guide.pdf` (8 pages, v1.0, March 2026)

## Brand personality

- **Intriguing** — every communication leaves the reader wanting more
- **Intelligent** — respects the player's intelligence, nothing condescending
- **Complicit** — speaks as if sharing a secret ("you and I know something")
- **Immersive** — every touchpoint feels like part of the case file
- **Accessible** — mysterious doesn't mean elitist

## Logo system

**Primary logo:** Case file stamp — double border, redaction bars, "DECLASSIFIED" in Courier Bold, red separator line, "C A S E S" wide tracking, "OPEN" stamp rotated -12°. Clear space = height of 'D' around entire logo.

**DC Icon:** 3 variants (light bg, dark bg, red accent). Sizes: 32px favicon, 48px tab, 64px app.

**Narrative lockup:** Full case file with tagline "YOUR NEXT CASE IS WAITING. TONIGHT." For hero sections, video thumbnails, social headers.

## Color palette

**Primary:**

| Name | Hex | Use |
|------|-----|-----|
| Espresso | #2c2520 | Backgrounds, text |
| Pergamino | #f5e6d0 | Light backgrounds |
| Sangre seca | #9b2c2c | Accent, CTAs |
| Arena | #d4c4a8 | Text on dark |

**Secondary:**

| Name | Hex |
|------|-----|
| Carbón | #1a1714 |
| Cuero | #463b32 |
| Ceniza | #8a7e6a |
| Rojo Vivo | #c0392b |
| Marfil | #e8dcc8 |

**Functional:**

| Name | Hex | Use |
|------|-----|-----|
| Resuelto | #2d6a4f | Solved states |
| Pista | #b8860b | Clue highlights |
| Misterio | #6c3483 | Mystery elements |
| Confianza | #1a5276 | Trust signals |

**Golden rule:** 70% Espresso/Pergamino (backgrounds), 20% Arena/Ceniza (text, details), 10% Sangre seca (accent — lines, stamps, CTAs). Red NEVER dominates.

Inspiration: aged case files + film noir + Colombian coffee at midnight.

## Typography

| Level | Font | Use |
|-------|------|-----|
| Display | Courier New Bold / Courier Prime | Logo, case titles, stamps. Always uppercase, letter-spacing 2-6px |
| Headings | Playfair Display / Georgia | Web headlines, product titles, marketing copy. Emotional weight |
| Body | Source Sans 3 / DM Sans | UI, emails, blog. Clean, doesn't compete with display |

**Hierarchy:** Monospace top (classification) → Serif middle (emotion) → Sans bottom (information)

## Social media templates (designed specs, not coded)

| ID | Format | Angle | Frequency |
|----|--------|-------|-----------|
| A | Post 1:1 | New case announcement | Weekly |
| B | Post 1:1 | Debate / engagement | 2-3x week |
| C | Post 1:1 | Emotional hook | 1-2x week |
| D | Post 1:1 | Digital unboxing | Monthly |
| E | Story 9:16 | New case launch | Weekly |
| F | Story 9:16 | Poll / quiz | 2x week |
| G | Story 9:16 | Testimonial | When available |
| H | TikTok 9:16 | True crime hook | Per video |
| I | TikTok 9:16 | POV organic | Per video |

All templates use redaction bars as recurring visual signature. Carousel structure: hook → problem → price → CTA.

## Usage rules

**DO:** Use defined palette, maintain red line as constant element, respect logo clear space, Courier for all "official" elements, redaction bars as signature, dark (Espresso) or light (Pergamino) backgrounds only.

**DON'T:** Change logo typeface, use red >10%, place logo on noisy backgrounds, use gradients/shadows/glow, distort the logo, use emojis in brand comms (except social), mix with cartoon/gamer aesthetics, use blue/green/purple backgrounds as primary.

> *The brand feels like a real case file that landed in your hands. We don't sell a game. We open a case. Every piece of communication is evidence.*

## Brand assets `[AUDIT]`

13 SVG files in `~/declassifiedcase/src/assets/brand/`: element_redaction_bars (light/dark), favicon, icon (light/dark/red), lockup_narrative, logo_primary_stamp (light/dark), stamp_classified, stamp_open, wordmark_horizontal (light/dark)

Brand guide PDF: `brand_guide.pdf` (8 pages)

---

# 17. QUALITY ASSURANCE

## Pipeline quality framework (6 pillars, 60 points)

1. User Experience / Emotional Arc (2x weight, MOST IMPORTANT)
2. Information Relevance
3. Clue Structure and Cognitive Load
4. Visual Support
5. Dynamic Clue Variety
6. Document as Experience

## Marketing claim linter `[AUDIT]`

- File: `claim_linter.py` (316 lines)
- 16 patterns + 7 verifiers
- **Fail-closed:** pipeline stops on violations
- Integrated in `marketing_runner.py` at phase M-lint (line 41: `from claim_linter import lint_assets`)
- Data source: `verified_facts` + `allowed_claims` + `forbidden_claims` in product_brief

---

# 18. COST TRACKING & BUDGET

## LiteLLM spend data `[AUDIT]`

| Week | Total Spend | API Calls |
|------|------------|-----------|
| 2026-03-23 | $74.13 | 2,405 |
| 2026-03-30 | $0.00 | 12 |

**NOTE:** The $74.13 includes the Codex OAuth migration period. With full OAuth ($200/mo Pro, $0/token for GPT), the ongoing cost should be significantly lower since GPT calls (96% of prior spend) are now $0/token. Needs 1-2 weeks of post-OAuth data to establish new baseline. `[INCONCLUSIVE]`

## Cost targets

| System | Target | Notes |
|--------|--------|-------|
| Pipeline per case | $6-8 | Phases 2-7 tracking invisible (sessions_spawn bug) |
| Marketing weekly | ~$2-4 | Most calls via Codex OAuth ($0) |
| Planner per run | $0.58-1.15 regular, $2.55-5.80 deep | Documented in planner |
| Monthly total target | TBD | Need post-OAuth baseline |
| OpenAI Pro subscription | $200/mo fixed | Codex OAuth |

## Backup `[AUDIT]`

- `safe_backup.sh`: **NOT FOUND** — needs recreation
- Cron backup job: **NOT configured**
- Last manual backup: 2026-03-23, 295MB tar.gz in Windows Downloads (per optimization plan)

---

# 19. OPTIMIZATION PLAN v2.2

## File: `~/.openclaw/OPTIMIZATION_PLAN.md` (523 lines) `[AUDIT]`

Authored by Claude Opus 4.6, reviewed by GPT+Gemini (2 rounds).

## Phase status `[AUDIT]`

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

---

# 20. ALL FILES & PATHS

## Root `[AUDIT]`

```
~/.openclaw/
├── .env                          — 21 API keys (master)
├── openclaw.json                 — Platform config
├── start_all_services.sh         — Service startup (60 lines)
├── sync_keys.sh                  — Key sync to litellm.env (10 lines)
├── OPTIMIZATION_PLAN.md          — v2.2 (523 lines)
├── declassified_project_bible_v1.md — Bible v1 (archived)
├── credentials/                  — OAuth tokens, Telegram ACLs
├── workspace/                    — CEO agent
├── workspace-declassified/       — Pipeline agent
├── workspace-meta-planner/       — Planner agent
├── workspace-content-distribution/ — ⚠️ STALE (should archive)
├── workspace-image-generator/    — ⚠️ STALE (should archive)
├── marketing-system/             — Marketing skills + scripts
├── marketing-hub/                — Legacy marketing (agents/social-agente)
├── products/                     — Product data + weekly runs
├── shared/                       — Shared scripts (spawn_core.py)
├── agents/                       — Agent registry
├── browser/                      — Chromium config
├── media/                        — Inbound media
├── logs/                         — Internal logs
├── telegram/                     — Telegram state
└── .git/                         — openclaw-config repo
```

## Marketing system `[AUDIT]`

```
~/.openclaw/marketing-system/
├── skills/              — 15 skills (SKILL.md each)
├── scripts/             — 24 Python scripts
│   └── sql/
│       └── create_schema_v2.1.sql
└── config/
    ├── email_config.json
    └── telegram_security.json
```

## Products `[AUDIT]`

```
~/.openclaw/products/misterio-semanal/
├── product_brief.json
├── strategies/
│   ├── v2/             — Active (approved)
│   └── _archived_v1_baseline/
└── weekly_runs/
    ├── 2026-W14/ ✅
    ├── 2026-W15/ ✅
    ├── 2026-W16/ ✅
    └── 2026-W17/ ✅
```

---

# 21. GIT REPOSITORIES

## openclaw-config `[AUDIT]`

- Remote: `https://github.com/pr3t3l/openclaw-config.git`
- Branch: main
- Status at audit: 11 dirty files (5 modified, 6 untracked)

| Commit | Description |
|--------|-------------|
| c02a20e | docs: add Declassified Cases project bible v1 |
| 6c0e2bf | feat: Telegram operations bot 4A |
| eb4b3a5 | feat: Stripe → PostgreSQL sync |
| b0a16f2 | feat: runners dual-write to PostgreSQL |
| d853c6e | test: W17 re-run with QA hardening |
| ed5ac57 | feat: QA compliance hardening |
| 66a7c0f | feat: PostgreSQL schema v2.1 + db.py |
| 9f4d306 | fix: email_config to verified domain |
| a82d610 | feat: Veo 3 + Resend integrations |
| 37b3022 | fix: anti-fabrication + Sonnet QA + DALL-E 3 |
| e0ca416 | feat: case bridge + W17 dry run |
| afb8eb4 | feat: skills v1.1 rewrite + strategy v2 |
| faf052f | feat: Finance Tracker + Marketing System |
| dcc8956 | Add file-based plan init |
| 29938b3 | Migrate GPT to chatgpt-gpt54 OAuth |
| b800aa1 | feat: v3.1 upgrade — 3-round debate |
| 9b9822f | feat: real token tracking |
| a94cff9 | V9: replace sessions_spawn with spawn scripts |
| 30ebae2 | feat: Build Phase 3 — Fase C |
| ff75f65 | feat: Build Phase 2 — Fase B |

## declassifiedcase `[AUDIT]`

- Remote: `https://github.com/pr3t3l/declassifiedcase.git`
- Branch: main
- Status at audit: clean

| Commit | Description |
|--------|-------------|
| 7924d24 | chore: save before lovable sync |
| 9b1ebb2 | feat: admin panel redesign |
| 117d9af | feat: complete redesign — 14 components, 6 pages |

---

# 22. TECHNICAL LESSONS LEARNED

Renumbered sequentially from all sources.

| ID | Lesson | Source |
|----|--------|--------|
| TL-01 | Python requests DIES in WSL for long API calls. Use streaming curl via subprocess. | Pipeline |
| TL-02 | POI portraits: 100px JPEG q70 = $0.004/image (15x cheaper than 200px PNG) | Pipeline |
| TL-03 | cost_tracker.py: always use `(totals.get('field') or 0)` for None-safe access | Pipeline |
| TL-04 | sessions_spawn cannot write files. Use spawn_agent.py / spawn_narrative.py | Pipeline |
| TL-05 | subprocess timeout must exceed curl --max-time (currently 650 > 600) | Pipeline |
| TL-06 | Use wget not curl for DALL-E image downloads | Pipeline |
| TL-07 | MAX_TOKENS 32000 for visual documents, 16384 for text docs | Pipeline |
| TL-08 | NEVER use dark backgrounds in rendered HTML — documents are paper | Pipeline |
| TL-09 | Always mkdir -p target directories before writing files | Pipeline |
| TL-10 | All file paths in agent prompts must be absolute (WORKSPACE_ROOT) | Pipeline |
| TL-11 | OpenClaw doesn't resolve ${ENV_VARS} in apiKey — hardcode or skip master_key | Config |
| TL-12 | LiteLLM dashboard: UI_USERNAME/UI_PASSWORD in litellm.env (not master_key) | Config |
| TL-13 | SKILL.md MUST include exact JSON schema inline with types | Planner |
| TL-14 | asyncio parallel debate fails in WSL. Sequential fallback works | Planner |
| TL-15 | LiteLLM model names ≠ provider names (claude-sonnet46 not claude-sonnet-4-6) | Config |
| TL-16 | M2.7 ignores complex AGENTS.md routing — not reliable for orchestration | Model |
| TL-17 | Sonnet truncates JSON above ~8K tokens. Generate by blocks | Architecture |
| TL-18 | PostgreSQL GENERATED columns can't use ::TEXT casts — use IMMUTABLE functions | PostgreSQL |
| TL-19 | ON CONFLICT with GENERATED columns: use column_name not expression | PostgreSQL |
| TL-20 | WSL auto-start: WSL.lnk + wsl.conf boot hook (NOT .bat keepalive) | Operations |
| TL-21 | Veo 3 model names use -001 suffix not -preview | API |
| TL-22 | `echo >>` for .env creates duplicates — edit with nano instead | Operations |
| TL-23 | isolatedSession + lightContext need gateway ≥v2026.4 — not available yet | Config |
| TL-24 | CEO MEMORY.md must be CEO-specific — never copy from Declassified workspace | Architecture |
| TL-25 | sessions_spawn is invisible for cost tracking — phases 2-7 untracked | Pipeline |
| TL-26 | M2.7 A/B test not done — don't assume it's better without data | Process |
| TL-27 | `$(cat file.md)` in bash fails >~8KB — use file-based wrapper | WSL |
| TL-28 | Git: identity Alfredo Pretel, email 30666965+pr3t3l@users.noreply.github.com | Git |
| TL-29 | Google Sheets OAuth: use run_local_server(port=18900, open_browser=False) in WSL | Finance |
| TL-30 | Google Sheets needs BOTH spreadsheets AND drive scopes | Finance |
| TL-31 | Lovable Publish after Code edits: git push doesn't deploy — Publish button required | Web |
| TL-32 | One Claude Code instance per repo — two on same repo causes git conflicts | Process |
| TL-33 | LiteLLM Prisma: duplicate model LiteLLM_DeletedTeamTable — warning, not blocking | LiteLLM |
| TL-34 | verify_db_parity.py needs psycopg2 installed in the venv that runs it | DB |
| TL-35 | litellm.env: only API keys + UI creds. Extra vars (TELEGRAM_*) crash LiteLLM | Config |
| TL-36 | Google Sheets OAuth in WSL: port 18900, open_browser=False | Finance setup |
| TL-37 | Google Sheets needs spreadsheets + drive scopes | Finance setup |
| TL-38 | Receipt amounts: re.findall + max() beats re.search (first match) | Finance bug |
| TL-39 | Credit card payments are POSITIVE in Chase CSV — check payment keywords before sign split | Finance classification |
| TL-40 | Spanish payment keywords needed in classifier (SU PAGO, PAGO AUTOMATICO) | Finance i18n |
| TL-41 | AI batch classification ~$0.01/50 merchants — always cheaper than defaulting to Other | Finance cost |

---

# 23. DESIGN PRINCIPLES

## Architecture & Design

1. Always design complete/advanced from the start — with AI implementing, the cost difference is minutes not weeks
2. No patches — fix the root system. Mediocre output = rewrite the skill/prompt
3. For implementation-ready docs, skip the meta-planner and go direct to Code
4. Large artifacts must be generated by domain blocks — never monolithic JSON (TL-17)
5. Cross-model review (Claude + GPT + Gemini) for all major architecture decisions
6. Gap Finder BEFORE architecture — unanimity across 4 models
7. Data flow + contracts BEFORE architecture — define what moves before who moves it
8. Debate is conditional, not ritual — simple ideas don't need 3-model debate
9. Cost Estimator = script, not LLM — deterministic tasks use deterministic scripts
10. Shared scripts use pinned copies, NOT symlinks

## Model Routing

11. Sonnet 4.6 is untouchable for render/creative — unanimous cross-model consensus
12. No mini or nano models for content generation or QA — ever
13. OpenRouter for experimental models only, not replacing direct API

## Quality & Compliance

14. Claim linter is fail-closed — violations stop the pipeline
15. verified_facts as single source of truth — generators use ONLY this data
16. DB = source of truth, JSON = backup export

## Operations

17. Budget-conscious — track and mention costs of every API call
18. Report only failures — if something works, assume it works
19. Cross-model review before implementation — produces significantly better results

---

# 24. SESSION HISTORY

## Session 1: 2026-03-24/25 — Meta-Workflow Planner Build

4-model design (Claude+GPT+Gemini+M2.7), 3 build phases, git unification, token tracking, deep analysis upgrade planning.

## Session 2: 2026-03-26/29 — Marketing System + Infrastructure

Marketing system implementation (80 files), strategy v2, QA hardening, PostgreSQL v2.1, Stripe sync, brand guide, web redesign, Telegram ops 4A. Most productive session.

## Session 3: 2026-03-18/22 — Pipeline V9 + Optimization

Pipeline V9 audit (15 fixes), ai_render.py parameters, spawn architecture, Optimization Plan v2.2 (phases 0-6A), Codex OAuth migration, cost baseline measurement.

## Session 4: 2026-03-27/28 — Finance Tracker

8-module finance tracker, Google Sheets OAuth, cron jobs, commercialization plan, debt restructuring analysis.

## Session 5: 2026-03-29 — Design & Brand Identity

Brand guide (8 pages, 14 SVGs), web redesign (14 components, 6 pages), admin panel redesign, persona landing pages, UTM tracking. Deployed via Lovable.

## Session 6: 2026-03-29 — Social Media Setup

FB Page, IG Business, FB Developer App (Phase 3), IONOS email setup, n8n/OpenClaw auto-publishing planning.

## Session 7: 2026-03-29/30 — Bible Consolidation

Gap analysis across 6+ chats, audit script v2.1, system verification, Bible v2 production.

## Session 8: 2026-03-31 — Finance Tracker (Complete Build)

### What was built
- Complete personal finance tracking system (9 modules) as OpenClaw skill
- Google Sheets integration (8 tabs, OAuth configured)
- 87+ merchant auto-categorization rules
- Multi-category receipt splitting with Airbnb tax deduction tracking
- AI batch classification for unknown merchants
- Bank CSV reconciliation (Chase, Discover, Citi, Wells Fargo)
- Batch receipt processor for Walmart links
- Income tracking with auto-balance update
- Daily cashflow calculator

### Financial analysis performed
- Full analysis of all bank statements (Jan 2025 — Mar 2026)
- AI spending breakdown: $888 total (Claude $134 sub + $317 API, OpenAI $261 sub + $109 API, Google $67)
- Debt timeline: Wells Fargo $200 (pay now), Discover $566/mo x 11, Citibank $288/mo x 17
- Payment calendar built from real bank data (6 debts + subscriptions + utilities)

### Bugs fixed
- Receipt parser: re.search → re.findall + max() for amounts
- Reconciliation: false positive probable_match eliminated (amount-only match removed)
- Classification: positive amounts on credit cards (payments) misclassified as refunds
- Spanish keywords missing: SU PAGO, PAGO AUTOMATICO
- CATEGORIES list out of sync with budgets.json
- Single-month reconciliation → multi-month

### Documents created
- Workflow specification V1 (docx, 9 sections)
- V1.1 Addendum: Reconciliation + Rule Engine + Daily Cashflow (docx)
- Financial control plan (md)
- Presentation deck (11 slides, pptx)
- Project Bible gaps document with verification script
- AI Classification + PDF + Smart Categories spec
- Batch Receipt Instructions spec

### Commercialization plan
- Phase 1 (NOW): Personal use 3 months
- Phase 2 (Q3): OpenClaw skill marketplace $49-99
- Phase 3 (Q4): SaaS via Telegram $19/mo (target: Airbnb hosts)
- Phase 4 (2027): Scale or white-label to accountants

## Session 9: 2026-04-01 — Finance Tracker v1.0.8–v1.0.11 + Commercialization

### What was built
- **v1.0.8:** Setup UX overhaul (auto-detect name/language, JSON-only, 3 questions), Schedule E fix, leak scanner
- **v1.0.9:** 5 new commands (modify-payment, add-debt, update-debt, pay-debt, remove-goal), KeyError fix, version tracking in telemetry
- **v1.0.10:** 38-command numbered menu for /finance_tracker, VERSION bump
- **v1.0.11:** Questions one-at-a-time, telemetry notice (GDPR/CCPA), enhanced telemetry events (setup_input, ai_call, setup_sheets, tax_profile), natural language tax mapping

### Supabase telemetry improvements
- Added `reviewed` column to telemetry table for triage
- Marked all existing events (≤46) as reviewed
- Every event now includes version number

### Website / Commercialization
- Price updated: $120 → $47
- Stripe Payment Link connected
- Dynamic pricing via Supabase Edge Function (get-stripe-price) + useStripePrice hook
- Privacy Policy page at /products/finance-tracker-privacy
- Portfolio card: "(Robotin)" → "(OpenClaw Skill)", chips show product features
- SYSTEM_GUIDE.md: 521-line complete system reference

### Bugs fixed
- EOFError x7 (setup without JSON)
- Schedule E parsing ("Airbnb" not recognized as rental)
- Personal name in code comment (leak)
- KeyError in format_confirmation (direct key access)
- Setup UX: 3 questions at once → one at a time

### Documentation updated
- workflow_bible_finance.md — full audit v3.0
- openclaw_project_bible_v2.md §11 — updated to v1.0.11

## Session 10: 2026-04-01/02 — Website Restructure + Stripe Migration (Claude Code)

### Website restructure
- Nav: "Products" → "Workflows", href changed from `/products/finance-tracker` → `/workflows`
- New `/workflows` page: 2 featured cards (Declassified + Finance Tracker) + 4 smaller "Other Workflows" cards (Platform, Pipeline, Planner, Marketing) + Contact CTA
- Each workflow card deep-links to OpenClaw Portfolio via `?tab=` query param
- ScrollToTop component added — pages scroll to top on navigation
- PortfolioSection: "Products" label → "Workflows"
- Headline: "Stop guessing. Start tracking every purchase — line by line."

### Profile updates
- M.AI education: removed "in progress" — completed, shows "Continuous AI Development"
- Skills: new "Automotive & Quality Standards" category (ISO 9001, IATF 16949)
- Skills: added Prompt Engineering, Data Mining, Six Sigma, CNC Programming, AutoCAD, Lean Manufacturing, Master's in AI

### Stripe migration
- Created new Stripe account (replaced old profile)
- Migrated from hardcoded `price_id` to **lookup keys** (`financial_tracker_standard`)
- New `create-checkout` Edge Function: creates Stripe Checkout Session dynamically
- Price shown on page and price charged are always in sync — no more static Payment Links
- `useStripePrice` hook updated: accepts `lookupKey` instead of `priceId`, returns `{ formatted, priceId }`
- To change price: create new price in Stripe with same lookup key + "Transfer lookup key"

### Infrastructure migration
- Frontend `.env`: switched from Lovable's Supabase (`tajcmrnpnkfkkjunzkae`) to own project (`oetfiiatbzfydbtzozlz`)
- Edge Functions deployed to `oetfiiatbzfydbtzozlz`: `get-stripe-price` + `create-checkout` (no-verify-jwt)
- `get-stripe-price`: upgraded Stripe SDK 12→14, removed invalid apiVersion
- Vercel connected to GitHub for deployment (replacing Lovable Publish)
- IONOS domain still pointing to Cloudflare/Lovable — needs migration to Vercel

### Bugs fixed
- Stripe SDK v12 didn't support apiVersion 2024-11-20 → upgraded to v14 + removed explicit version
- Frontend called wrong Supabase project → `.env` updated
- $47 fallback shown instead of real price → Edge Function deployed + working

---

# 25. CURRENT STATE & PENDING ITEMS

## COMPLETED ✅

| # | What | When |
|---|------|------|
| 1 | Marketing System full implementation | Session 2 |
| 2 | 15 marketing skills (13 rewritten to pro level) | Session 2 |
| 3 | Strategy v2 (6 personas, 105 keywords, 25 angles) | Session 2 |
| 4 | Case bridge (pipeline → marketing) | Session 2 |
| 5 | Veo 3 integration | Session 2 |
| 6 | Resend integration (6/6 emails) | Session 2 |
| 7 | PostgreSQL v2.1 (24 tables, db.py) | Session 2 |
| 8 | QA compliance hardening (claim linter) | Session 2 |
| 9 | Runners dual-write to DB | Session 2 |
| 10 | Stripe sync script | Session 2 |
| 11 | Brand guide + 13 SVG assets | Session 5 |
| 12 | Web redesign: 14 components, 6 pages, UTM tracking | Session 5 |
| 13 | Admin panel redesign | Session 5 |
| 14 | 5 persona landing pages | Session 5 |
| 15 | Deployed to production via Lovable | Session 5 |
| 16 | Telegram ops bot code (Phase 4A) | Session 2 |
| 17 | Finance Tracker (skill + 4 cron jobs) | Session 4 |
| 18 | Meta-Planner Phases A+B+C | Session 1 |
| 19 | Optimization Plan phases 0-6A | Session 3 |
| 20 | Codex OAuth ($0/token GPT) | Session 3 |
| 21 | Bible v2 (this document) | Session 7 |
| 22 | Finance Tracker complete build (9 modules + batch receipts) | Session 8 |
| 23 | AI batch classification for unknown merchants | Session 8 |
| 24 | 87+ auto-categorization rules deployed | Session 8 |
| 25 | Bank CSV reconciliation (Chase, Discover, Wells, Amex) | Session 8 |
| 26 | Batch receipt processor (17 Walmart receipts) | Session 8 |
| 27 | Finance Tracker v1.0.8–v1.0.11 (setup wizard, telemetry, 38 commands) | Session 9 |
| 28 | Stripe checkout + dynamic pricing for Finance Tracker | Session 9 |
| 29 | Privacy Policy page (GDPR/CCPA compliant) | Session 9 |
| 30 | Supabase telemetry: reviewed column, version tracking, enhanced events | Session 9 |
| 31 | SYSTEM_GUIDE.md (521 lines — complete system reference) | Session 9 |
| 32 | Website restructure: "Products" → "Workflows" page + nav | Session 10 |
| 33 | Stripe migration: new account + lookup keys + dynamic checkout | Session 10 |
| 34 | Edge Functions deployed: get-stripe-price + create-checkout | Session 10 |
| 35 | Supabase migration: Lovable project → own project | Session 10 |
| 36 | Profile updates: M.AI completed, Automotive skills, ScrollToTop | Session 10 |
| 37 | Headline copy optimization for conversion | Session 10 |

## PENDING 🔲

| Item | Status | Blocker |
|------|--------|---------|
| Telegram ops bot operational | Code done, needs dedicated bot token | Create new bot via BotFather |
| Telegram ops Phase 4B (operations) | Designed | After 4A is operational |
| FB Developer App (API tokens) | Phase 3 in progress | Complete Meta app review |
| TikTok account | Not started | — |
| YouTube channel | Not started | — |
| DALL-E 3 test via LiteLLM | Config exists | Needs test run |
| A/B test M2.7 as CEO model | Designed | Needs cost baseline data |
| Compaction benchmark (Opt Phase 7) | Designed | After A/B test |
| AGENTS.md reduction (Opt Phase 8) | Designed | After compaction |
| Full E2E run with new case | Designed | After integrations stable |
| cyber-ghost: inject photos + merge + distribute | Paused | Manual resume |
| Free mini case lead magnet | Not started | — |
| Landing pages SEO content | Placeholder content in PersonaLanding | After marketing content system |
| safe_backup.sh recreation | Missing | Create script + cron |
| psycopg2 install for verify_db_parity | Bug | `pip install psycopg2-binary` |
| ~~Finance tracker smoke test fix~~ | ~~Traceback~~ | DONE (Session 8) |
| ~~Finance: EOFError, KeyError, Schedule E bugs~~ | ~~Multiple~~ | DONE (Session 9, v1.0.8–v1.0.9) |
| ~~Finance: Setup UX + telemetry + commands~~ | ~~v1.0.8–v1.0.11~~ | DONE (Session 9) |
| ~~Finance: Stripe checkout + dynamic pricing~~ | ~~Website~~ | DONE (Session 9) |
| ~~Finance: Deploy get-stripe-price Edge Function~~ | ~~Deployed to oetfiiatbzfydbtzozlz~~ | DONE (Session 10) |
| ~~Finance: Set STRIPE_API_KEY in website Supabase~~ | ~~New Stripe account configured~~ | DONE (Session 10) |
| ~~Finance: Migrate to lookup keys + dynamic checkout~~ | ~~financial_tracker_standard~~ | DONE (Session 10) |
| Website: Migrate IONOS domain from Cloudflare/Lovable to Vercel | DNS change needed | None |
| Finance: PDF bank statement support | Spec ready | None |
| Finance: Smart category creation (AI suggests + user approves) | Spec ready | None |
| Finance: AI tax profile retry logic | LiteLLM down → basic fallback | None |
| Finance: SaaS multi-tenant conversion | Q4 2026 | After 3 months personal use |
| Archive stale workspaces | workspace-content-distribution, workspace-image-generator | Move to ~/openclaw-archive/ |
| CEO AGENTS.md + MEMORY.md update | Stale version/model info | Update to match openclaw.json |
| GOG_KEYRING_PASSWORD duplicate in .env | Bug | Remove duplicate line |
| Tailscale serve configuration | Not configured (was assumed configured) | `tailscale serve --bg 18789` |

---

# 26. OPERATIONAL PLAYBOOK

## Starting services (normally auto-starts via WSL boot)

```bash
# If manual start needed:
bash ~/.openclaw/start_all_services.sh

# Verify:
curl -s http://127.0.0.1:18789 > /dev/null && echo "Gateway OK"
curl -s http://127.0.0.1:4000/health > /dev/null && echo "LiteLLM OK"
pg_isready && echo "PostgreSQL OK"
```

## Weekly marketing cycle

```bash
cd ~/.openclaw/marketing-system/scripts

# 1. Create brief (if new case)
python3 case_to_brief.py misterio-semanal 2026-WXX /path/to/case/

# 2. Generate content
python3 marketing_runner.py misterio-semanal 2026-WXX

# 3. Review claim linter
cat ~/.openclaw/products/misterio-semanal/weekly_runs/2026-WXX/claim_lint_report.json | python3 -m json.tool

# 4. Generate media
python3 generate_marketing_videos.py misterio-semanal 2026-WXX
python3 generate_marketing_images.py misterio-semanal 2026-WXX

# 5. Approve
python3 marketing_runner.py misterio-semanal 2026-WXX approve

# 6. Send emails
python3 send_marketing_emails.py misterio-semanal 2026-WXX --dry-run

# 7. Sync Stripe
python3 stripe_sync.py misterio-semanal --days 7

# 8. Growth Intelligence
python3 growth_runner.py misterio-semanal 2026-WXX
```

## Meta-Planner

```bash
# Start new plan
cd ~/.openclaw/workspace-meta-planner
bash scripts/start_plan.sh "<slug>" "<idea>"

# Or via CEO Telegram: "Planifica: <idea>"

# Check status
bash scripts/resume_plan.sh <slug>

# View outputs
ls runs/<slug>/
```

## Database

```bash
# Connect
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db"

# Overview
SELECT tablename, n_live_tup FROM pg_stat_user_tables WHERE schemaname='marketing' ORDER BY 1;

# Buyer segments
SELECT segment_id, segment_name, priority FROM marketing.buyer_segments;
```

## DBeaver (Windows)

Host: localhost, Port: 5432, Database: litellm_db, User: litellm, Password: litellm-local-2026. Navigate: Schemas → marketing → Tables.

---

# 27. REMOTE OPERATIONS

## Tailscale `[AUDIT]`

- Installed on WSL
- Device: pretel-laptop
- Tailnet: tail600a27.ts.net
- `tailscale serve`: **NOT configured** at time of audit `[AUDIT]`
- Gateway controlUi allows origin: `https://pretel-laptop.tail600a27.ts.net` `[AUDIT]`

## Termius (phone)

- SSH via Tailscale IP
- Used to dispatch Claude Code tasks remotely

## Claude Code `[AUDIT]`

- Version: 2.1.86
- Workspace scope: `~/.openclaw/`
- Installed globally via npm

## tmux

- Pattern: `tmux new -s <name>` / `tmux attach -t <name>`
- No active sessions at time of audit `[AUDIT]`

## Remote dispatch pattern

```bash
# From phone via Termius:
ssh robotin@<tailscale-ip>
tmux new -s work
cd ~/.openclaw
claude --print "your task here"
```

---

**END OF DOCUMENT**

*This document is the single source of truth for the entire OpenClaw platform. Verified via system audit 2026-03-29. Facts tagged [AUDIT] are machine-verified, [MANUAL] are confirmed by Alfredo, [INCONCLUSIVE] need re-verification. If it's not in this document, it doesn't exist for future sessions.*
