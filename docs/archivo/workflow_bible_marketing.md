# WORKFLOW BIBLE — MARKETING SYSTEM
## Documento técnico autoritativo
### Last verified: 2026-03-29 (audit v2.1)
### Sources: extraction + 14 library files + Bible v2 §9,§12,§17,§18 + system audit

> **Source tags:** `[AUDIT]` = machine-verified 2026-03-29. `[EXT]` = from extraction.
> `[ARCH]` = from system_architecture_marketing.md. `[GROWTH]` = from growth_intelligence_v2.1.
> `[BIBLE]` = from Project Bible v2. `[RESEARCH]` = from DTC research doc.

---

# 1. PURPOSE & CONTEXT

The Marketing System is a fully automated content generation engine with three operational layers. It generates weekly campaigns segmented by buyer persona with A/B testing, quality gates, and a growth intelligence feedback loop.

It runs via scripts in `~/.openclaw/marketing-system/` `[AUDIT]`. The CEO bot (Robotin) currently triggers runs manually. A dedicated Telegram ops bot was coded but is not operational (token conflict).

**Product:** misterio-semanal (Declassified Cases) — the only active product. Architecture supports multi-product (e.g., `velas-artesanales/`). `[ARCH]`

---

# 2. TIMELINE

| Date | Event | Result | Source |
|------|-------|--------|--------|
| 2026-03-26 | System architecture document (3 workflows + runtime) frozen | Foundation design locked | [ARCH] |
| 2026-03-26 | Growth Intelligence v2.1 designed and frozen | 3 deterministic + 3 LLM components | [GROWTH] |
| 2026-03-26 | Marketing workflow idea submitted to Meta-Planner | Run `strategy-runtime-1` | [EXT] |
| 2026-03-28 06:00 | Meta-Planner Phase C completed, Gate 3 approved | Planner done. Decision: "planner was overkill — go direct to Code" | [EXT] |
| 2026-03-28 07:00 | Claude Code implemented entire Marketing System | 80 files, 8,708 lines, 35 minutes. Commit faf052f | [EXT] |
| 2026-03-28 08:00 | Strategy v1 audit: catastrophic failure | 1 persona (should be 10+), 0 keywords, wrong audience ("hispanohablantes") | [EXT] |
| 2026-03-28 09:00 | DTC marketing research (30+ sources) | Creative Strategy Flywheel, 15-30 ad variants/week needed | [RESEARCH] |
| 2026-03-28 10:00 | GPT cross-review of architecture | 11 patches: diagnostic tree, "lanes" concept, structural IDs, hard block on QA | [EXT] |
| 2026-03-28 10:30 | 13 skills rewritten to professional level | 6 minutes via Claude Code | [EXT] |
| 2026-03-28 11:00 | Strategy v2 generated | 6 personas, 105 keywords, 25 creative angles, 4-tier competitors | [EXT] |
| 2026-03-28 12:00 | case_to_brief.py created (Pipeline → Marketing bridge) | 19K char enriched brief. Anti-spoiler verified | [EXT] |
| 2026-03-28 13:00 | Dry run W17 with "The Miracle Withdrawal" | 12 scripts + 12 ads + 6 emails. HARD BLOCK caught 24 criticals | [EXT] |
| 2026-03-28 14:00 | 3 fixes: anti-fabrication, DALL-E config, Sonnet for QA | Commit 37b3022 | [EXT] |
| 2026-03-28 15:00 | Veo 3 + Resend implementation | Video in 60s, 6/6 emails. Commits a82d610, 9f4d306 | [EXT] |
| 2026-03-28 16:00-18:00 | PostgreSQL schema: v1 → GPT review → v2 → GPT review → v2.1 | 24 tables, 33 FK, 142 CHECK. Commit 66a7c0f | [EXT] |
| 2026-03-28 19:30 | db.py created (46 functions, 926 lines) | Full CRUD + analytics wrapper | [EXT] |
| 2026-03-28 20:30 | QA compliance hardening | claim_linter.py (16 patterns, 7 verifiers). Commit ed5ac57 | [EXT] |
| 2026-03-28 21:30 | W17 re-run: 0 claim violations (was 13), ~4 QA criticals (was 24) | 100% fabrication elimination | [EXT] |
| 2026-03-28 22:00 | Runners dual-write to PostgreSQL | 7/7 parity checks pass. Commit b0a16f2 | [EXT] |
| 2026-03-28 22:30 | Stripe integration | stripe_sync.py, CLI v1.39.0, 0 orders. Commit eb4b3a5 | [EXT] |
| 2026-03-29 01:30 | Telegram ops Phase 4A implemented | telegram_ops.py (758 lines). Commit 6c0e2bf | [EXT] |
| 2026-03-29 02:00 | Project Bible v1 created | 911 lines, 15 sections | [EXT] |

