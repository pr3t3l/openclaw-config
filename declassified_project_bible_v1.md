# DECLASSIFIED CASES — COMPLETE PROJECT DOCUMENTATION
## OpenClaw Marketing System + Pipeline + Infrastructure
### Last updated: 2026-03-29 | Version: 1.0

---

# TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Architecture & Infrastructure](#2-architecture--infrastructure)
3. [Declassified Pipeline (V9)](#3-declassified-pipeline-v9)
4. [Marketing System (Complete)](#4-marketing-system)
5. [PostgreSQL Database (v2.1)](#5-postgresql-database-v21)
6. [Integrations](#6-integrations)
7. [Quality Assurance System](#7-quality-assurance-system)
8. [Brand Identity & Web](#8-brand-identity--web)
9. [All Files & Paths](#9-all-files--paths)
10. [Git History & Commits](#10-git-history--commits)
11. [Technical Lessons Learned](#11-technical-lessons-learned)
12. [Design Principles](#12-design-principles)
13. [Session History](#13-session-history)
14. [Current State & Pending Items](#14-current-state--pending-items)
15. [Operational Playbook](#15-operational-playbook)

---

# 1. PROJECT OVERVIEW

## What we're building

**OpenClaw** is a multi-agent AI orchestration platform running on WSL Ubuntu. The primary commercial application is **Declassified Cases** (declassified.shop) — a weekly AI-generated mystery detective game sold as digital download.

The system has two major subsystems:
1. **Declassified Pipeline (V9)** — generates the mystery cases (PDFs with documents, evidence, suspects)
2. **Marketing System** — generates all marketing content, manages campaigns, tracks growth, and will publish to social media

Both are fully AI-operated with human gates for approval.

## Key People & Accounts

- **Owner:** Alfredo Pretel (Alf)
- **Target audience:** Americans in USA (English-first, Spanish secondary)
- **Store:** declassified.shop (React + Vite + Supabase + Stripe)
- **GitHub:** pr3t3l/openclaw-config (unified repo), pr3t3l/declassifiedcase (web store)
- **Stripe:** acct_1SqwSeAcsyW8mQQC (Declassified Case)
- **Email domain:** declassified.shop (verified in Resend)

## Pricing

- Single case (e.g., Linda Oward): $12.00 USD
- Pack 4 cases: $59.00 USD
- Future target: $19.99 per case

---

# 2. ARCHITECTURE & INFRASTRUCTURE

## Hardware & OS

- Dedicated laptop running Windows with WSL Ubuntu
- Username: robotin (WSL) / robot (Windows)
- Home: /home/robotin/
- Windows Downloads: /mnt/c/Users/robot/Downloads/

## Services Running

| Service | Port | Purpose |
|---------|------|---------|
| OpenClaw Gateway | 18789 | Agent orchestration |
| LiteLLM Proxy | 4000 | Model routing + cost tracking |
| PostgreSQL 16 | 5432 | Database (litellm_db) |
| Tailscale | — | Remote access (pretel-laptop.tail600a27.ts.net) |

## Telegram Bots

| Bot | Workspace | Purpose |
|-----|-----------|---------|
| @Robotin1620_Bot | workspace/ | CEO agent |
| @APVDeclassified_bot | workspace-declassified/ | Declassified pipeline |
| @Super_Workflow_Creator_bot | workspace-meta-planner/ | Meta Planner |

## Model Routing (March 2026)

| Use Case | Model | Via |
|----------|-------|-----|
| CEO orchestrator | MiniMax M2.7 | OpenRouter |
| Declassified orchestrator | GPT-5.2 medium | LiteLLM (frozen) |
| ALL creative/render tasks | Claude Sonnet 4.6 | Direct API (NEVER CHANGE) |
| Pipeline skills | chatgpt-gpt54 | LiteLLM OAuth |
| Meta Planner debates | chatgpt-gpt54 | LiteLLM |
| Marketing quality reviewer | Claude Sonnet 4.6 | LiteLLM (claude-sonnet46) |

**Model tiers:**
- Tier S reasoning: Gemini 3.1 Pro, GPT-5.4, Claude Opus 4.6
- Tier A agentic/value: MiniMax M2.7, Kimi K2.5
- Tier B budget: Gemini Lite, GPT-5 Mini
- **ABSOLUTE RULE: NO mini or nano models anywhere in the system**

## LiteLLM Configuration

- Config: `~/.config/litellm/config.yaml`
- Env: `~/.config/litellm/litellm.env`
- Database URL: `postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db`
- 23 models configured
- Codex OAuth for all GPT usage (Pro $200/mo, $0/token)
- Dashboard at :4000 (no auth, localhost-only — TL-12)

## OpenClaw Configuration

- Config: `~/.openclaw/openclaw.json`
- Version: v2026.3.13
- Two permission layers: models.providers.litellm.models AND agents.defaults.models (both must be updated together)

---

# 3. DECLASSIFIED PIPELINE (V9)

## Pipeline Phases (10 total)

1. **Init** — start_new_case.sh
2. **Narrative Architect** — case-plan.json + clue_catalog.json (~$0.80-1.00)
3. **Art Director** — art_briefs.json (POI portraits ONLY) + scene_descriptions.json (~$0.25)
4. **Experience Designer** — experience_design.json (emotional beats + detective annotations) (~$0.25)
5. **Production Engine** — _content.md per document, one envelope at a time (~$1.50)
6. **Playthrough QA** — simulated player walkthrough + benchmark scoring (~$1.00)
7. **Image Generator** — POI portraits only, 4-6 per case (~$0.10)
8. **AI Render** — ai_render.py: Claude Sonnet → HTML → Chromium → PDF (~$2.00)
9. **Package + Validate** — merge PDFs per envelope, validate_final.py
10. **Distribution** — ZIP → Google Drive → Telegram

**Total cost target: $6-8 per case**

## Cases Completed

1. Case 1 — completed
2. Case 2 — completed
3. Case 3: "The Miracle Withdrawal" (medication-that-cures-too-well-gpt) — completed ($4.46, 21 docs)
4. Case 4: cyber-ghost — in progress

## V9 Key Decisions

- ALL document rendering via Claude Sonnet API (zero templates)
- POI portraits are the ONLY pre-generated images
- doc_type_catalog.json replaces template_registry.json
- sessions_spawn CANNOT write files — use spawn_agent.py / spawn_narrative.py
- Python requests FAILS in WSL — use streaming curl via subprocess
- POI portraits: 100px JPEG q70 (~$0.004/image)

## Quality Framework (6 pillars, 60 points)

1. User Experience / Emotional Arc (2x weight, MOST IMPORTANT)
2. Information Relevance
3. Clue Structure and Cognitive Load
4. Visual Support
5. Dynamic Clue Variety
6. Document as Experience

---

# 4. MARKETING SYSTEM

## Overview

Fully automated marketing content generation system built on OpenClaw. Generates weekly campaigns segmented by buyer persona with A/B testing, quality gates, and growth intelligence feedback loop.

## Components

### 4.1 Runtime Layer (8 scripts)
- `llm_caller.py` — unified LLM calling via LiteLLM
- `telegram_sender.py` — Telegram notifications
- `preflight_check.py` — pre-run validation
- `state_lock_manager.py` — prevents concurrent runs
- `artifact_validator.py` — validates JSON output
- `rollback_executor.py` — rollback on failure
- `gate_handler.py` — human approval gates
- `runtime_orchestrator.py` — coordinates everything

### 4.2 Strategy Layer (5 skills + runner)
Skills in `~/.openclaw/marketing-system/skills/`:
- `market-analysis` — 4-tier competitor matrix, TAM/SAM/SOM
- `buyer-persona` — 5-10 segments by use case (currently 6)
- `brand-strategy` — paradigm shift + 25 creative angles
- `seo-architecture` — 60-100 keywords (currently 105)
- `channel-strategy` — segment×trigger×channel matrix

Runner: `strategy_runner.py` — generates all 5 artifacts, 2 gates (S1, S2)

### 4.3 Marketing Weekly Layer (5 skills + runner)
- `script-generator` — 12 reel scripts in 6 creative lanes
- `ad-copy-generator` — 12 ads in 4 sets by persona
- `email-generator` — 6 emails in 3 behavioral sequences
- `calendar-generator` — weekly publishing schedule
- `quality-reviewer` — 10-point strategic checklist, HARD BLOCK on criticals (uses Sonnet)

Runner: `marketing_runner.py` — generates all assets, claim linter, quality reviewer, 2 gates (M1, M2)

### 4.4 Growth Intelligence Layer (3 deterministic + 3 LLM skills + runner)
Deterministic:
- `metrics-calculator` — calculate CPM, CTR, CPA, ROAS from raw data
- `experiment-manager` — register/close experiments
- `pattern-promoter` — promote tentative → confirmed patterns

LLM:
- `metrics-interpreter` — weekly performance narrative
- `diagnosis-agent` — root cause analysis + creative decay detection
- `learning-extractor` — extract winning/losing patterns

Runner: `growth_runner.py` — 10-step pipeline, 1 gate (G1)

### 4.5 Additional Skills
- `video-prompt-generator` — generates Veo3 + DALL-E prompts from case brief
- `strategy-report-generator` — HTML summary report

### 4.6 Case Bridge
- `case_to_brief.py` — extracts enriched weekly_case_brief.json (19K chars) from pipeline output
- Includes: scenes for video, POI headshot prompts, key clues for hooks, emotional arc, hook angles
- Anti-spoiler verified (never reveals the culprit)

## Strategy v2 (Approved)

Generated with the rewritten professional skills:
- **6 buyer segments:** couples_date_night, game_night_hosts, true_crime_solo, gift_buyers, family_detectives, educators
- **105 SEO keywords** across 5 pillar pages
- **25 creative angles** for content variation
- **4-tier competitor matrix:** Hunt A Killer, Unsolved Case Files, Cold Case Inc, Escape Room Kits
- **Segment × trigger × channel matrix** for targeting

## Weekly Cycle (Operational Manual)

Sunday: Prepare brief (case_to_brief.py if new case)
Monday: AI generates content → human reviews → approves
Tue-Fri: Human publishes (manual now, automated later)
Saturday: Collect metrics → Growth Intelligence
~3-4 hours/week human time




##TELEGRAM OPERATIONS BOT — Quick Reference
Appendix to Project Bible
Bot: Uses @Robotin1620_Bot token (TELEGRAM_BOT_TOKEN in .env)
Security: Only responds to user_id 8024871665
Start: python3 ~/.openclaw/marketing-system/scripts/telegram_ops.py
Kill: pkill -f "python3 telegram_ops.py"

SUBFASE 4A — IMPLEMENTED ✅
System Reports
CommandWhat it does/helpList all available commands/statusFull system overview: projects, strategy, campaigns, assets, KB, experiments + health checks (PostgreSQL, LiteLLM, Stripe)/strategy report <product_id>Strategy summary: competitors, segments, positioning, keywords, creative angles/week brief <product_id> <week>Weekly run summary: case, assets generated, QA status, approval state/growth report <product_id> <week>Growth diagnosis: root cause, winning/losing patterns, experiments
Database Queries
CommandWhat it does/db segments <product_id>List buyer segments with priority/db assets <product_id> [week]Assets by type and status/db campaigns <product_id>Active campaigns with metrics/db experiments <product_id>Experiments with status/db kb <product_id>Knowledge base patterns/db orders [days]Recent Stripe orders

SUBFASE 4B — PENDING 🔲
Weekly Cycle Operations
CommandWhat it does/week start <product_id> <week> [case_dir]Start full cycle: brief → marketing → claim linter/week media <product_id> <week>Generate videos (Veo3) + images (DALL-E)/week approve <product_id> <week>Approve run, promote assets/week emails <product_id> <week> [--test email]Send emails via Resend/sync stripe [days]Run stripe_sync.py/growth <product_id> <week>Execute Growth Intelligence/override lint <product_id> <week> "reason"Override claim linter (requires reason)

EXAMPLE WEEKLY FLOW FROM TELEGRAM
/week start misterio-semanal 2026-W18
  → Bot runs marketing_runner.py, reports results

/week brief misterio-semanal 2026-W18
  → Review what was generated

/week media misterio-semanal 2026-W18
  → Generate Veo3 videos + DALL-E images

/week approve misterio-semanal 2026-W18
  → Approve and promote assets

/week emails misterio-semanal 2026-W18 --test your@email.com
  → Test email send

/sync stripe 7
  → Sync last 7 days of Stripe payments

/growth misterio-semanal 2026-W18
  → Run Growth Intelligence after metrics collected

---

# 5. POSTGRESQL DATABASE (v2.1)

## Connection

```
postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db
Schema: marketing
```

## Tables (24 total)

Cross-reviewed with GPT-5.4 (2 rounds). All fixes applied:

| # | Table | Purpose |
|---|-------|---------|
| 1 | projects | Business/brand top-level |
| 2 | strategy_versions | Parent table for strategy versioning (PK: project_id, version) |
| 3 | product_catalog | Items with JSONB variants |
| 4 | strategy_outputs | 1 row per strategic artifact |
| 5 | buyer_segments | Reusable segments across campaigns |
| 6 | campaigns | Multi-week marketing campaigns |
| 7 | campaign_products | Normalized campaign ↔ product |
| 8 | campaign_target_segments | Normalized campaign ↔ segment |
| 9 | campaign_runs | Weekly execution within a campaign |
| 10 | assets | Creative pieces with structural IDs |
| 11 | asset_metrics_base | Universal metrics per asset |
| 12 | asset_metrics_video | Video metrics (hook_rate, hold_rate, etc.) |
| 13 | asset_metrics_email | Email metrics (open_rate, click_rate, etc.) |
| 14 | asset_metrics_search | Google Ads metrics |
| 15 | asset_metrics_landing | Landing page metrics |
| 16 | platform_metrics_weekly | Aggregated by platform |
| 17 | seo_metrics | Search Console data |
| 18 | orders | Stripe mirror for attribution |
| 19 | conversion_events | Generic events (purchase, lead, quote, etc.) |
| 20 | growth_analyses | Growth Intelligence diagnoses |
| 21 | decisions | Post-Growth decision registry |
| 22 | knowledge_base | Winning/losing patterns + learned concepts |
| 23 | experiments | A/B test lifecycle |
| 24 | gates | Human decision log |

## Key Design Decisions

- `week_start_date DATE` instead of `week TEXT` (with `iso_week GENERATED`)
- CHECK constraints on ALL status/type fields
- Idempotency keys (GENERATED) on all ingestion tables
- ON DELETE CASCADE on metric child tables
- Composite FKs (project_id, version) for strategy consistency
- `campaign_products` and `campaign_target_segments` as intermediary tables (no TEXT[] arrays)
- `conversion_events` generic table ready for non-ecommerce (leads, appointments, etc.)
- `decisions` table separate from `growth_analyses` (diagnosis ≠ action)

## Wrapper: db.py (46 functions)

Location: `~/.openclaw/marketing-system/scripts/db.py` (926 lines)
Covers: CRUD for all tables + 4 analytics queries (best_performing_assets, creative_decay_check, segment_performance, campaign_roi)

## Migration

`migrate_json_to_db.py` — imports existing JSON data. Idempotent.
Migrated: 1 project, 2 strategy versions, 10 outputs, 6 segments, 1 campaign, 3 runs, 15 assets, 3 KB entries, 3 experiments.

## Runners Dual-Write

All 3 runners (strategy, marketing, growth) write to PostgreSQL AND JSON:
- DB = source of truth
- JSON = backup/export
- Safe wrapper: `_db_write(fn, *args)` — logs errors, never blocks runner
- Parity check: `verify_db_parity.py` — 7 checks, all pass

---

# 6. INTEGRATIONS

## Veo 3 (Video Generation)

- Script: `generate_marketing_videos.py`
- SDK: `google-genai` (Gemini API)
- Model: `veo-3.0-fast-generate-001` ($0.15/sec = $1.20/8s video)
- Standard model: `veo-3.0-generate-001` ($0.40/sec = $3.20/8s video)
- API Key: GOOGLE_API_KEY in .env
- Test: 1MB video generated in ~60s
- Supports 9:16 vertical (TikTok/Reels) + 1080p
- Commit: a82d610

## DALL-E 3 (Image Generation)

- Script: `generate_marketing_images.py`
- Model: dall-e-3 via LiteLLM
- Added to LiteLLM config (needs proxy restart to test)
- API Key: OPENAI_API_KEY

## Resend (Email)

- Script: `send_marketing_emails.py`
- API Key: RESEND_API_KEY in .env
- Domain: declassified.shop (verified)
- From: cases@declassified.shop
- Test: 6/6 emails sent successfully
- Config: `~/.openclaw/marketing-system/config/email_config.json`
- Commit: 9f4d306

## Stripe (Payments)

- Script: `stripe_sync.py`
- CLI: stripe v1.39.0 installed
- Account: acct_1SqwSeAcsyW8mQQC (Declassified Case)
- API Key: STRIPE_API_KEY in .env (live key)
- Syncs payment_intents → marketing.orders with UTM attribution
- Test: Connected successfully, 0 orders (no sales yet)
- Commit: eb4b3a5

## LiteLLM (Model Proxy)

- 23 models configured
- Codex OAuth for GPT (Pro subscription, $0/token)
- PostgreSQL spend tracking + dashboard
- Config: `~/.config/litellm/config.yaml`



---

# 7. QUALITY ASSURANCE SYSTEM

## Problem

W17 original had 24 critical issues: 14 fabricated testimonials, 8 invented facts, 4 forbidden claims.

## Solution (3 layers)

### Layer 1: verified_facts in product_brief.json
15 verified data points (price, duration, players, documents, etc.)
7 allowed claims, 10 forbidden claims

### Layer 2: claim_linter.py (deterministic, no LLM)
- 16 fabrication patterns (testimonials, guarantees, exclusivity, comparisons, invented data)
- 7 fact verifiers (documents, hours, price, players, envelopes, cases)
- Runs BEFORE quality reviewer
- HARD BLOCK if critical violations found
- Exit code 1 = pipeline stops

### Layer 3: quality-reviewer skill (Sonnet)
- 10-point strategic checklist
- HARD BLOCK if critical_issues > 0
- Changed from GPT to Sonnet (handles 75K+ context better)

### Layer 4: Anti-fabrication rules in 3 skills
Added "Verified Facts (MANDATORY)" section to script-generator, ad-copy-generator, email-generator

## Results

| Metric | W17 Original | W17 Hardened | Improvement |
|--------|-------------|-------------|-------------|
| Claim linter | 13 critical | **0** | 100% eliminated |
| QA criticals | 24 | **~4** | 83% reduction |
| Fabrications | 14 | **0** | 100% eliminated |
| Fact errors | 8 | **0** | 100% eliminated |
| Forbidden claims | 4 | **0** | 100% eliminated |

## Pipeline Order (marketing_runner.py)

1. script_generator → 2. ad_copy_generator → 3. email_generator → 4. Gate M1 → 5. calendar_generator → **6. claim_linter (HARD BLOCK)** → 7. quality_reviewer (only if lint passes) → 8. Gate M2

---

# 8. BRAND IDENTITY & WEB

## Brand Guide (Completed)

Created by design chat — 8-page PDF + 14 SVG assets.

### Colors
| Name | Hex | Usage |
|------|-----|-------|
| Espresso | #2c2520 | Dark backgrounds, primary text |
| Parchment | #f5e6d0 | Light backgrounds |
| Dried blood | #9b2c2c | Accent, CTAs (MAX 10%) |
| Sand | #d4c4a8 | Text on dark |
| Charcoal | #1a1714 | Deepest dark |
| Leather | #463b32 | Cards, secondary surfaces |
| Ash | #8a7e6a | Muted text |
| Vivid red | #c0392b | Hover states |
| Ivory | #e8dcc8 | Subtle accent |

Rule: 70% espresso/parchment — 20% sand/ash — 10% dried blood

### Typography
- Display: Courier Prime (logo, stamps, case numbers) — always uppercase
- Heading: Playfair Display (headlines, marketing copy) — emotional weight
- Body: Source Sans 3 (UI, descriptions) — clean, readable

### SVG Assets (in C:\Users\robot\OneDrive\Documents\Declassified\)
logo_primary_stamp.svg, logo_primary_stamp_dark.svg, icon_light.svg, icon_dark.svg, icon_red.svg, lockup_narrative.svg, wordmark_horizontal.svg, wordmark_horizontal_dark.svg, favicon.svg, stamp_open.svg, stamp_classified.svg, element_redaction_bars.svg, element_redaction_bars_dark.svg

### Brand Rules (NEVER violate)
1. Red is always 10% — only in accent lines, stamps, CTAs
2. No emojis in main content
3. No gradients, shadows, or glow effects
4. Dark bg = Espresso or Charcoal, NEVER pure black
5. Light bg = Parchment, NEVER pure white
6. "OPEN" stamp always rotated -10° to -15°
7. The red line is sacred — appears in every section

## Web Store (declassified.shop)

### Stack
- Frontend: React + Vite + TypeScript + Tailwind CSS + shadcn/ui
- Backend: Lovable Cloud (Supabase)
- Payments: Stripe Checkout
- Emails: Resend API
- Analytics: GA4
- Repo: github.com/pr3t3l/declassifiedcase

### Current Flow (to be optimized)
Landing → Case page → Context → Decision → Stripe → Success + Download

### Planned Flow (post-redesign)
Landing → Case page (ALL info + CTA) → Stripe → Success + Download
(Remove intermediate context/decision pages)

### Implementation Document
`DECLASSIFIED_IMPLEMENTATION_FOR_CODE.md` — 1172 lines, 6 phases:
1. Design system setup (Tailwind, fonts, SVGs)
2. React components (14 brand components)
3. Page layouts (homepage, case landing, catalog, persona landings, blog)
4. Purchase flow optimization (UTM tracking, remove intermediate pages)
5. Future-proofing (multi-language, content API, social proof)
6. Implementation order

---

# 9. ALL FILES & PATHS

## OpenClaw Core
```
~/.openclaw/openclaw.json                    — OpenClaw config
~/.openclaw/.env                              — All API keys (Anthropic, OpenAI, Google, Stripe, Resend, Telegram)
~/.config/litellm/config.yaml                — LiteLLM model routing
~/.config/litellm/litellm.env                — LiteLLM env vars
```

## Marketing System
```
~/.openclaw/marketing-system/
├── skills/                                   — 15 skills (SKILL.md each)
│   ├── market-analysis/
│   ├── buyer-persona/
│   ├── brand-strategy/
│   ├── seo-architecture/
│   ├── channel-strategy/
│   ├── script-generator/
│   ├── ad-copy-generator/
│   ├── email-generator/
│   ├── calendar-generator/
│   ├── quality-reviewer/
│   ├── video-prompt-generator/
│   ├── strategy-report-generator/
│   ├── metrics-interpreter/
│   ├── diagnosis-agent/
│   └── learning-extractor/
├── scripts/
│   ├── strategy_runner.py                    — Strategy generation (5 artifacts, 2 gates)
│   ├── marketing_runner.py                   — Marketing weekly (5 phases, claim linter, QA, 2 gates)
│   ├── growth_runner.py                      — Growth Intelligence (10 steps, 1 gate)
│   ├── runtime_orchestrator.py               — Coordinates everything
│   ├── db.py                                 — PostgreSQL wrapper (46 functions, 926 lines)
│   ├── migrate_json_to_db.py                 — JSON → PostgreSQL migration
│   ├── verify_db_parity.py                   — JSON vs DB parity check
│   ├── claim_linter.py                       — Deterministic claim verification (HARD BLOCK)
│   ├── case_to_brief.py                      — Pipeline → marketing bridge
│   ├── generate_marketing_videos.py          — Veo 3 video generation
│   ├── generate_marketing_images.py          — DALL-E 3 image generation
│   ├── send_marketing_emails.py              — Resend email sending
│   ├── stripe_sync.py                        — Stripe → PostgreSQL sync
│   ├── llm_caller.py                         — Unified LLM calling
│   ├── telegram_sender.py                    — Telegram notifications
│   ├── preflight_check.py
│   ├── state_lock_manager.py
│   ├── artifact_validator.py
│   ├── rollback_executor.py
│   ├── gate_handler.py
│   ├── metrics_calculator.py
│   ├── experiment_manager.py
│   └── pattern_promoter.py
│   └── sql/
│       └── create_schema_v2.1.sql            — PostgreSQL schema (477 lines)
└── config/
    ├── email_config.json                     — Resend config (from: cases@declassified.shop)
    └── telegram_security.json
```

## Product Data
```
~/.openclaw/products/misterio-semanal/
├── product_brief.json                        — With verified_facts, allowed_claims, forbidden_claims
├── product_manifest.json
├── knowledge_base_marketing.json
├── experiments_log.json
├── metrics_model.json
├── strategies/
│   ├── v2/                                   — Active strategy (approved)
│   │   ├── market_analysis.json
│   │   ├── buyer_persona.json
│   │   ├── brand_strategy.json
│   │   ├── seo_architecture.json
│   │   ├── channel_strategy.json
│   │   └── strategy_manifest.json
│   └── _archived_v1_baseline/
├── weekly_runs/
│   ├── 2026-W14/                             — Completed
│   ├── 2026-W15/                             — Completed
│   └── 2026-W17/                             — Completed (hardened QA)
│       ├── drafts/
│       ├── approved/
│       ├── growth/
│       ├── claim_lint_report.json
│       └── run_manifest.json
└── runtime/
    ├── runtime_state.json
    └── invalidation_log.json
```

## Declassified Pipeline
```
~/.openclaw/workspace-declassified/
├── AGENTS.md                                 — 461-line orchestrator
├── skills/                                   — 10 pipeline skills
├── cases/
│   ├── scripts/                              — ai_render.py, spawn_agent.py, etc.
│   ├── config/                               — design_system.json, doc_type_catalog.json
│   ├── render/                               — render_pdf_system_chromium.js, merge_pdfs.js
│   └── exports/<slug>/                       — Case outputs
```

## Documents Created This Session
```
/mnt/user-data/outputs/
├── claude_code_prompt_rewrite_skills_v1.1_final.md
├── claude_code_prompt_case_bridge.md
├── claude_code_prompt_integrations_veo3_resend.md
├── claude_code_prompt_postgresql_v2.1_final.md
├── claude_code_prompt_phase1_qa_hardening.md
├── claude_code_prompt_phase2_runners_db.md
├── claude_code_prompt_phase4_telegram_ops_v2.md
├── postgresql_schema_redesign_for_gpt_review.md
├── postgresql_schema_v2_for_second_review.md
├── research_dtc_marketing_best_practices_2026.md
├── human_ai_operations_manual.md
├── plan_next_session_for_gpt_review.md
├── prompt_for_design_chat_coeditor.md
├── prompt_redesign_v2_declassified_shop.md
└── DECLASSIFIED_IMPLEMENTATION_FOR_CODE.md     — (uploaded by user, 1172 lines)
```

---

# 10. GIT HISTORY & COMMITS

Repository: `pr3t3l/openclaw-config`

| Commit | Description |
|--------|-------------|
| faf052f | feat: Finance Tracker + Marketing System (80 files, 8,708 lines) |
| 37b3022 | fix: anti-fabrication rule, quality reviewer on Sonnet, DALL-E 3 config |
| a82d610 | feat: Veo 3 video generation + Resend email sending integrations |
| 9f4d306 | fix: update email_config to verified domain declassified.shop |
| 66a7c0f | feat: PostgreSQL schema v2.1 + db.py wrapper + JSON migration |
| ed5ac57 | feat: QA compliance hardening — verified_facts + claim_linter + skill updates |
| b0a16f2 | feat: runners dual-write to PostgreSQL + JSON backup + parity check |
| eb4b3a5 | feat: Stripe → PostgreSQL sync for marketing.orders |

---

# 11. TECHNICAL LESSONS LEARNED

| ID | Lesson | Impact |
|----|--------|--------|
| TL-01 | Python requests DIES in WSL for long API calls. Use streaming curl via subprocess. | Critical — affects all Anthropic API calls |
| TL-02 | POI portraits: 100px JPEG q70 = $0.004/image (15x cheaper than 200px PNG) | Cost optimization |
| TL-03 | cost_tracker.py: always use `(totals.get('field') or 0)` for None-safe access | Bug prevention |
| TL-04 | sessions_spawn cannot write files. Use spawn_agent.py / spawn_narrative.py | Architecture |
| TL-11 | OpenClaw v2026.3.2 doesn't resolve `${ENV_VARS}` in apiKey. Hardcode or skip master_key | Config |
| TL-12 | LiteLLM dashboard login = master_key, but master_key breaks OpenClaw auth. Dashboard runs without auth (localhost-only) | Config conflict |
| TL-13 | SKILL.md MUST include exact JSON schema inline with types. Models produce incompatible output without it | Prompt engineering |
| TL-14 | asyncio parallel debate fails in WSL. Sequential fallback works | WSL limitation |
| TL-15 | LiteLLM model names ≠ provider names (e.g., `claude-sonnet46` not `claude-sonnet-4-6`) | Config |
| TL-16 | M2.7 ignores complex AGENTS.md routing. Not reliable for multi-step orchestration | Model limitation |
| TL-17 | Sonnet truncates/breaks JSON above ~8K output tokens. Generate by blocks, not monolithic | Architecture |
| TL-18 | PostgreSQL GENERATED columns cannot use ::TEXT casts directly. Create IMMUTABLE helper functions | PostgreSQL |
| TL-19 | ON CONFLICT with GENERATED column indexes: use `ON CONFLICT (column_name)` not the expression | PostgreSQL |
| TL-20 | WSL services don't auto-start. Use .bat in Windows Startup folder with keepalive loop | Operations |
| TL-21 | Veo 3 model names use `-001` suffix not `-preview` (e.g., `veo-3.0-fast-generate-001`) | API |
| TL-22 | `echo >>` for .env can create duplicates if run multiple times. Edit with nano instead | Operations |

---

# 12. DESIGN PRINCIPLES

## Architecture & Design

1. **Always design complete/Advanced from the start — never MVP.** With AI implementing, the difference is minutes not weeks.
2. **No patches — fix the root system.** When output is mediocre, rewrite the skill/prompt that produces it.
3. **For implementation-ready docs, skip the meta-planner and go direct to Code.** Planner adds value for raw, unstructured ideas.
4. **Large artifacts must be generated by domain blocks and consolidated** — never as monolithic JSON (TL-17).
5. **Cross-model review (Claude + GPT + Gemini + M2.7)** for all major architectural decisions before implementation.

## Model Routing

6. **Sonnet 4.6 is untouchable for render/creative** — unanimous cross-model consensus.
7. **No mini or nano models anywhere in the system** — not for QA, reporting, formatting, nothing.
8. **OpenRouter for new/experimental models only**, not replacing direct API.

## Quality & Compliance

9. **Claim linter is fail-closed** — if it detects violations, the pipeline stops. No exceptions without explicit override with documented reason.
10. **verified_facts as single source of truth** — generators use ONLY data from verified_facts. If it's not in verified_facts, it doesn't exist.
11. **DB = source of truth, JSON = backup export** — dual-write during migration, but DB is authoritative.

## Operations

12. **Budget-conscious** — track costs of every API call. Monthly budget ~$50.
13. **Report only failures** — if something works, assume it works. Don't ask "did that work?"
14. **Cross-model review before implementation** — produces significantly better results than single-model analysis.

---

# 13. SESSION HISTORY

## Session 1: 2026-03-26 (Previous chat)
- Meta-Planner v3.1 upgrade planning
- Marketing System architecture design (strategy + marketing + growth + runtime)
- Frozen docs created
- Initial Claude Code implementation attempt

## Session 2: 2026-03-28 to 2026-03-29 (This chat — MASSIVE)

### Part 1: Planner closure + Marketing implementation
- Closed strategy-runtime-1 planner run (3 gates)
- Claude Code implemented entire Marketing System in ~35 minutes (4A-4D)
- 80 files, 8,708 lines, commit faf052f

### Part 2: Quality audit + Skills rewrite
- Discovered strategy v1 output was poor (1 persona, 0 keywords, wrong audience)
- DTC marketing research (30+ sources)
- GPT cross-review (11 patches)
- 13 skills rewritten to professional level
- Strategy v2 generated (6 personas, 105 keywords, 25 angles)

### Part 3: Case bridge + Dry run
- Created case_to_brief.py connecting pipeline → marketing
- Dry run with "The Miracle Withdrawal" — content references real suspects, settings
- Anti-spoiler verified

### Part 4: Integrations
- Veo 3: video generated in 60s, $1.20/video
- Resend: 6/6 emails sent, domain verified (declassified.shop)
- DALL-E 3: configured in LiteLLM

### Part 5: 3 Fixes
- Anti-fabrication rules in 3 skills
- Quality reviewer changed to Sonnet
- DALL-E 3 added to LiteLLM config

### Part 6: PostgreSQL v2.1
- Schema designed, cross-reviewed with GPT (2 rounds)
- 6 major fixes applied (strategy_versions, campaign_products, asset_metrics split, week_start_date, CHECK constraints, idempotency keys)
- 24 tables created, db.py with 46 functions, migration completed

### Part 7: QA Compliance Hardening (Phase 1 of GPT plan)
- verified_facts + allowed_claims + forbidden_claims in product_brief
- claim_linter.py with 16 patterns + 7 verifiers
- Integrated into marketing_runner.py (between calendar and quality reviewer)
- Results: 0 claim violations (was 13), ~4 QA criticals (was 24)

### Part 8: Runners → DB (Phase 2)
- 3 runners modified with dual-write
- verify_db_parity.py: 7/7 checks pass

### Part 9: Stripe (Phase 3)
- stripe_sync.py created
- Stripe CLI installed
- Connected to live account (0 orders — no sales yet)

### Part 10: Brand Identity + Web Redesign
- Brand guide created (8 pages, 14 SVGs) by design chat
- Implementation document (1172 lines) for Code
- 5 fixes identified (price hardcoding, testimonial placeholders, etc.)
- Target audience corrected: Americans, not hispanics

### Part 11: Telegram Ops (Phase 4 — in progress)
- Prompt created for subfase 4A (read-only commands + reports)
- GPT reviewed and approved with 6 adjustments
- Ready for implementation

---

# 14. CURRENT STATE & PENDING ITEMS

## COMPLETED ✅

| # | What | When |
|---|------|------|
| 1 | Marketing System full implementation (runtime + strategy + marketing + growth) | Session 2 |
| 2 | 13 skills rewritten to professional level | Session 2 |
| 3 | Strategy v2 generated and approved | Session 2 |
| 4 | Case bridge (pipeline → marketing) | Session 2 |
| 5 | Veo 3 integration (video generation) | Session 2 |
| 6 | Resend integration (email sending) | Session 2 |
| 7 | PostgreSQL v2.1 (24 tables, db.py, migration) | Session 2 |
| 8 | QA compliance hardening (claim linter, verified_facts) | Session 2 |
| 9 | Runners dual-write to DB | Session 2 |
| 10 | Stripe sync script | Session 2 |
| 11 | Brand guide + SVG assets | Session 2 |
| 12 | Web redesign implementation document | Session 2 |

## PENDING (GPT-approved plan) 🔲

| Phase | What | Status |
|-------|------|--------|
| 4A | Telegram ops bot (read-only + reports) | Prompt ready, not yet executed |
| 4B | Telegram ops bot (operations — /week start, approve, etc.) | Designed, after 4A |
| 5 | Google Search Console integration | Needs landing pages first |
| 6 | Meta autopublishing (Instagram/Facebook) | Alf creating accounts now |
| 7 | TikTok/YouTube publishing | After Meta |
| 8 | weekly_cycle.py orchestrator | After all above are stable |
| — | Web redesign implementation | Document ready for Code |
| — | DALL-E 3 test | LiteLLM proxy needs restart |
| — | Full E2E run with new case | After integrations |
| — | Declassified skills → dedicated agents migration | Post quality milestone |
| — | Meta-Planner Deep Analysis upgrade v3.1 | Designed, not implemented |

## KEY DECISIONS STILL PENDING

1. **A/B test M2.7 vs current CEO model** (Phase 6B of optimization) — required before any orchestrator migration
2. **Migrate runners to DB-only** (remove JSON as primary) — after confirming DB stability
3. **Landing pages for SEO** — need to be created in the web store before Search Console has data
4. **Free mini case lead magnet** — needs to be designed and produced
5. **Multi-language infrastructure** — English primary, Spanish secondary, structure now but implement later

---

# 15. OPERATIONAL PLAYBOOK

## Starting Services (after WSL restart)

```bash
# 1. PostgreSQL
sudo service postgresql start

# 2. LiteLLM
source /home/robotin/litellm-venv/bin/activate
cd /home/robotin/.config/litellm
set -a; source litellm.env; set +a
nohup litellm --config config.yaml --host 127.0.0.1 --port 4000 &

# 3. OpenClaw (if needed)
# Check ~/.openclaw/ for startup script

# 4. Verify
curl -s -H "Authorization: Bearer sk-litellm-local" http://127.0.0.1:4000/health | head -5
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db" -c "SELECT COUNT(*) FROM marketing.projects;"
```

## Weekly Marketing Cycle (Manual — until Telegram bot is ready)

```bash
cd ~/.openclaw/marketing-system/scripts

# Step 1: Create brief from case (if new case this week)
python3 case_to_brief.py misterio-semanal 2026-W18 /path/to/case/

# Step 2: Generate marketing content
python3 marketing_runner.py misterio-semanal 2026-W18

# Step 3: Review claim linter results
cat ~/.openclaw/products/misterio-semanal/weekly_runs/2026-W18/claim_lint_report.json | python3 -m json.tool

# Step 4: Generate media
python3 generate_marketing_videos.py misterio-semanal 2026-W18
python3 generate_marketing_images.py misterio-semanal 2026-W18

# Step 5: Approve
python3 marketing_runner.py misterio-semanal 2026-W18 approve

# Step 6: Send emails
python3 send_marketing_emails.py misterio-semanal 2026-W18 --dry-run

# Step 7: Sync Stripe (after sales)
python3 stripe_sync.py misterio-semanal --days 7

# Step 8: Growth Intelligence (after metrics collected)
python3 growth_runner.py misterio-semanal 2026-W18
```

## Database Quick Queries

```sql
-- Connect
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db"

-- Overview
SELECT 'projects' as t, COUNT(*) FROM marketing.projects
UNION ALL SELECT 'strategies', COUNT(*) FROM marketing.strategy_versions
UNION ALL SELECT 'segments', COUNT(*) FROM marketing.buyer_segments
UNION ALL SELECT 'campaigns', COUNT(*) FROM marketing.campaigns
UNION ALL SELECT 'assets', COUNT(*) FROM marketing.assets
UNION ALL SELECT 'kb', COUNT(*) FROM marketing.knowledge_base
ORDER BY 1;

-- Assets by type
SELECT asset_type, COUNT(*) FROM marketing.assets GROUP BY 1;

-- Buyer segments
SELECT segment_id, segment_name, priority FROM marketing.buyer_segments;
```

## DBeaver Connection (Windows)

- Driver: **PostgreSQL** (NOT MySQL)
- Host: localhost
- Port: 5432
- Database: litellm_db
- Username: litellm
- Password: litellm-local-2026
- Navigate to: Schemas → marketing → Tables

---

**END OF DOCUMENT**

*This document is the single source of truth for the entire Declassified Cases + OpenClaw Marketing System project. If everything else is lost, this document + the Git repo can reconstruct the full system.*
