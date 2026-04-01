# WORKFLOW BIBLE — DECLASSIFIED CASES PIPELINE V9
## Documento técnico autoritativo
### Last verified: 2026-03-29 (audit v2.1)
### Sources: 6 chat extractions + Bible v2 §8 + system audit + benchmark analysis

> **Source tags:** `[AUDIT]` = machine-verified 2026-03-29. `[EXT-xx]` = from extraction file.
> `[BIBLE]` = from Project Bible v2. `[BENCH]` = from benchmark analysis chat.

---

# 1. PURPOSE & CONTEXT

Declassified Cases is a commercial mystery detective game. Players receive sealed evidence envelopes containing police files, forensic reports, witness interviews, social media screenshots, and other documents. They solve fictional crimes using the clues embedded across 15-25 documents.

The pipeline is the AI system that generates these cases from concept to packaged PDFs ready for sale at declassified.shop.

**Bot:** @APVDeclassified_bot (Telegram)
**Agent:** Declassified (id: declassified)
**Workspace:** `~/.openclaw/workspace-declassified/` `[AUDIT]`

---

# 2. EVOLUTION TIMELINE

| Date | Version | Key change | Source |
|------|---------|-----------|--------|
| 2026-03-05 | V5.1 | Initial redesign: skills, tiers, templates, "quality through structure" philosophy | [EXT-v5.1] |
| 2026-03-05 | V5.1 | Tier system (SHORT/NORMAL/PREMIUM) with envelope structure | [EXT-v5.1] |
| 2026-03-05 | V5.1 | 7 SKILL.md files, AGENTS.md, 5 validation scripts, 18 HTML templates | [EXT-v5.1] |
| ~2026-03-10 | V6 | Model abstraction layer (model_routing.json), smart retry (3 attempts), lessons-learned agent | [EXT-v6] |
| ~2026-03-10 | V6 | Kill expected_X.json — validators derive from clue_catalog.json | [EXT-v6] |
| ~2026-03-10 | V6 | Dynamic document selection (only 2 mandatory: Case Intro + POI Sheet) | [EXT-v6] |
| ~2026-03-10 | V6 | First test run (smart-home-murder): Narrative Architect schema compliance failure — 58 FAIL | [EXT-v6] |
| 2026-03-16 | V8 | Full architecture redesign with benchmark-driven quality framework | [EXT-v8v9] |
| 2026-03-16 | V8 | 6-pillar quality scoring (60 pts, 2x weight on UX) | [BENCH] |
| 2026-03-17 | V8 | Case 1 "The Last Livestream": 18 docs, 12 images, score 86% (51.3/60) | [EXT-v8v9] |
| 2026-03-17 | V8 | GitHub repo: pr3t3l/declassified-cases-pipeline (later unified into openclaw-config) | [EXT-v8v9] |
| 2026-03-18 | V8 | Multi-agent setup: @Robotin1620_Bot→CEO, @APVDeclassified_bot→Declassified | [EXT-v8v9] |
| 2026-03-18 | V8 | Case 2 "The Influencer Who Erased Herself": phases 1-7 complete, rendering quality poor | [EXT-v8v9] |
| 2026-03-19 | **V9** | **Zero templates revolution**: Claude generates ALL HTML directly. No Handlebars, no templates. | [EXT-v8v9] |
| 2026-03-19 | V9 | ai_render.py created: streaming curl → Anthropic API → HTML → Chromium → PDF | [EXT-v8v9] |
| 2026-03-19 | V9 | spawn_agent.py + spawn_narrative.py replace sessions_spawn | [EXT-v8v9] |
| 2026-03-19 | V9 | Case 3 "Cyber Ghost" initialized (NORMAL tier, 4 POIs, 20 docs) | [EXT-v8v9] |
| 2026-03-19 | V9 | sessions_spawn confirmed broken 6+ times: "(no output)", 0 tokens | [EXT-v8v9] |
| 2026-03-19 | V9 | V9 Pipeline Audit: 14 critical, 15 warnings, 7 notes | [EXT-v8v9] |
| 2026-03-19 | V9 | 15 audit fixes via Claude Code (commits 340ce8d → 722d78b) | [EXT-v8v9] |
| 2026-03-20 | V9 | spawn_images.py created (DALL-E 3 POI portraits) | [EXT-v8v9] |
| 2026-03-20 | V9 | [IMAGE:] tag system for Production Engine | [EXT-v8v9] |
| 2026-03-20 | V9 | MAX_TOKENS 8192 → 32000, subprocess timeout 310 → 650 | [EXT-v8v9] |
| 2026-03-20 | V9 | inject_poi_photos.py for post-render portrait injection | [EXT-v8v9] |
| 2026-03-22 | V9 | Anthropic API key rotated (old blocked at $0 balance) | [EXT-v8v9] |
| 2026-03-22 | V9 | 4 experimental workspaces archived | [EXT-v8v9] |
| 2026-03-30 | V8.3 audit | Congruency audit: 9 CRITICAL, 25 WARNING, 17 NOTE | [EXT-v83] |
| 2026-03-30 | V9 spawn fix | AGENTS.md rewrite: ALL sessions_spawn → exec python3 spawn scripts | [EXT-spawn] |
| 2026-03-30 | V9 spawn fix | Envelope-by-envelope clue_catalog generation (fix for 50KB output limit) | [EXT-spawn] |
| 2026-03-30 | V9 spawn fix | merge_clue_catalogs.py created | [EXT-spawn] |
| 2026-03-30 | V9 spawn fix | Commit a94cff9 pushed to openclaw-config | [EXT-spawn] |