---

# 3. ARCHITECTURE — THE 3 LAYERS + RUNTIME

```
                    ┌──────────────────────────────────┐
                    │     RUNTIME / ORCHESTRATOR        │
                    │  Dependencies, versions, gates,    │
                    │  invalidation, Telegram            │
                    └──────┬──────────┬──────────┬──────┘
                           │          │          │
              ┌────────────▼──┐  ┌────▼────────┐ │  ┌───────────────────┐
              │  STRATEGY     │  │ MARKETING   │ │  │ GROWTH            │
              │  (once)       │  │ WEEKLY      │ │  │ INTELLIGENCE      │
              │  5 artifacts  │──►│ (weekly)    │◄┘──│ (post-execution)  │
              └───────────────┘  └─────────────┘    └───────────────────┘
                                         │                     ▲
                                         └─────metrics─────────┘
```

| Layer | Purpose | Runner | Gates | Frequency | Est. cost |
|-------|---------|--------|-------|-----------|-----------|
| **Strategy** | Market analysis, personas, brand, SEO, channels | `strategy_runner.py` | S1, S2 | Once per product, updated quarterly | <$2 |
| **Marketing Weekly** | Scripts, ads, emails, calendar, QA | `marketing_runner.py` | M1, M2 | Weekly per active case | ~$0.09 |
| **Growth Intelligence** | Metrics, diagnosis, patterns, experiments | `growth_runner.py` | G1 | Weekly after metrics collected | ~$0.042 |
| **Runtime** | Coordinates everything, validates strategy, manages state | `runtime_orchestrator.py` | — | Continuous | $0 |

**Non-negotiable rule:** Marketing NEVER runs without a valid, approved strategy. `[ARCH]`

---

# 4. STRATEGY LAYER — 5 SKILLS `[AUDIT]`

The Strategy Layer is product-agnostic. It runs once per product and generates 5 foundational artifacts that feed all downstream marketing. This workflow can be re-used for ANY product (e.g., future candle business, SaaS finance tracker). Just create a new `product_brief.json` and run `strategy_runner.py <new_product_id>`.

| Skill | What it produces | Output file |
|-------|-----------------|-------------|
| market-analysis | 4-tier competitor matrix, TAM/SAM/SOM | `market_analysis.json` |
| buyer-persona | 5-10 segments by use case | `buyer_persona.json` |
| brand-strategy | Paradigm shift + creative angles | `brand_strategy.json` |
| seo-architecture | 60-100 keywords across pillar pages | `seo_architecture.json` |
| channel-strategy | Segment × trigger × channel matrix | `channel_strategy.json` |

**Runner:** `strategy_runner.py` — generates all 5 artifacts, 2 human gates (S1 after personas, S2 after full strategy).

### Current product configuration: misterio-semanal (Declassified Cases)

The following is the APPROVED strategy for `misterio-semanal` specifically. A different product would have completely different personas, keywords, and competitors.

**Strategy v2 (current, approved):** `[BIBLE]`

- **6 buyer segments:** couples_date_night, game_night_hosts, true_crime_solo, gift_buyers, family_detectives, educators
- **105 SEO keywords** across 5 pillar pages
- **25 creative angles** for content variation
- **4-tier competitor matrix:** Hunt A Killer, Unsolved Case Files, Cold Case Inc, Escape Room Kits
- **Segment × trigger × channel matrix** for targeting

v1 archived in `_archived_v1_baseline/`. `[AUDIT]`

**Product location:** `~/.openclaw/products/misterio-semanal/strategies/v2/`

If a new product is added, its strategy would live in `~/.openclaw/products/<new_product_id>/strategies/v1/`.

---

# 5. MARKETING WEEKLY LAYER — 5 SKILLS + CLAIM LINTER `[AUDIT]`

