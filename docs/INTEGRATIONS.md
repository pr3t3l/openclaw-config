# INTEGRATIONS.md — OpenClaw
<!--
SCOPE: ALL external APIs, services, and third-party integrations.
       Endpoints, rate limits, costs, auth method, health checks.
NOT HERE: API keys → ~/.openclaw/.env and ~/.config/litellm/litellm.env ONLY
NOT HERE: Database schemas → DATA_MODEL.md
NOT HERE: How workflows use these → docs/specs/[workflow]/spec.md

UPDATE FREQUENCY: When adding a new integration or when limits/pricing change.
-->

**Last updated:** 2026-04-08
**Sources:** Project Bible v2 §3,§6, Platform Bible §4-5 (archived in docs/archivo/)

---

## API Key Locations

| File | Keys stored | Used by |
|------|------------|---------|
| `~/.openclaw/.env` | 21 keys (all services) | OpenClaw agents, spawn scripts |
| `~/.config/litellm/litellm.env` | 6 keys (LLM providers + UI creds) | LiteLLM proxy |
| `~/.openclaw/credentials/` | OAuth tokens, bot ACLs | Google Sheets, Telegram |

**RULE:** Keys are NEVER written in documentation. This doc describes endpoints and limits only.

---

## LLM Providers (via LiteLLM)

All LLM calls route through LiteLLM proxy at `http://127.0.0.1:4000` unless noted.

### Anthropic (Claude)

**Purpose:** AI rendering (HTML→PDF), high-quality generation
**Auth:** API key in .env (ANTHROPIC_API_KEY)
**Used by:** Pipeline Phase 8 (ai_render.py — DIRECT, not via LiteLLM), general generation

| Model | LiteLLM Name | Use Case | Cost |
|-------|-------------|----------|------|
| Claude Sonnet 4.6 | claude-sonnet46 | Rendering, quality generation | Paid per token |

**Gotchas:**
- Phase 8 uses DIRECT Anthropic API (not LiteLLM) for streaming render
- Key was rotated 2026-03-22 after $0 balance block

### OpenAI / Codex OAuth

**Purpose:** Primary model for generation phases (nearly free via subscription)
**Auth:** Codex OAuth token + ChatGPT subscription OAuth
**Used by:** Pipeline Phases 2-7, Planner all phases, Marketing generation

| Model | LiteLLM Name | Use Case | Cost |
|-------|-------------|----------|------|
| GPT-5.4 (Codex) | openai-codex/gpt-5.4 | Primary generation (all 3 agents) | $0 (subscription) |
| GPT-5.4 (ChatGPT) | chatgpt-gpt54 | Fallback / alternative | $0 (subscription) |
| GPT-5.4 thinking | chatgpt-gpt54-thinking | Reasoning tasks, narrative, QA | $0 (subscription) |

**Gotchas:**
- Codex OAuth is the cost optimization strategy — 90%+ of generation at $0
- Session tokens may expire — monitor for auth errors

### Google (Gemini)

**Purpose:** Alternative models, image analysis
**Auth:** GEMINI_API_KEY in .env

| Model | LiteLLM Name | Use Case | Cost |
|-------|-------------|----------|------|
| Gemini 3.1 Pro | gemini31pro | Alternative generation | Per token |
| Gemini 3.1 Pro thinking | gemini31pro-thinking | Reasoning tasks | Per token |

**Gotchas:**
- Rate limits after ~15 spawns in 2 hours (LL-AI model notes)
- Key was renewed 2026-03-23

### OpenRouter

**Purpose:** Access to additional models (M2.7, Step 3.5, Kimi)
**Auth:** OPENROUTER_API_KEY in .env

| Model | Use Case | Note |
|-------|----------|------|
| MiniMax M2.7 | A/B testing candidate | NOT reliable for routing (LL-AI-016) |
| Step 3.5 | Alternative reasoning | Available via OpenRouter |
| Kimi | Alternative generation | Available via OpenRouter |

---

## Image Generation

### DALL-E 3 (OpenAI)

**Purpose:** POI portrait generation
**Auth:** OPENAI_IMAGE_GEN_KEY in .env
**Used by:** Pipeline Phase 7 (spawn_images.py)
**Cost:** ~$0.04/image (1024x1024)
**Gotcha:** Use wget (not curl) for downloads — special chars in URLs (LL-INFRA-006)

### nano-banana-2-gemini