---

# 3. ARCHITECTURE — THE 10 PHASES

```
[1. Init] → [2. Narrative Architect] → [3. Art Director] → [4. Experience Designer]
     ↓                                                              ↓
[5. Production Engine] → [6. Playthrough QA] → [7. Image Generator]
     ↓                                                              ↓
[8. AI Render] → [9. Package + Validate] → [10. Distribution]
```

| Phase | What it does | Spawn method | Model | Est. cost |
|-------|-------------|-------------|-------|-----------|
| 1 | Init: create case folder, manifest.json | `start_new_case.sh` | none | $0 |
| 2a | Narrative Architect: case-plan.json | `spawn_narrative.py --phase plan` | chatgpt-gpt54-thinking | ~$0.40 |
| 2b | Narrative Architect: clue_catalog.json (per envelope) | `spawn_narrative.py --phase catalog --envelope X` (×4) | chatgpt-gpt54-thinking | ~$0.60 |
| 3 | Art Director: art_briefs.json + scene_descriptions.json | `spawn_agent.py` | chatgpt-gpt54 | ~$0.25 |
| 4 | Experience Designer: experience_design.json | `spawn_agent.py` | chatgpt-gpt54-thinking | ~$0.25 |
| 5 | Production Engine: _content.md per document (per envelope) | `spawn_agent.py` (×4 envelopes) | chatgpt-gpt54-thinking | ~$1.50 |
| 6 | Playthrough QA: benchmark scoring | `spawn_agent.py` | chatgpt-gpt54-thinking | ~$1.00 |
| 7 | Image Generator: POI portraits | `spawn_images.py` | nano-banana-2-gemini / DALL-E 3 | ~$0.10 |
| 8 | AI Render: HTML → PDF per document | `ai_render.py` (direct Claude API) | claude-sonnet-4-6 | ~$2.00 |
| 9 | Package: merge PDFs per envelope, validate_final.py | scripts (no LLM) | none | $0 |
| 10 | Distribution: ZIP → Google Drive → Telegram | content-distribution skill | none | $0 |

**Total target per case: $6-8** `[BIBLE]`

**CRITICAL:** Phases 2-7 use Codex OAuth via LiteLLM ($0/token). Phase 8 uses direct Anthropic API (paid per token). Phase 8 is the primary cost driver. `[AUDIT]`

---

# 4. SPAWN ARCHITECTURE

## The sessions_spawn problem `[EXT-spawn]`