| Skill | What it produces | Output format |
|-------|-----------------|---------------|
| script-generator | 12 reel scripts in 6 creative lanes | JSON array |
| ad-copy-generator | 12 ads in 4 sets by persona | JSON array |
| email-generator | 6 emails in 3 behavioral sequences | JSON array |
| calendar-generator | Weekly publishing schedule | JSON |
| quality-reviewer | 10-point strategic checklist, HARD BLOCK on criticals | Report JSON |

**Runner:** `marketing_runner.py` — 8 phases:

```
1. Preflight (validate strategy exists)
2. Generate scripts (script-generator)
3. Generate ads (ad-copy-generator)
4. Generate emails (email-generator)
5. Generate calendar (calendar-generator)
6. Gate M1 → Human reviews scripts
7. Claim linter (deterministic, HARD BLOCK) ← added in QA hardening
8. Quality reviewer (Sonnet, HARD BLOCK on criticals)
9. Gate M2 → Human approves full package
```

### Creative lanes concept `[RESEARCH]` `[EXT]`

Content is organized in 6 creative lanes (not random topics):
- Each lane targets a specific emotional trigger
- 12 scripts = 2 per lane
- Prevents content fatigue through structured variation

### Claim linter `[AUDIT]` `[EXT]`

**File:** `claim_linter.py` (316 lines)
- 16 regex patterns detecting fabricated claims
- 7 verifiers cross-checking against `verified_facts`
- Data source: `product_brief.json` → `verified_facts` (15 fields) + `allowed_claims` (7) + `forbidden_claims` (10)
- **Fail-closed:** ANY critical violation stops the pipeline. Quality reviewer never runs.
- Integration: line 41 of `marketing_runner.py`: `from claim_linter import lint_assets`
- Result: W17 went from 13 violations → 0, QA criticals from 24 → 4

### Anti-fabrication rules `[EXT]`

3 skills (script-generator, ad-copy-generator, email-generator) have "Verified Facts (MANDATORY)" sections. Generators use ONLY data from `verified_facts`. If a fact isn't verified, it doesn't exist.

---

# 6. GROWTH INTELLIGENCE LAYER `[GROWTH]`

### Principle: "Mide antes de opinar. Diagnostica antes de cambiar." `[GROWTH]`

### Tactical vs Strategic separation `[GROWTH]`

| Level | What it does | Frequency | Who acts |
|-------|-------------|-----------|----------|
| **Tactical** | Week-to-week optimization (copy, timing, targeting) | Weekly | AI proposes, human approves |
| **Strategic** | Market positioning, pricing, audience changes | Quarterly or triggered | Human decides, AI executes |

### Components (3 deterministic + 3 LLM) `[AUDIT]` `[GROWTH]`

| Component | Type | What it does |
|-----------|------|-------------|
| metrics-calculator (`metrics_calculator.py`) | Script ($0) | CTR, CPC, CPM, CPA, ROAS, deltas, trends, threshold flags |
| experiment-manager (`experiment_manager.py`) | Script ($0) | Register/close A/B experiments, track hypothesis→result |
| pattern-promoter (`pattern_promoter.py`) | Script ($0) | Promote tentative → confirmed patterns after evidence threshold |
| metrics-interpreter | LLM skill | Weekly performance narrative from calculated metrics |
| diagnosis-agent | LLM skill | Root cause analysis + creative decay detection |
| learning-extractor | LLM skill | Extract winning/losing patterns → knowledge_base |

**Runner:** `growth_runner.py` — 10-step pipeline, 1 human gate (G1 after diagnosis). `[BIBLE]`

### Feedback loop `[ARCH]`

```
Growth → optimization_actions.json → injected into Marketing Weekly prompts
Growth → knowledge_base_marketing.json → patterns learned (confirmed = use, tentative = suggest)
Growth → strategy_alert.json → Runtime → soft/hard invalidation
```

### Strategy invalidation triggers `[ARCH]`

**Hard invalid** (blocks marketing): price change >20%, audience change, country/language change, positioning change
**Soft invalid** (Telegram asks human): sales drop >30% for 2+ weeks, CPA unsustainable, engagement persistent drop, strategy >90 days old

---

# 7. RUNTIME LAYER — 8 SCRIPTS `[AUDIT]`

| Script | Purpose | Lines |
|--------|---------|-------|
| `runtime_orchestrator.py` | Coordinates all 3 workflows | ? |
| `llm_caller.py` | Unified LLM calling via LiteLLM | ? |
| `telegram_sender.py` | Telegram notifications | ? |
| `preflight_check.py` | Pre-run validation (strategy exists, approved, not invalid) | ? |
| `state_lock_manager.py` | Prevents concurrent runs | ? |
| `artifact_validator.py` | Validates JSON output from skills | ? |
| `rollback_executor.py` | Rollback on failure | ? |
| `gate_handler.py` | Human approval gates via Telegram | ? |