**Purpose:** Alternative image generation (cheaper)
**Auth:** NANO_BANANA_API_KEY in .env
**Cost:** ~$0.004/image at 100px JPEG q70 (LL-COST-002)
**Gotcha:** Needs exponential backoff (2s, 5s, 10s) for RESOURCE_EXHAUSTED errors

---

## Communication

### Telegram Bot API

**Purpose:** Primary user interface (3 bots)
**Base URL:** `https://api.telegram.org/bot{token}/`
**Auth:** Per-bot tokens in .env

| Bot | Token Variable | Agent | Domain |
|-----|---------------|-------|--------|
| @Robotin1620_Bot | TELEGRAM_BOT_TOKEN | CEO | Personal assistant, finance, admin |
| @APVDeclassified_bot | TELEGRAM_DECLASSIFIED_TOKEN | Declassified | Case pipeline |
| @Super_Workflow_Creator_bot | TELEGRAM_PLANNER_TOKEN | Planner | Workflow planning |

**Auth control:** `credentials/telegram-*-allowFrom.json` (ACL per bot)
**Rate limits:** 30 msg/sec per bot, 20 msg/min per chat
**Gotcha:** 4th bot (marketing ops) planned but needs its own BotFather token

### Resend

**Purpose:** Transactional email (order confirmations, marketing)
**Auth:** RESEND_API_KEY in .env
**Domain:** declassified.shop (verified)
**Used by:** Marketing System (6 email types), Stripe delivery flow
**Cost:** Free tier covers current volume

---

## Payments

### Stripe

**Purpose:** Product sales (Declassified Cases), future SaaS subscriptions
**Auth:** STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET in .env
**Account:** acct_1SqwSeAcsyW8mQQC
**Used by:** Web store (declassified.shop), stripe_sync.py

| Endpoint | Purpose |
|----------|---------|
| Checkout Sessions | Create payment links |
| Webhooks | Order completion → email delivery |
| Price lookup keys | Dynamic pricing (financial_tracker_standard) |

**Architecture:** Stripe webhook → Supabase Edge Function → Resend email → Google Drive download

---

## Data & Storage

### Google Sheets API

**Purpose:** Finance Tracker data storage
**Auth:** OAuth2 via `credentials/google-client.json` + `finance-tracker-token.json`
**Scopes:** spreadsheets + drive (BOTH required — LL-INFRA-030)
**Port:** 18900 for OAuth callback in WSL (LL-INFRA-029)
**Gotcha:** open_browser=False required in WSL

### Google Drive API

**Purpose:** Product delivery (case ZIP files)
**Auth:** Same OAuth as Sheets
**Used by:** Content Distribution (Pipeline Phase 10)

### Supabase

**Purpose:** Web store backend (declassified.shop)
**Services:** Auth, Database, Storage, Edge Functions
**Project:** oetfiiatbzfydbtzozlz (migrated from Lovable project)
**Edge Functions:** get-stripe-price, create-checkout

---

## Video & Audio

### Google Veo 3

**Purpose:** Marketing video generation
**Auth:** GOOGLE_API_KEY in .env
**Model name:** Uses -001 suffix, NOT -preview (LL-AI-021b)
**Cost:** Per video, ~60s generation time

### ElevenLabs

**Purpose:** Text-to-speech (TTS)
**Auth:** ELEVENLABS_API_KEY in .env
**Used by:** CEO bot skill

---

## Remote Access

### Tailscale

**Purpose:** SSH access to WSL from phone
**Device:** pretel-laptop
**Tailnet:** tail600a27.ts.net
**Used with:** Termius (phone) → SSH → tmux → Claude Code

**Status:** Installed but `tailscale serve` NOT configured (as of audit 2026-03-29)
**Gateway allows:** `https://pretel-laptop.tail600a27.ts.net`

---

## Cost Summary

| Service | Est. Cost/Month | Driver | Optimization |
|---------|----------------|--------|-------------|
| Anthropic (Claude) | $20-40 | Pipeline Phase 8 renders | Only phase that pays per token |
| OpenAI (Codex OAuth) | $0 | Subscription covers it | 90%+ of generation |
| Gemini | $5-10 | Fallback/alternatives | Use only when Codex unavailable |
| DALL-E 3 | $2-5 | Image generation | nano-banana for cheap images |
| Telegram | $0 | Bot API is free | — |
| Resend | $0 | Free tier | — |
| Stripe | 2.9% + $0.30/txn | Per sale | Standard pricing |
| Supabase | $0 | Free tier | — |
| LiteLLM | $0 | Self-hosted | — |
| PostgreSQL | $0 | Self-hosted | — |
| **Total estimate** | **$30-60/month** | | |