`sessions_spawn` (OpenClaw's built-in sub-agent spawner) is BROKEN for file writing:
- Sub-agents complete with "(no output)" and 0 tokens
- Confirmed broken 6+ times across multiple cases and phases
- Cannot be fixed — it's an upstream OpenClaw platform limitation

## The replacement: spawn scripts `[AUDIT]`

| Script | Purpose | How it works |
|--------|---------|-------------|
| `spawn_agent.py` | Generic content generation | Calls Claude API via streaming curl, script writes files (not sub-agent) |
| `spawn_narrative.py` | Narrative Architect (plan + catalog) | Specialized for --phase plan/catalog --envelope X |
| `spawn_images.py` | POI portrait generation | Calls DALL-E 3 / nano-banana-2-gemini |

## AGENTS.md spawn counts `[AUDIT]`

- sessions_spawn: 2 occurrences (both are "NEVER use" rules)
- spawn_agent: 11 occurrences
- spawn_narrative: 5 occurrences

## Cost tracking gap `[BIBLE]` `[EXT-spawn]`

**BUG:** When the orchestrator (Declassified bot) uses `sessions_spawn` internally for routing/decisions, those tokens are invisible to manifest.json. Only spawn_agent.py/spawn_narrative.py/ai_render.py log costs. This means the tracked cost per case ($4-6) is LOWER than actual cost (estimated ~$8-12 including orchestrator).

## Bootstrap truncation `[EXT-spawn]`

AGENTS.md (423 lines, ~19.7KB) gets truncated to ~18.1KB when injected into sub-agents (~13% removed). Rules at the end of AGENTS.md may not be seen by sub-agents. Future fix: reduce AGENTS.md size or increase `bootstrapMaxChars`.

---

# 5. SKILLS — 11 TOTAL `[AUDIT]`

| Skill | Purpose | Model tier |
|-------|---------|-----------|
| narrative-architect | Case plan + clue catalog | thinking |
| art-director | Art briefs (POI portraits) + scene descriptions | medium |
| experience-designer | Emotional beats + detective annotations | thinking |
| production-engine | _content.md per document with [IMAGE:] tags | thinking |
| quality-auditor | Playthrough QA + benchmark scoring | thinking |
| image-generator | POI portrait generation | medium |
| content-distribution | ZIP → Google Drive → Telegram | none |
| lessons-learned | Reviews failures, updates lessons_learned.json | medium |
| document-designer | Legacy (may be unused in V9) | medium |
| nano-banana-2-gemini | Image generation via Gemini | medium |
| tts-script-writer | Audio script for PREMIUM tier | thinking |

---

# 6. AI RENDER (Phase 8) `[AUDIT]`

The crown jewel of V9. Claude Sonnet generates every document as standalone HTML, then Chromium converts to PDF.

**File:** `~/.openclaw/workspace-declassified/cases/scripts/ai_render.py` (679 lines) `[AUDIT]`

### Parameters `[AUDIT]`

| Parameter | Value | Why |
|-----------|-------|-----|
| DEFAULT_MODEL | claude-sonnet-4-6 | Direct Anthropic API (NOT via LiteLLM) |
| MAX_TOKENS | 32000 | Increased from 8192 to prevent truncation of complex docs |
| curl --max-time | 600 seconds | 10 min per document render |
| subprocess timeout | 650 seconds | Must exceed curl timeout (TL-05) |

### Two-tier prompt system

| Tier | Doc types | System prompt |
|------|-----------|--------------|
| Tier 1 (text) | Transcripts, witness statements, court orders | Short prompt, minimal styling |
| Tier 2 (visual) | Social media, floor plans, POI sheets | Full design system prompt with visual instructions |

### [IMAGE:] tag system `[EXT-v8v9]`

Production Engine embeds visual placement tags in `_content.md`:

```
[IMAGE: POI portrait — embed visuals/canonical/poi_02_aldric_voss_mugshot.png, police booking style]
[IMAGE: Instagram post screenshot mockup — standard Instagram light UI]
[IMAGE: Floor plan diagram — Apartment 4C, 680 sq ft]
```

Rules:
- Every document gets at least 1 [IMAGE:] tag
- POI sheets get one per POI
- NEVER specify dark backgrounds
- ai_render.py reads these and creates visuals in HTML/CSS

### Post-render steps

- `inject_poi_photos.py` — replaces CSS avatar placeholders with real base64-encoded POI portraits
- `render_pdf_system_chromium.js` — Puppeteer: headless, Letter format, printBackground, margins 18mm/16mm
- `merge_pdfs.js` — combines per-envelope PDFs into final Envelope_X.pdf

**RULE:** Background MUST be white/light — NEVER dark backgrounds (TL-08)

---

# 7. DOCUMENT TYPE CATALOG

**File:** `~/.openclaw/workspace-declassified/cases/config/doc_type_catalog.json` `[AUDIT]`

Extensible catalog of document designs. Built-in types have detailed specs. Custom types use `design_hint` field. `[AUDIT]` confirmed types include: interrogation_transcript, official_memo, newspaper_front, newspaper_corporate, and many more (60 lines shown in audit).

Only 2 mandatory documents per case: `[EXT-v6]`
1. Case Introduction (any type that fits the story, always sequence 1 in Envelope A)
2. POI Sheet (type_id 1, always sequence 2)

All other documents chosen by Narrative Architect based on the story.

---

# 8. MODEL ROUTING

**File:** `~/.openclaw/workspace-declassified/cases/config/model_routing.json` `[AUDIT]`

| Reasoning level | Primary model | Cost | Use cases |
|----------------|--------------|------|-----------|
| thinking | chatgpt-gpt54-thinking | $0 (Codex OAuth) | Narrative, experience, production, QA playthrough |
| medium | chatgpt-gpt54 | $0 (Codex OAuth) | Art direction, image gen, QA depth |
| none | chatgpt-gpt54 | $0 (Codex OAuth) | Distribution, assembly |
| render | claude-sonnet-4-6 (direct API) | ~$0.03-0.10/doc | Document HTML generation |
| image | nano-banana-2-gemini, dall-e-3 fallback | $0.02/image, $0.08/HD | POI portraits |

**Agent reasoning map** from model_routing.json: `[AUDIT]`

narrative-architect→thinking, experience-designer→thinking, production-engine→thinking, quality-auditor→thinking (playthrough)/medium (depth), art-director→medium, image-generator→medium, content-distribution→none, tts-script-writer→thinking, lessons-learned→medium

---

# 9. CASES — 6 TOTAL `[AUDIT]`

| # | Slug | Name | Status | Tier | POIs | Docs | Score | Date |
|---|------|------|--------|------|------|------|-------|------|
| 1 | the-last-livestream | The Last Livestream | distributed ✅ | NORMAL | 5 | 18 | 86% (51.3/60) | 2026-03-17 |
| 2 | the-influencer-who-erased-herself | The Influencer Who Erased Herself | distributed ✅ | NORMAL | ? | 20 | needs V9 re-render | 2026-03-18 |
| 3a | medication-that-cures-too-well | The Medicine That Cures Too Well | stopped ⛔ | NORMAL | 5 | 21 | — | ~2026-03-22 |
| 3b | medication-that-cures-too-well-gpt | The Miracle Withdrawal (GPT re-run) | distributed ✅ | NORMAL | ? | 21 | — | ~2026-03-28 |
| 4 | cyber-ghost | Cyber Ghost | paused ⏸️ | NORMAL | 4 | 20 | — | 2026-03-19 |
| 5 | asalto-cronometrado | ? | initialized 🆕 | ? | ? | ? | — | ? |

### Case details from extractions:

**Cyber Ghost** `[EXT-v8v9]`: Setting: Harwick, USA. Victim: Jordan Mercer (31), freelance web dev. Culprit: Aldric Voss (POI-02), political consultant, staged fentanyl overdose. Remaining: inject POI photos + merge PDFs + distribute.

**Medication-that-cures-too-well** `[EXT-spawn]`: Setting: Cambridge, Massachusetts, Kendall Square biotech. Culprit: Calvin Rourke (POI-02), EVP Business Development. Method: nitrogen displacement via HVAC override. 5 POIs, 6 contradictions, digital_corporate style.

---

# 10. QUALITY FRAMEWORK — 6 PILLARS, 60 POINTS `[BENCH]`

| # | Pillar | Weight | Max pts |
|---|--------|--------|---------|
| 1 | **User Experience / Emotional Arc** | **2x** | **20** |
| 2 | Information Relevance | 1x | 10 |
| 3 | Clue Structure & Cognitive Load | 1x | 10 |
| 4 | Visual Support | 1x | 10 |
| 5 | Dynamic Clue Variety | 1x | 5 |
| 6 | Document as Experience | 1x | 5 |

### Benchmark scores `[BENCH]`

| Case | Score | % | Source |
|------|-------|---|--------|
| Linda Oward (gold standard) | 53/60 | 88% | Internal |
| Steve Jacobs (competition) | 50/60 | 83% | mododetective.store |
| Carmen García (competition) | 49/60 | 82% | mododetective.store |
| The Last Livestream (V8) | 51.3/60 | 86% | Pipeline output |
| Murder in Automated Home (V7) | 27/60 | 45% | Pipeline output — NOT production-ready |

### Tier constraints `[EXT-v6]` `[BENCH]`

| Dimension | SHORT | NORMAL | PREMIUM |
|-----------|-------|--------|---------|
| Suspects (minimum) | 4-5 | 6-8 | 8-12 |
| Documents | 10-15 | 15-22 | 22-30 |
| Pages | 15-25 | 25-38 | 38-55 |
| Envelopes | 2-3 | 3-4 | 4-5 |
| Social media mockups | 1-2 | 3-5 | 5-8 |
| Cross-envelope links | 2-3 | 4-6 | 6-10 |

### UX emotional arc (target experience) `[EXT-v6]`

The pipeline must produce cases that evoke: (a) "Aha!" intellectual satisfaction, (b) suspense/tension, (c) immersion/"flow", (d) conflicting empathy vs suspicion, (e) pleasure of not knowing, (f) smugness when deducing early, (g) catharsis/closure, (h) frustration from red herrings, (i) camaraderie in group solving.

---

# 11. CONFIG FILES `[AUDIT]`

| File | Purpose | Lines |
|------|---------|-------|
| design_system.json | Visual language for all documents | ? |
| doc_type_catalog.json | Document type specs (extensible) | 60+ |
| lessons_learned.json | Pipeline lessons for agents to read | 229 |
| model_routing.json | Per-phase model assignments + pricing | 53 |
| template_registry.json | Legacy template→variable mapping (replaced by doc_type_catalog) | 769 |
| tier_definitions.json | Tier constraints (SHORT/NORMAL/PREMIUM) | 188 |

---

# 12. SCRIPTS `[AUDIT]`

| Script | Purpose | Lines |
|--------|---------|-------|
| ai_render.py | Phase 8: Claude API → HTML → Chromium → PDF | 679 |
| spawn_agent.py | Generic agent spawner (replaces sessions_spawn) | ~460 |
| spawn_narrative.py | Narrative Architect spawner (plan + catalog) | ~450 |
| spawn_images.py | DALL-E 3 / nano-banana POI portraits | ? |
| start_new_case.sh | Phase 1: init case folder + manifest | 143 |
| cost_tracker.py | Logs API calls to manifest.json | ? |
| benchmark_scoring.py | Quality scoring (6 pillars) | 394 |
| normalize_output.py | Fixes Narrative Architect output schema issues | 499 |
| validate_narrative.py | Validates case-plan + clue_catalog | 538 |
| validate_art.py | Validates art_briefs (⚠️ has false-positive bug) | 180 |
| validate_content.py | Validates _content.md files | ? |
| validate_experience.py | Validates experience_design.json | 245 |
| validate_placeholders.py | Checks for unresolved template vars | 147 |
| validate_final.py | Final pre-distribution validation | 179 |
| inject_poi_photos.py | Post-render POI portrait injection | ? |
| merge_clue_catalogs.py | Merges per-envelope clue catalogs | ? |
| fix_case_plan_schema.py | Legacy schema fixer | ? |

---

# 13. KEY DESIGN DECISIONS

| # | Decision | Why | Date | Source |
|---|----------|-----|------|--------|
| 1 | Zero templates (V9) | Templates too rigid, Claude can generate any document type | 2026-03-19 | [EXT-v8v9] |
| 2 | Quality through structure | "La calidad se diseña en el CLUE_CATALOG, no se QA-ea después" | 2026-03-05 | [EXT-v5.1] |
| 3 | Images AFTER QA | DALL-E costs wasted if content rejected. Generate images only after content approved | 2026-03-05 | [EXT-v5.1] |
| 4 | Hybrid QA | 87% of QA is deterministic (scripts). LLM only for narrative judgment | 2026-03-05 | [EXT-v5.1] |
| 5 | Model abstraction | SKILL.md references reasoning levels, not model names. Single config routes | 2026-03-30 | [EXT-v6] |
| 6 | Smart retry (3 max) | Each retry MUST diagnose failure. Never blind retry. After 3 → stop + alert human | 2026-03-30 | [EXT-v6] |
| 7 | Envelope-by-envelope generation | 22-doc clue_catalog too large for single spawn (~50KB output crashes) | 2026-03-30 | [EXT-spawn] |
| 8 | Lessons-learned agent | Each case gets better by learning past failures. Reads structured failure JSON only | 2026-03-30 | [EXT-v6] |
| 9 | Dynamic document selection | Only 2 mandatory docs. All others chosen by Narrative Architect per story | 2026-03-30 | [EXT-v6] |
| 10 | POI portraits 100px JPEG q70 | $0.004/image vs $0.06 at 200px PNG (15x cheaper) | 2026-03-20 | [EXT-v8v9] |
| 11 | Resolution envelope (R) per POI | Each POI gets individual clearance/conviction document — better closure | 2026-03-30 | [BENCH] |
| 12 | Skills not agents | Pipeline "agents" are skills in CEO workspace, not separate OpenClaw agents | 2026-03-05 | [EXT-v5.1] |
| 13 | Two experiential styles | "físico/local" (handwritten, receipts) vs "digital/corporativo" (social media, apps) | 2026-03-30 | [BENCH] |

---

# 14. CONNECTIONS TO OTHER WORKFLOWS

```
Pipeline ──case_to_brief.py──→ Marketing System (weekly content)
Pipeline ──exports/slug/──→ Web Store (declassified.shop, Stripe)
Pipeline ──costs──→ LiteLLM SpendLogs → Finance tracking
Pipeline ──lessons_learned.json──→ Planner (Lessons Validator agent)
Brand Identity ──design_system.json──→ Pipeline (visual language)
Brand Identity ──SVGs──→ Web Store (product pages)
```

**case_to_brief.py:** Extracts enriched `weekly_case_brief.json` (19K chars) from pipeline output. Includes: scenes for video, POI headshot prompts, key clues for hooks, emotional arc. Anti-spoiler verified (never reveals culprit). `[BIBLE]`

---

# 15. CURRENT STATE `[AUDIT]`

### Working ✅
- 11 skills deployed and active
- spawn_agent.py, spawn_narrative.py, spawn_images.py operational
- ai_render.py with correct params (MAX_TOKENS=32000, claude-sonnet-4-6)
- model_routing.json updated to chatgpt-gpt54 ($0/token via Codex OAuth)
- 3 cases distributed, 6 total exports
- AGENTS.md rewritten to use spawn scripts (commit a94cff9)
- All validators present

### Broken/Issues ⚠️
- **validate_art.py** has false-positive bug `[AUDIT]`
- **Cost tracking** invisible for orchestrator tokens (sessions_spawn phases) `[BIBLE]`
- **Bootstrap truncation** AGENTS.md 19.7KB → 18.1KB injected (13% lost) `[EXT-spawn]`
- **cyber-ghost** paused at inject photos + merge + distribute `[AUDIT]`
- **Manifest.json** returns `case_name: unknown` and `cost: unknown` for all cases `[AUDIT]`

### Not tested `[AUDIT]`
- DALL-E 3 via LiteLLM (config exists but no test run)
- TTS (PREMIUM tier only — ElevenLabs configured but untested)

---

# 16. TECHNICAL LESSONS (Pipeline-specific)

| ID | Lesson | Source |
|----|--------|--------|
| TL-01 | Python requests DIES in WSL for long API calls — ALWAYS use streaming curl via subprocess | [EXT-v8v9] |
| TL-02 | POI portraits: 100px JPEG q70 = $0.004/image (15x cheaper than 200px PNG) | [EXT-v8v9] |
| TL-04 | sessions_spawn cannot write files — use spawn scripts | [EXT-spawn] |
| TL-05 | subprocess timeout must exceed curl --max-time (650 > 600) | [EXT-v8v9] |
| TL-06 | Use wget not curl for DALL-E image downloads | [EXT-v8v9] |
| TL-07 | MAX_TOKENS 32000 for visual docs, 16384 for text docs | [EXT-v8v9] |
| TL-08 | NEVER dark backgrounds in rendered HTML — documents are paper | [EXT-v8v9] |
| TL-09 | Always mkdir -p target directories before writing files | [EXT-v8v9] |
| TL-10 | All file paths in agent prompts must be absolute (WORKSPACE_ROOT) | [EXT-spawn] |
| TL-17 | Sonnet truncates JSON above ~8K tokens — generate by blocks | [BIBLE] |
| TL-25 | sessions_spawn is invisible for cost tracking — phases 2-7 untracked | [EXT-spawn] |
| PL-01 | SKILL.md needs concrete JSON skeleton examples, not just field lists | [EXT-v6] |
| PL-02 | "Read silently" rule — sub-agents must never echo config files to output | [EXT-v6] |
| PL-03 | Never patch failed output with scripts — delete and re-run with augmented prompt | [EXT-v6] |
| PL-04 | Validators must validate what the previous phase PRODUCES, not what a future phase will produce | [EXT-v83] |
| PL-05 | When changing format in a producer, grep the OLD format in ALL consumers | [EXT-v83] |
| PL-06 | Sub-agent model retains old schemas from training — embed concrete skeleton in every spawn | [EXT-v6] |

---

# 17. PENDING ITEMS (prioritized)

| Priority | Item | Blocker | Est. effort |
|----------|------|---------|-------------|
| 🔴 | Fix validate_art.py false-positive | None | 15 min |
| 🔴 | Complete cyber-ghost: inject photos + merge + distribute | API key/credits | 1 hour |
| 🔴 | Fix manifest.json to capture case_name and cost properly | Schema update | 30 min |
| 🟡 | Reduce AGENTS.md below bootstrap truncation threshold (~18KB) | Opt Phase 8 | 2 hours |
| 🟡 | Test DALL-E 3 via LiteLLM (restart proxy) | Proxy restart | 15 min |
| 🟡 | Re-render Case 2 (Influencer) with V9 pipeline | Time | 2 hours |
| 🟡 | Build cost reconciliation script (tracked vs actual) | Design | 2 hours |
| 🟡 | Test PREMIUM tier (TTS via ElevenLabs) | Case needed | 4 hours |
| 🟢 | New case: asalto-cronometrado (continue from initialized state) | Content | 4 hours |
| 🟢 | Add concrete JSON skeletons to all SKILL.md files (PL-01) | Time | 3 hours |
| 🟢 | Create Layout Planner SKILL.md (for future template-based path) | Design | 2 hours |

---

**END OF WORKFLOW BIBLE — DECLASSIFIED PIPELINE V9**

*This document is the single source of truth for the Declassified Cases pipeline. It consolidates 6 chat extractions spanning 2026-03-05 to 2026-03-30, verified against the system audit of 2026-03-29 and the Project Bible v2.*