### Version pinning `[ARCH]`

When a weekly run starts, it pins to a specific strategy version. If v3 appears while W14 runs, W14 stays on v2. Immutable once started.

### Manifest system (3 levels) `[ARCH]`

| Manifest | Scope | Written by |
|----------|-------|-----------|
| `product_manifest.json` | Per product | Runtime |
| `strategy_manifest.json` | Per strategy version | Strategy runner |
| `run_manifest.json` | Per weekly execution | Marketing runner |

---

# 8. ALL SCRIPTS — 24 TOTAL `[AUDIT]`

| Script | Category | Purpose |
|--------|----------|---------|
| strategy_runner.py | Runner | Strategy generation (5 artifacts, 2 gates) |
| marketing_runner.py | Runner | Marketing weekly (8 phases, claim linter, QA, 2 gates) |
| growth_runner.py | Runner | Growth Intelligence (10 steps, 1 gate) |
| runtime_orchestrator.py | Runtime | Coordinates everything |
| db.py | DB | PostgreSQL wrapper (46 functions, 926 lines) |
| migrate_json_to_db.py | DB | JSON → PostgreSQL migration (idempotent) |
| verify_db_parity.py | DB | JSON vs DB parity check (⚠️ BROKEN — needs psycopg2) |
| claim_linter.py | QA | Deterministic claim verification (316 lines, HARD BLOCK) |
| case_to_brief.py | Bridge | Pipeline → marketing (19K char enriched brief) |
| generate_marketing_videos.py | Integration | Veo 3 video generation |
| generate_marketing_images.py | Integration | DALL-E 3 image generation |
| send_marketing_emails.py | Integration | Resend email sending |
| stripe_sync.py | Integration | Stripe → PostgreSQL order sync |
| telegram_ops.py | Ops | Telegram operations bot (758 lines, 11 commands) |
| telegram_sender.py | Runtime | Telegram notifications |
| llm_caller.py | Runtime | Unified LLM calling |
| preflight_check.py | Runtime | Pre-run validation |
| state_lock_manager.py | Runtime | Prevents concurrent runs |
| artifact_validator.py | Runtime | JSON output validation |
| rollback_executor.py | Runtime | Rollback on failure |
| gate_handler.py | Runtime | Human approval gates |
| metrics_calculator.py | Growth | Deterministic metrics calculation |
| experiment_manager.py | Growth | A/B experiment lifecycle |
| pattern_promoter.py | Growth | Promote tentative → confirmed patterns |

---

# 9. ALL SKILLS — 15 TOTAL `[AUDIT]`

| # | Skill | Layer | What it produces |
|---|-------|-------|-----------------|
| 1 | market-analysis | Strategy | Competitor matrix, TAM/SAM/SOM |
| 2 | buyer-persona | Strategy | 5-10 segments |
| 3 | brand-strategy | Strategy | Paradigm shift + 25 angles |
| 4 | seo-architecture | Strategy | 60-100 keywords |
| 5 | channel-strategy | Strategy | Segment × trigger × channel matrix |
| 6 | script-generator | Weekly | 12 reel scripts in 6 lanes |
| 7 | ad-copy-generator | Weekly | 12 ads in 4 persona sets |
| 8 | email-generator | Weekly | 6 emails in 3 behavioral sequences |
| 9 | calendar-generator | Weekly | Publishing schedule |
| 10 | quality-reviewer | Weekly | 10-point checklist, HARD BLOCK |
| 11 | metrics-interpreter | Growth | Performance narrative |
| 12 | diagnosis-agent | Growth | Root cause + creative decay |
| 13 | learning-extractor | Growth | Winning/losing patterns |
| 14 | video-prompt-generator | Additional | Veo3 + DALL-E prompts from case brief |
| 15 | strategy-report-generator | Additional | HTML summary report |

---

# 10. POSTGRESQL DATABASE v2.1 `[AUDIT]`

**24 tables, 33 FK, 142 CHECK constraints** in schema `marketing`.