**Budget targets:** See CONSTITUTION.md §6

---

## OpenClaw Skill System (Planner Integration)

### Architecture
- Planner runs as Python orchestrator at `~/.openclaw/workspace-meta-planner/planner/`
- OpenClaw Gateway triggers execution via skills (SKILL.md files)
- Skills use normal mode with strict exec instructions (`command-dispatch: tool` does NOT work for this use case — see LL-INFRA-036)
- `/reset` required before skill invocation to prevent LLM simulation (LL-INFRA-037)

### Skills
- `skills/sdd-planner/SKILL.md` → `/sdd_planner` command
  Executes: `python3 scripts/run_sdd_planner.py start "<args>"`
- `skills/sdd-planner-reply/SKILL.md` → `/sdd_planner_reply` command
  Executes: `status` to find run/gate, then `gate-reply <run_id> <gate_id> "<response>"`

### Model Gateway
- LiteLLM proxy at `http://127.0.0.1:4000`
- `config/model_mapping.json` maps spec names → LiteLLM model names:
  - `claude-opus-4-6` → `claude-opus46`
  - `gpt-5.4` → `gpt52-thinking`
  - `gemini-3.1-pro` → `gemini31pro-none`
- ModelGateway uses streaming curl via subprocess (tempfile + @file pattern) because Python requests FAILS in WSL for long API calls (LL-INFRA-001)
- API key: `sk-litellm-local` (from `~/.openclaw/.env`)

### Transient Data Pattern
- State (`planner_state.json`) only contains schema-valid fields (`additionalProperties: false`)
- Transient data stored as files in `planner_runs/{run_id}/`:
  `intake_answers.json`, `draft_content.md`, `audit_result.json`,
  `ideation_result.json`, `lessons_check_result.json`, `finalize_result.json`
- See LL-ARCH-034 for rationale

### G0 Modes
- `MODULE_SPEC` / `WORKFLOW_SPEC` — basic mode, all gates manual
- `MODULE_SPEC auto` — auto-approve mode: skips G1/G3/G5, only G0+G7 manual (LL-PROC-034)
- `MODULE_SPEC interactive` — interactive intake: asks one question per section (LL-PROC-035)
- `MODULE_SPEC auto interactive` — auto-approve + interactive (auto wins, interactive ignored)

### G1 Responses
- `approved` — confirm intake, advance to Phase 1.5
- `skip` — skip current document entirely, no cost (LL-COST-042)
- `[section answer]` — in interactive mode, answer for current section
- `auto` — in interactive mode, switch to auto-generate remaining sections

### Telegram File Delivery
- Phase 5 sends `.md` file attachment + summary message to Telegram chat
- Uses `curl` subprocess to POST to Telegram Bot API (LL-INFRA-001 pattern)
- Requires `TELEGRAM_CHAT_ID` env var set when run starts
- Auto-approve mode sends file with "(auto-approved)" note
- See `_send_telegram_document()` in `phase_handlers.py`

### Dynamic Cost Thresholds
- Thresholds calculated at G0 based on document count:
  - <=3 docs: alert=$5, hard_limit=$10
  - 4-6 docs: alert=$10, hard_limit=$20
  - 7+ docs: alert=$30, hard_limit=$50
- Stored in state as `cost_alert_threshold`/`cost_hard_limit`
- Overrides pricing.json defaults (LL-COST-043)

### Known Limitations
- `/reset` required before every skill invocation session (LL-INFRA-037)
- `command-dispatch: tool` incompatible with Python script wrapping (LL-INFRA-036)
- Skill directory hyphens become underscores in Telegram commands (LL-INFRA-038)

---

## Health Checks

| Service | Check Command | Expected |
|---------|--------------|----------|
| LiteLLM | `curl -s http://127.0.0.1:4000/health` | 200 OK |
| OpenClaw Gateway | `curl -s http://127.0.0.1:18789` | 200 OK |
| PostgreSQL | `pg_isready` | accepting connections |
| All three | `bash ~/.openclaw/start_all_services.sh` | Idempotent restart |