Core tables: projects, strategy_versions, product_catalog, strategy_outputs, buyer_segments, campaigns, campaign_products, campaign_target_segments, campaign_runs, assets, asset_metrics_base/video/email/search/landing, platform_metrics_weekly, seo_metrics, orders, conversion_events, growth_analyses, decisions, knowledge_base, experiments, gates.

**Key design decisions** `[EXT]`:
- `week_start_date DATE` instead of `week TEXT` (with `iso_week GENERATED`)
- CHECK constraints on ALL status/type fields
- Idempotency keys (GENERATED) on ingestion tables
- ON DELETE CASCADE on metric child tables
- `campaign_products` and `campaign_target_segments` as intermediary tables (no TEXT[] arrays)
- DB = source of truth, JSON = backup export (dual-write)

**⚠️ verify_db_parity.py BROKEN** — `ModuleNotFoundError: No module named 'psycopg2'` `[AUDIT]`

---

# 11. CASE BRIDGE (Pipeline → Marketing) `[EXT]`

**Script:** `case_to_brief.py`

Extracts enriched `weekly_case_brief.json` (19K chars) from pipeline case exports:
- Scenes for video (Veo 3 prompts)
- POI headshot prompts (DALL-E)
- Key clues for social media hooks
- Emotional arc for email sequences
- Hook angles for ads

**Anti-spoiler verified:** Never reveals the culprit. `[EXT]`

**Usage:** `python3 case_to_brief.py misterio-semanal 2026-WXX /path/to/case/`

---

# 12. TELEGRAM OPERATIONS BOT `[AUDIT]`

**File:** `telegram_ops.py` (758 lines) — EXISTS but NOT RUNNING `[AUDIT]`

**Problem:** Uses shared `TELEGRAM_BOT_TOKEN` (CEO bot), causing getUpdates conflict. Needs dedicated `TELEGRAM_OPS_TOKEN` via BotFather. `[AUDIT]`

**Security:** Only responds to `user_id 8024871665` (Alfredo).

## Phase 4A — Read-Only Commands (code done, not operational)

### System Reports

| Command | What it does | When to use | Example output |
|---------|-------------|-------------|----------------|
| `/help` | Lists all available commands | When you forget a command | Full command reference |
| `/status` | Full system overview: projects, strategy, campaigns, assets, KB, experiments + health (PostgreSQL, LiteLLM, Stripe) | Daily check or after restart | `Projects: 1 | Strategy: v2 (approved) | Assets: 15 | PostgreSQL: OK | LiteLLM: OK (24 models)` |
| `/strategy report misterio-semanal` | Strategy summary: competitors, 6 personas, positioning, keywords, angles | Before planning a week or reviewing foundations | `Personas: couples_date_night (P1)... | Keywords: 105 | Angles: 25 | Competitors: Hunt A Killer ($30/mo)...` |
| `/week brief misterio-semanal 2026-W17` | Run summary: case, assets, QA, claim linter, approval | After marketing run completes | `Case: The Miracle Withdrawal | Scripts: 12 | Ads: 12 | Emails: 6 | Linter: 0 violations | Status: APPROVED` |
| `/growth report misterio-semanal 2026-W17` | Diagnosis: root cause, patterns, experiments, recommendations | Saturday after weekly metrics | `CTR 2.1% (+0.3%) | Winning: emotional > rational 3:1 | Experiments: carousel vs single (running)` |

### Database Queries

| Command | What it does | When to use | Example output |
|---------|-------------|-------------|----------------|
| `/db segments misterio-semanal` | Buyer segments with priority | Planning which persona to target | `P1: true_crime_solo | P2: couples_date_night...` |
| `/db assets misterio-semanal W17` | Assets by type and status | Checking what's ready to publish | `reel_scripts: 12 (approved) | ad_copy: 12 | emails: 6 | videos: 0` |
| `/db campaigns misterio-semanal` | Active campaigns with metrics | Reviewing campaign performance | `launch-W14 | active | W14-W17 | 48 assets | 0 orders` |
| `/db experiments misterio-semanal` | A/B experiments with hypothesis | Deciding to close or extend | `EXP-001: carousel vs single | running | pending` |
| `/db kb misterio-semanal` | Knowledge base patterns | Reviewing what we've learned | `Confirmed: emotional hooks > rational | Tentative: Tue 9am best for IG` |
| `/db orders 30` | Stripe orders (last N days) with UTM | Connecting marketing to revenue | `Order #1: $12.00 | UTM: ig_reel_W15 | linda-oward` |

## Phase 4B — Operations Commands (designed, not coded)

| Command | What it does | When to use | Example output |
|---------|-------------|-------------|----------------|
| `/week start misterio-semanal 2026-W18 /path/case` | Full cycle: brief → marketing_runner → report | Monday morning | `Brief created | Scripts: 12 ✅ | Ads: 12 ✅ | Linter: 0 ✅ | QA: 2 warnings ⚠️ | Gate M1 pending` |
| `/week media misterio-semanal 2026-W18` | Generate videos (Veo 3) + images (DALL-E 3) | After reviewing content | `4 videos (Veo 3 Fast, $1.20 each) ✅ | 6 images ✅ | All media ready` |
| `/week approve misterio-semanal 2026-W18` | Approve, promote drafts/ → approved/ | After confirming everything | `W18 APPROVED | 30 assets promoted | Ready for publishing` |
| `/week emails misterio-semanal 2026-W18` | Send emails via Resend (--test flag) | Ready to send campaign | `Seq 1 (curiosity): 2 sent ✅ | Seq 2 (urgency): 2 ✅ | Seq 3 (social): 2 ✅` |
| `/sync stripe 30` | Pull payments → PostgreSQL | Weekly or after sale | `3 new orders | $36.00 | UTM: 2 IG, 1 email` |
| `/growth misterio-semanal 2026-W18` | Full Growth Intelligence (10 steps) | Saturday after metrics | `Diagnosis: CPA +15% — creative fatigue lane 3 | 2 new patterns | Gate G1 pending` |
| `/override lint misterio-semanal 2026-W18 "razón"` | Override claim linter (reason mandatory) | ONLY for false positives | `Override applied | Reason logged | ⚠️ Logged in gates table` |

## Weekly Flow from Telegram (complete cycle)

```
MONDAY:
  /week start misterio-semanal 2026-W18 ~/.openclaw/.../exports/cyber-ghost
  /week brief misterio-semanal 2026-W18       → review
  /week media misterio-semanal 2026-W18       → videos + images
  /week approve misterio-semanal 2026-W18     → approve all

TUESDAY-FRIDAY:
  Manual publish (until Meta API tokens obtained)
  /week emails misterio-semanal 2026-W18 --test your@email.com

SATURDAY:
  /sync stripe 7
  /growth misterio-semanal 2026-W18           → diagnosis + recommendations
```

---

# 13. INTEGRATIONS `[AUDIT]`

| Integration | Script | Status | Cost |
|-------------|--------|--------|------|
| Veo 3 (video) | `generate_marketing_videos.py` | Tested (1 video, 60s) | $0.15/sec Fast, $0.40/sec Standard |
| DALL-E 3 (images) | `generate_marketing_images.py` | Config exists, NOT TESTED | ~$0.08/HD |
| Resend (email) | `send_marketing_emails.py` | Tested (6/6 sent) | Free tier |
| Stripe (payments) | `stripe_sync.py` | Connected, 0 orders | — |
| Google Search Console | — | NOT started | — |
| Meta autopublishing | — | NOT started (FB Dev App Phase 3) | — |

---

# 14. MODEL ROUTING

| Component | Model | Cost | Reason |
|-----------|-------|------|--------|
| All marketing skills | LiteLLM default (chatgpt-gpt54 via Codex OAuth) | $0/token | Cost optimization |
| quality-reviewer | claude-sonnet46 via LiteLLM | per-token | GPT timed out with 75K+ context |
| video-prompt-generator | Default | $0 | — |
| metrics-calculator, experiment-manager, pattern-promoter | Script (no LLM) | $0 | Deterministic |

---

# 15. WEEKLY RUNS `[AUDIT]`

| Week | Status | Notes |
|------|--------|-------|
| W14 | ✅ Complete | First run (strategy v2) |
| W15 | ✅ Complete | Skills v1.1 rewrite |
| W16 | ✅ Complete | (Bible v1 said missing — exists) |
| W17 | ✅ Complete | QA hardened (0 claim violations) |

---

# 16. WEEKLY CYCLE (OPERATIONAL) `[EXT]`

```
SUNDAY     Prepare brief (case_to_brief.py if new case)
MONDAY     AI generates content → human reviews → approves
TUE-FRI    Human publishes (manual now, automated after Meta API tokens)
SATURDAY   Collect metrics → Growth Intelligence
```

~3-4 hours/week human time. `[EXT]`

---

# 17. KEY DESIGN DECISIONS

| # | Decision | Why | Date |
|---|----------|-----|------|
| 1 | Skip planner for implementation-ready docs | Planner took hours; Code implemented Advanced in 35 min | 2026-03-28 |
| 2 | Always Advanced, never MVP | With AI, Advanced takes same time as MVP | 2026-03-28 |
| 3 | No patches — fix root system | Strategy v1 mediocre → rewrote all 13 skills | 2026-03-28 |
| 4 | Quality reviewer on Sonnet | GPT timeout with 75K+ context | 2026-03-28 |
| 5 | Claim linter fail-closed | W17: 14 fabricated testimonials. No exceptions | 2026-03-28 |
| 6 | Veo 3 Fast for drafts, Standard for production | $1.20 vs $3.20 per 8s video | 2026-03-28 |
| 7 | DB = source of truth, JSON = backup | Dual-write during migration | 2026-03-28 |
| 8 | PostgreSQL 2-round GPT review | v1→GPT→v2→GPT→v2.1. Caught 7 structural issues | 2026-03-28 |
| 9 | 6 creative lanes (not random content) | Prevents content fatigue, structured variation | 2026-03-28 |
| 10 | Version pinning on strategy | Weekly run immutable once started | 2026-03-26 |
| 11 | Hard/soft strategy invalidation | Hard blocks marketing. Soft asks human via Telegram | 2026-03-26 |

---

# 18. CONNECTIONS TO OTHER WORKFLOWS

### What are the other workflows?

The Marketing System is one of 5 workflows in OpenClaw. Here's how they relate:

| Workflow | What it does | Relationship to Marketing |
|----------|-------------|--------------------------|
| **Declassified Pipeline** | Creates the mystery cases (the PRODUCT that marketing promotes) | Primary dependency — no cases = nothing to market |
| **Meta-Workflow Planner** | Validates ideas and designs workflow architectures | Used to DESIGN this marketing system (strategy-runtime-1 run) |
| **Finance Tracker** | Tracks expenses and cashflow | Monitors marketing COSTS via LiteLLM spend data |
| **Platform (Robotin)** | OpenClaw infrastructure, CEO agent, model routing, memory | Provides the runtime that executes all marketing scripts |

```
Pipeline ──case_to_brief.py──→ Marketing Weekly (enriched case brief)
Marketing ──content──→ Social Media (manual publish, future: auto via Meta API)
Marketing ──emails──→ Resend → customers
Marketing ──stripe_sync.py──→ PostgreSQL.marketing.orders
Growth ──optimization_actions──→ Marketing Weekly (injected as context)
Growth ──strategy_alert──→ Runtime → Strategy re-run
Strategy ──5 JSONs──→ Marketing Weekly (personas, brand, channels, SEO, competitors)
Knowledge Base ──patterns──→ Marketing Weekly (confirmed patterns used, tentative suggested)
Planner ──strategy-runtime-1──→ triggered Marketing System design
Web Store ──landing pages──→ Search Console (pending, pages exist but no content)
```

---

# 19. DATA FLOW — COMPLETE ARTIFACT MAP `[ARCH]`

### Strategy → Marketing

| Artifact | Producer | Consumer |
|----------|----------|----------|
| buyer_persona.json | Strategy | script/ad/email generators |
| brand_strategy.json | Strategy | All content generators |
| channel_strategy.json | Strategy | calendar_generator, orchestrator |
| seo_architecture.json | Strategy | Future blog_writer |
| market_analysis.json | Strategy | Reference only |

### Growth → Marketing

| Artifact | Producer | Consumer |
|----------|----------|----------|
| optimization_actions.json | diagnosis-agent | Injected into all content prompts |
| knowledge_base_marketing.json | learning-extractor | All content generators |

### Growth → Runtime → Strategy

| Artifact | Producer | Consumer |
|----------|----------|----------|
| strategy_alert.json | Growth evaluator | Runtime → soft/hard invalidation |

---

# 20. CURRENT STATE `[AUDIT]`

### Working ✅
- 15 skills deployed `[AUDIT]`
- 24 scripts present `[AUDIT]`
- Strategy v2 approved (6 personas, 105 keywords, 25 angles)
- 4 weekly runs completed (W14-W17)
- PostgreSQL 24 tables, dual-write active
- claim_linter integrated and enforcing (0 violations on W17)
- stripe_sync.py exists and connected
- Resend domain verified, 6/6 emails sent
- Veo 3 tested (1 video, 60s)
- case_to_brief.py working with anti-spoiler

### Broken/Issues ⚠️
- **verify_db_parity.py** fails: missing psycopg2 `[AUDIT]`
- **telegram_ops.py** not running: shared token conflict `[AUDIT]`
- **DALL-E 3** not tested via LiteLLM `[AUDIT]`
- **0 real sales** — Growth Intelligence has no actual metrics
- **No landing page content** — persona pages have placeholder text
- **No Meta API tokens** — can't auto-publish to FB/IG

### Technical lessons

| ID | Lesson |
|----|--------|
| TL-15 | LiteLLM model names ≠ provider names (claude-sonnet46 not claude-sonnet-4-6) |
| TL-17 | Sonnet truncates JSON >8K tokens — generate by blocks |
| TL-18 | PostgreSQL GENERATED columns can't use ::TEXT casts — IMMUTABLE functions |
| TL-19 | ON CONFLICT with GENERATED columns: use column_name not expression |
| TL-21 | Veo 3 uses -001 suffix not -preview |
| TL-35 | litellm.env: only API keys + UI creds. Extra vars crash LiteLLM |

---

# 21. PENDING ITEMS (prioritized)

| Priority | Item | Blocker |
|----------|------|---------|
| 🔴 | Install psycopg2 for verify_db_parity.py | `pip install psycopg2-binary` |
| 🔴 | Create dedicated Telegram ops bot token | BotFather → TELEGRAM_OPS_TOKEN |
| 🔴 | Complete FB Developer App (Phase 3) → API tokens | Meta app review |
| 🟡 | Test DALL-E 3 via LiteLLM | Proxy restart needed |
| 🟡 | Populate persona landing pages with real content | Marketing content + SEO keywords |
| 🟡 | First real E2E cycle: case → content → publish → sell → metrics → growth | All above |
| 🟡 | Implement Phase 4B (Telegram operations commands) | 4A operational first |
| 🟡 | Google Search Console integration | Landing pages with content first |
| 🟡 | TikTok + YouTube accounts and publishing | After Meta |
| 🟢 | weekly_cycle.py orchestrator (automates full Sunday-Saturday) | After all integrations stable |
| 🟢 | Multi-language (EN primary, ES secondary) | Structure now, implement later |

---

# 22. DIRECTORY STRUCTURE `[AUDIT]` `[ARCH]`

```
~/.openclaw/marketing-system/
├── skills/                              — 15 skills (SKILL.md each)
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
├── scripts/                             — 24 Python scripts
│   ├── strategy_runner.py
│   ├── marketing_runner.py
│   ├── growth_runner.py
│   ├── runtime_orchestrator.py
│   ├── db.py                            — 926 lines, 46 functions
│   ├── claim_linter.py                  — 316 lines, HARD BLOCK
│   ├── case_to_brief.py
│   ├── telegram_ops.py                  — 758 lines
│   ├── stripe_sync.py
│   ├── generate_marketing_videos.py
│   ├── generate_marketing_images.py
│   ├── send_marketing_emails.py
│   ├── migrate_json_to_db.py
│   ├── verify_db_parity.py
│   ├── [8 runtime scripts]
│   └── sql/
│       └── create_schema_v2.1.sql       — 477 lines
└── config/
    ├── email_config.json
    └── telegram_security.json

~/.openclaw/products/misterio-semanal/
├── product_brief.json                   — verified_facts + claims
├── product_manifest.json
├── knowledge_base_marketing.json
├── experiments_log.json
├── metrics_model.json
├── strategies/
│   ├── v2/                              — Active (approved)
│   └── _archived_v1_baseline/
├── weekly_runs/
│   ├── 2026-W14/ ✅
│   ├── 2026-W15/ ✅
│   ├── 2026-W16/ ✅
│   └── 2026-W17/ ✅ (QA hardened)
└── runtime/
    ├── runtime_state.json
    └── invalidation_log.json
```

---

**END OF WORKFLOW BIBLE — MARKETING SYSTEM**

*Consolidates: 1 extraction (2026-03-28/29), system_architecture_marketing.md, growth_intelligence_v2.1_frozen.md, DTC research, human_ai_operations_manual, QA hardening docs, PostgreSQL schema docs, telegram ops docs, and Project Bible v2. Verified against system audit 2026-03-29.*
