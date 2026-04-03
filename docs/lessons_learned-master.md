# Lessons Learned — Master Consolidation
## All lessons across all OpenClaw workspaces
### Last updated: 2026-04-03
### Sources: shared/lessons_learned.md, workflow_engineering_lessons_learned, cases/config/lessons_learned.json, postmortem reports, workflow bibles, system_configuration.md

> This document consolidates ALL lessons learned from every workspace and document
> in the OpenClaw repository. It is the single reference for the complete set.
>
> **Canonical operational source** remains `shared/lessons_learned.md` — that file
> is what agents and validators actually read at runtime. This document is the
> exhaustive archive including context, evidence, and cross-references.

---

# PART 1: WORKFLOW ENGINEERING LESSONS (L-01 to L-33)

These lessons emerged from building the Declassified Cases Pipeline (V1-V9, ~$50+ spent)
and the Meta-Workflow Planner. They are the foundation for all agentic workflows.

## Category 1: Planning

### L-01: Plan the data flow BEFORE building agents
Every artifact must have an explicit consumer. If an output has no consumer, it should not exist. If a consumer needs an artifact that no one produces, it's a missing dependency. **FAIL the pipeline if orphan_outputs or missing_required_artifacts are non-empty.**
- *Evidence:* Experience Designer output was never consumed by the renderer.
- *Enforced by:* `validate_schema.py` (data_flow_map), `run_phase_b.sh` (hard fail on L-01)

### L-02: Define the contract (schema) between every producer-consumer pair
Define the schema/contract for every artifact BEFORE building the agent that produces it. Agents that guess the output structure produce garbage.
- *Evidence:* Narrative Architect produced `usage_map` arrays, but Art Director expected `for_doc` strings. Silent mismatch.
- *Enforced by:* `contract-designer` skill (B2 phase)

### L-03: Test one document end-to-end BEFORE running the full pipeline
After any infrastructure change, run ONE item end-to-end before batch processing. Never batch-run untested changes.
- *Evidence:* Applied 15 audit fixes, ran full case ($6+), renders still broken. Could have tested 1 doc for $0.10.
- *Enforced by:* `implementation-planner` SKILL.md requires `test_minimum` per phase

### L-04: Don't build V2 until V1 produces value
Start with the ugliest functional version. "Feo pero funcional" beats "bonito pero incompleto." Define an upgrade path from MVP to Standard without rewriting.
- *Enforced by:* `scope-framer` SKILL.md — never recommends Advanced as starting point

### L-05: Separate "does it work?" from "is it good?"
Infrastructure validation ("does it run?") and quality validation ("is it good?") are different phases. Don't mix them.
- *Evidence:* Hours spent mixing pipeline plumbing fixes with quality improvements.

## Category 2: Agent Architecture

### L-06: Test file I/O on day 1
Before building complex logic, verify that the spawn method can read inputs and write outputs to the correct paths.
- *Evidence:* `sessions_spawn` subagents could not write files. Discovered after 6 failed attempts.
- *Enforced by:* `implementation-planner` SKILL.md — Phase 1 always tests file I/O

### L-07: Direct API calls > Agent spawning for deterministic tasks
Use agent platforms for orchestration and routing. Use direct API calls for content generation where you need guaranteed file output.
- *Evidence:* Replaced all `sessions_spawn` with `spawn_agent.py` (direct API via curl). More reliable, exact cost tracking.

### L-08: One agent = one skill = one output type
Split large outputs into separate agent calls. One call = one file. If an artifact is too large for a single API call's MAX_TOKENS, split it.
- *Evidence:* Narrative Architect asked to produce both case-plan.json AND clue_catalog.json — clue_catalog truncated.
- *See also:* Block-based generation (2026-03-27 entries, `spawn_implementation_blocks.py`)

### L-09: Track orchestrator cost
The orchestrator itself consumes tokens. Account for orchestration overhead in cost estimates (~10% of per_run_total).
- *Evidence:* Tracked $2.42 in direct API costs but actual bill was $5+. Orchestrator was invisible.
- *Enforced by:* `cost_estimator.py` includes orchestrator_overhead field

### L-10: No stub outputs
Never accept placeholder/stub data in outputs. Validate that all fields have real, meaningful content.
- *Evidence:* clue_catalog.json had type_key='some_type', reveals='Reveals something about DOC-XX'.

## Category 3: Technical (WSL + API + Rendering)

### L-11: Canonical asset libraries
When multiple documents need the same asset (e.g., a person's photo), define one canonical version and reuse it. Don't regenerate.
- *Also:* Python `requests` fails in WSL for long API calls (>30s). See TL-01.
- *Evidence:* Art briefs requested separate mugshots for same POI across docs.

### L-12: Normalize identifiers
Use consistent IDs across all artifacts. Don't let different phases use different naming for the same entity.
- *Also:* Set subprocess timeout HIGHER than curl timeout. See TL-05.

### L-13: Cross-reference integrity
When changing a document's type or content, update ALL cross-references: dependencies, timelines, evidence chains.
- *Also:* MAX_TOKENS must match output complexity. See TL-07.

### L-14: Cost telemetry
Track token usage and cost per API call. Fail if a completed pipeline shows zero cost (missing telemetry).
- *Evidence:* manifest.json cost_tracking remained zero despite completed pipeline.

### L-15: Cross-reference updates on conversion
Any doc type conversion requires updating ALL references that depend on that document.
- *Evidence:* Converting evidence_mosaic → interrogation_transcript left stale cross-references.

### L-16: Trojan horse pacing
Early-envelope documents that hint at the solution must be ambiguous. The explicit reveal comes in later envelopes.
- *Evidence:* DoorDash receipt revealed key detail too early, collapsing mystery.

### L-17: Concrete specificity
Details in documents must be concrete and verifiable, not vague. Reject anything that could apply to any project.
- *Evidence:* Interview slips were "remembers the timestamp perfectly" instead of specific device states.

### L-18: Image coverage
Every document type that needs visual support must have image briefs planned. Don't skip "digital" document types.
- *Evidence:* Art Director only generated portraits + 1 building for 18 documents. Digital evidence docs got zero images.

### L-19: Output path conventions
Define where outputs go BEFORE building. Intermediate vs final output directories must be explicit.
- *Evidence:* Render output went to layout_specs/ but validators expected envelope_X/.

### L-20: Self-contained specs
If an artifact is the complete spec for a downstream agent, it must be self-contained — no implicit dependencies.
- *Evidence:* Visual instructions were split across experience_design.json and scene_descriptions.json; renderer only read _content.md.

## Category 4: Prompt Engineering

### L-21: Tell the model what NOT to do
Negative instructions prevent common failures. Include "NEVER" rules.
- *Evidence:* Claude generated dark backgrounds, truncated content, empty sections — all preventable.

### L-22: Script vs agent decision
If the logic is deterministic (no LLM needed), use a script, not an agent. Agents are for tasks requiring judgment.
- *Evidence:* 20-line Python script did image injection perfectly; LLM prompt engineering had failed for hours.
- *Enforced by:* `cost_estimator.py` is a script, not an agent

### L-23: Validate outputs structurally BEFORE quality-checking
Run cheap deterministic validators first. Only send to LLM QA after structural validation passes.
- *Evidence:* QA agent spent tokens analyzing structurally broken data.

## Category 5: Cost Management

### L-24: Set budget alarm BEFORE starting
Set a daily/session budget limit. Check actual API spend every 30 minutes during development.
- *Evidence:* Discovered $37+ spent only by checking billing dashboard hours later.

### L-25: Track orchestrator costs separately
Two cost buckets: (1) direct API calls — tracked in manifest.json, (2) orchestrator/routing — tracked via LiteLLM /spend endpoint.
- *Evidence:* manifest.json tracked $2.42, actual was $5+.

### L-26: Retry with diagnosis
Never retry with identical parameters. Always include failure diagnosis in the retry prompt. Max 2 retries before manual intervention.
- *Evidence:* Art Director spawned 3 times via sessions_spawn (all failed), each consuming tokens.

### L-27: Different models for different tasks
Use reasoning levels: expensive models for creative/complex tasks, cheap models for formatting/validation.

## Category 6: Workflow Management

### L-28: Human gates with justification
Every human gate must have a clear justification for why automation is too risky at that point. Human gates only for decisions that change outcomes.
- *Enforced by:* `implementation-planner` SKILL.md requires `human_gate.justification` per phase

### L-29: Save state after every phase
Every script must update manifest.json on completion AND on failure. Include: phase name, status, timestamp, cost.

### L-30: Backup before overwriting
Always backup before regenerating content. Compare before discarding.

### L-31: Use Claude Code for file edits, not chat
For any file modification, use Claude Code directly. Chat-based instructions are for planning, not execution.

### L-32: Multi-agent debates require structured output
For multi-model debates: define a JSON schema for "proposal", have each model fill it, then a judge model compares on defined criteria.
- *Enforced by:* `spawn_debate.py` uses JSON schema extraction for all rounds

### L-33: Compress upstream context for heavy agents
When an agent receives upstream artifacts as context, only include fields relevant to that agent's task. Implementation planner needs artifact names, purposes, and key fields — not full JSON schemas, examples, or format-level validation rules.
- *Date:* 2026-04-03
- *Fix:* `compress_contracts()` in `spawn_planner_agent.py` (67% reduction)
- *Fallback:* `block_mode` in `planner_config.json`
- *See:* `docs/FIX_LITELLM_TIMEOUT.md`

---

# PART 2: TECHNICAL LESSONS (TL-01 to TL-41)

Infrastructure, platform, and tooling lessons. Organized by domain.

## WSL & API (Pipeline-critical)

| ID | Lesson | Domain |
|----|--------|--------|
| TL-01 | Python `requests` FAILS in WSL for long API calls (>30s). ALWAYS use streaming `curl` via `subprocess`. All planner scripts use `litellm_stream.py`. | WSL/API |
| TL-02 | POI portraits: 100px JPEG q70 = $0.004/image (15x cheaper than 200px PNG) | Cost |
| TL-03 | cost_tracker.py: always use `(totals.get('field') or 0)` for None-safe access | Python |
| TL-04 | `sessions_spawn` cannot write files. Use spawn scripts with direct file I/O | Architecture |
| TL-05 | subprocess timeout MUST exceed curl --max-time. Buffer: `planner_config.json` → `subprocess_buffer` (50s) | WSL/API |
| TL-06 | Use wget not curl for DALL-E image downloads (special chars in URLs) | API |
| TL-07 | MAX_TOKENS: 32000 for visual docs, 16384 for text docs, 8192 standard, 5000 per block | API |
| TL-08 | NEVER dark backgrounds in rendered HTML — documents are printed on paper | Rendering |
| TL-09 | Always `mkdir -p` target directories before writing files | Filesystem |
| TL-10 | ALL file paths must be absolute. Include WORKSPACE_ROOT in every spawn preamble | Filesystem |

## Planner-specific

| ID | Lesson | Domain |
|----|--------|--------|
| TL-13 | SKILL.md MUST include exact JSON schema inline with types. Without them, models produce incompatible output | Planner |
| TL-14 | asyncio parallel debate fails in WSL ("future belongs to different loop"). Sequential fallback works | WSL |
| TL-15 | LiteLLM model names ≠ provider names (e.g., `claude-sonnet46` not `claude-sonnet-4-6`) | Config |
| TL-16 | M2.7 ignores complex AGENTS.md routing — not reliable for orchestration. Led to dedicated bot | Model |
| TL-17 | Sonnet truncates JSON above ~8K tokens. Generate by blocks | Architecture |

## Platform & Config

| ID | Lesson | Domain |
|----|--------|--------|
| TL-11 | OpenClaw doesn't resolve ${ENV_VARS} in apiKey — hardcode or skip master_key | Config |
| TL-12 | LiteLLM dashboard: UI_USERNAME/UI_PASSWORD in litellm.env (not master_key) | Config |
| TL-18 | PostgreSQL GENERATED columns can't use ::TEXT casts — use IMMUTABLE functions | PostgreSQL |
| TL-19 | ON CONFLICT with GENERATED columns: use column_name not expression | PostgreSQL |
| TL-20 | WSL auto-start: WSL.lnk + wsl.conf boot hook (NOT .bat keepalive) | Operations |
| TL-21 | Veo 3 model names use -001 suffix not -preview | API |
| TL-22 | `echo >>` for .env creates duplicates — edit with nano instead | Operations |
| TL-23 | isolatedSession + lightContext need gateway >=v2026.4 — not available yet | Config |
| TL-24 | CEO MEMORY.md must be CEO-specific — never copy from Declassified workspace | Architecture |
| TL-25 | sessions_spawn is invisible for cost tracking — phases 2-7 untracked | Pipeline |
| TL-26 | M2.7 A/B test not done — don't assume it's better without data | Process |
| TL-27 | `$(cat file.md)` in bash fails >~8KB — use file-based wrapper | WSL |
| TL-28 | Git identity: Alfredo Pretel, email 30666965+pr3t3l@users.noreply.github.com | Git |

## Finance Tracker

| ID | Lesson | Domain |
|----|--------|--------|
| TL-29 | Google Sheets OAuth: use run_local_server(port=18900, open_browser=False) in WSL | Finance |
| TL-30 | Google Sheets needs BOTH spreadsheets AND drive scopes | Finance |
| TL-31 | Lovable Publish after Code edits: git push doesn't deploy — Publish button required | Web |
| TL-32 | One Claude Code instance per repo — two on same repo causes git conflicts | Process |
| TL-33 | LiteLLM Prisma: duplicate model LiteLLM_DeletedTeamTable — warning, not blocking | LiteLLM |
| TL-34 | verify_db_parity.py needs psycopg2 installed in the venv that runs it | DB |
| TL-35 | litellm.env: only API keys + UI creds. Extra vars (TELEGRAM_*, GATEWAY_*) crash LiteLLM | Config |
| TL-36 | Google Sheets OAuth in WSL: port 18900, open_browser=False | Finance |
| TL-37 | Google Sheets needs spreadsheets + drive scopes | Finance |
| TL-38 | Receipt amounts: re.findall + max() beats re.search (first match) | Finance |
| TL-39 | Credit card payments are POSITIVE in Chase CSV — check payment keywords before sign split | Finance |
| TL-40 | Spanish payment keywords needed in classifier (SU PAGO, PAGO AUTOMATICO) | Finance i18n |
| TL-41 | AI batch classification ~$0.01/50 merchants — always cheaper than defaulting to Other | Finance cost |

> **Note:** TL-33/TL-34 in `workflow_bible_finance.md` refer to different lessons (Spanish keywords / AI classification cost) than TL-33/TL-34 in `openclaw_project_bible_v2.md` (LiteLLM Prisma / psycopg2). The project bible numbering is canonical.

---

# PART 3: PLANNER LESSONS (PL-07 to PL-09)

Lessons specific to the meta-workflow planner design process.

| ID | Lesson | Impact |
|----|--------|--------|
| PL-07 | Cross-critique produces better results than independent proposals | Basis for 3-round debate upgrade |
| PL-08 | Alternative paths diverge and the wrong one stays active | Avoid creating parallel paths that aren't integrated |
| PL-09 | Gate auto-approval hides quality issues | Basis for real human gates upgrade |

---

# PART 4: CASE-SPECIFIC LESSONS (LL-001 to LL-019)

From building Declassified murder mystery cases. Structured JSON source: `workspace/cases/config/lessons_learned.json`.

## el-asesinato-en-la-casa-inteligente (2026-03-12)

| ID | Category | Problem | Fix |
|----|----------|---------|-----|
| LL-001 | clue_catalog_quality | Stubs in clue_catalog: type_key='some_type', generic reveals | validate_narrative.py checks: type_key matches template_registry, reveals >30 chars |
| LL-002 | schema_mismatch | Envelope B failed 3x: HTML in Markdown, wrong schema | SKILL.md now includes exact JSON example per doc type |
| LL-003 | placeholder_passthrough | `{{CONTENT_FROM_MD_FILE}}` in rendered output | validate_placeholders.py added as mandatory scan |
| LL-004 | incomplete_image_coverage | Only 4 mugshot briefs, no evidence/scene images | Art Director SKILL.md requires briefs for ALL needs_image=true types |
| LL-005 | content_quality | Forensic reports 1-line methods, word count passed (counted labels) | validate_document.py counts narrative words only, per-type quality floors |
| LL-006 | hardcoded_template_data | evidence_mosaic.html had hardcoded pharmacy receipt from '03/18/1990' | All templates refactored to 100% data-driven via Handlebars |
| LL-007 | missing_tools | zip not installed, PDF tools missing, Google auth expired mid-pipeline | start_new_case.sh checks for required tools before starting |

## el-asesinato-en-la-casa-automatizada (2026-03-13)

| ID | Category | Problem | Fix |
|----|----------|---------|-----|
| LL-008 | inconsistent_poi_imagery | Separate mugshots for same POI across docs, inconsistent faces | One canonical portrait per POI, reused via library_path |
| LL-009 | victim_photo_style | Victim as police mugshot — wrong tone for victim profile | Victim image = normal portrait unless story requires booking photo |
| LL-010 | invalid_envelope_folder | Images written to non-existent envelope_P folder | Validation: envelope must be {A,B,C,R}, for_doc must be real doc_id |
| LL-011 | image_usage_planning | No specification of WHERE each image is used in docs | Art briefs must include usage_notes mapping image → doc_id + slot |
| LL-012 | consistency | Interview headers use placeholder POI identifiers | Normalize all interview subject lines to established POI IDs |
| LL-013 | consistency | Timeline source_docs mis-pointed after doc conversions | Verify cross-references exactly match evidence |
| LL-014 | telemetry_missing | manifest.json cost_tracking remained zero after completed pipeline | FAIL if totals are zero after completion (unless explicitly disabled) |

## the-last-livestream (2026-03-15/16)

| ID | Category | Problem | Fix |
|----|----------|---------|-----|
| LL-015 | cross_reference_integrity | Doc type conversion left stale cross-references | Any doc type conversion requires updating ALL references |
| LL-016 | trojan_horse_pacing | Trojan horse receipt revealed key detail too early | Early-envelope trojan docs must be ambiguous in reveals |
| LL-017 | interview_slip_specificity | Slips were vague ("remembers timestamp perfectly") | Slips must be concrete, verifiable, case-specific |
| LL-018 | incomplete_image_coverage | Art Director only generated portraits for 18 docs, digital docs got zero images | Updated template_registry: all visual doc types needs_image=true |
| LL-019 | layout-render | Render output went to layout_specs/, validators expected envelope_X/ | Output paths: envelope_X/<doc_id>.html and .pdf. layout_specs/ is intermediate only |

---

# PART 5: CASE POSTMORTEM LESSONS (LL-MTC-01 to LL-MTC-04)

From: medication-that-cures-too-well (2026-03-24)

| ID | Phase | Problem | Prevention |
|----|-------|---------|------------|
| LL-MTC-01 | Narrative Architect | Case-plan under-shot NORMAL tier minimums (14 docs < 15, 3 contradictions < 5) | Add orchestrator gate after case-plan: check docs/contradictions/evidence_chain against tier minimums |
| LL-MTC-02 | Narrative Architect | Envelope clue_catalog missing required fields, schema violations | Always include full clue_catalog skeleton + required field checklist in envelope prompts |
| LL-MTC-03 | Narrative Architect | Resolution envelope used `id` instead of `doc_id`, missing required fields | Extra strict prompts for Envelope R: ban `id`, require `doc_id`, require `player_purpose="resolution"` |
| LL-MTC-04 | Cost tracking | Many Gemini runs returned no token telemetry; manifest totals $0 | Record model, runtime, status; mark estimated_usd as null if unavailable |

---

# PART 6: OPERATIONAL LESSONS (Undated, from shared/lessons_learned.md)

These are date-stamped operational incidents, not numbered. They contain detailed evidence and rules.

## 2026-03-27 — Contract generation failures on large artifacts

**Escalation chain discovered:**
1. Monolithic generation fails → split by domain
2. Domain-split fails → identify failing block, retry only that block
3. Per-block still fails → one contract per artifact
4. Per-artifact too verbose → compact mode (schema + required + rules only)
5. JSON parse failure → auto-repair before declaring failure
6. Auto-retry up to 3 times before surfacing to human

**Rules:**
- Always save raw model output on failure before retrying
- Treat repeated invalid JSON on large outputs as architectural problem, not token-limit problem
- Apply auto-repair + retry patterns to implementation plans too
- Preferred fallback order: monolithic → domains → subdomains → one-per-artifact

## 2026-04-03 — LiteLLM server disconnect on large completions

**Diagnosis method:** Same payload with small max_tokens (500) works, large max_tokens (8192) disconnects. Proves issue is generation time, not input size.

**Root cause:** No explicit `request_timeout` in LiteLLM proxy config.

**Fix layers:**
1. Streaming via `litellm_stream.py` (SSE parsing) — all scripts
2. Context compression via `compress_contracts()` — 67% token reduction
3. `request_timeout: 600` in LiteLLM config — server-side
4. Block-based generation via `spawn_implementation_blocks.py` — configurable fallback

---

# PART 7: ANTI-PATTERNS

Collected from all sources. Never do these.

### Content Quality
- Never accept `some_type` as type_key — always use exact identifiers
- Never accept generic descriptions ("Reveals something about X") — require specifics
- Never count template/form labels toward content quality minimums
- Never include HTML tags in Markdown files
- Never hardcode case-specific data in templates — all content comes from JSON vars

### Operations
- Never retry with identical parameters — always include failure diagnosis
- Never use dark backgrounds in rendered HTML — documents are printed paper
- Never use Python `requests` in WSL for API calls — use curl subprocess
- Never use relative paths in agent prompts — always absolute
- Never use `sessions_spawn` to write files — use direct file I/O
- Never use `echo >>` for .env files — creates duplicates

### Architecture
- Normalize all identifiers consistently across phases
- Verify cross-references exactly match the evidence
- Never include a document type that doesn't serve the story
- Never split specs across multiple files — self-contained per consumer

---

# PART 8: MODEL NOTES

| Note | Source |
|------|--------|
| gemini31pro-thinking hits rate limits after ~15 spawns in 2 hours | Operational |
| gpt52-thinking is a reliable fallback for QA and narrative tasks | Operational |
| Sub-agents via sessions_spawn start with fresh context — token tracking per sub-agent is reliable | Architecture |
| Main session context compounds with each spawn — keep orchestration messages concise | Architecture |
| nano-banana-2-gemini needs exponential backoff (2s, 5s, 10s) for RESOURCE_EXHAUSTED errors | Operational |
| M2.7 not reliable for multi-step routing (ignores complex AGENTS.md) | TL-16 |

---

# PART 9: MASTER CHECKLIST

Before starting any agentic workflow, verify:

### Planning
- [ ] Data flow diagram complete (every file has a producer and consumer) — L-01
- [ ] JSON schemas defined for all inter-agent files — L-02
- [ ] Budget limit set with monitoring plan — L-24
- [ ] V1 scope defined (minimum viable output) — L-04
- [ ] Human gates identified and justified — L-28

### Architecture
- [ ] Subagent file I/O confirmed working (trivial test) — L-06
- [ ] Direct API vs agent spawn decided per task type — L-07
- [ ] Model selection per task complexity documented — L-27
- [ ] Cost tracking built into every script from day 1 — L-14
- [ ] All file paths use absolute paths — TL-10

### Development
- [ ] Single-item end-to-end test passes before batch — L-03
- [ ] Infrastructure fixes separated from quality improvements — L-05
- [ ] Deterministic tasks use scripts, not LLMs — L-22
- [ ] Structural validators run before LLM quality checks — L-23
- [ ] Backups created before content regeneration — L-30
- [ ] Large outputs split into blocks if >8K tokens — L-08, TL-17

### Operations
- [ ] Max 2 retries before diagnosis — L-26
- [ ] Both direct and orchestrator costs tracked — L-25
- [ ] Manifest.json updated on every phase completion/failure — L-29
- [ ] Context compressed for heavy downstream agents — L-33
- [ ] Streaming curl used for all API calls in WSL — TL-01

---

# SOURCE FILES

| File | Contents |
|------|----------|
| `shared/lessons_learned.md` | L-01 to L-33 + operational incidents (runtime reference) |
| `media/inbound/workflow_engineering_lessons_learned---*.md` | L-01 to L-32 with full context and checklists |
| `workspace/cases/config/lessons_learned.json` | LL-001 to LL-019 (case-specific, structured JSON) |
| `workspace-declassified/cases/config/lessons_learned.json` | LL-001 to LL-019 (synchronized copy) |
| `workspace-declassified/.../postmortem/lessons_learned_medication-that-cures-too-well.md` | LL-MTC-01 to LL-MTC-04 |
| `workspace-meta-planner/system_configuration.md` | TL-01, TL-04, TL-05, TL-09, TL-10 |
| `docs/openclaw_project_bible_v2.md` | TL-01 to TL-41 (full table) |
| `docs/workflow_bible_planner.md` | TL-13, TL-14, TL-15, TL-16, PL-07/08/09 |
| `docs/workflow_bible_pipeline.md` | TL-01 to TL-25 (pipeline subset) |
| `docs/workflow_bible_platform.md` | TL-11, TL-12, TL-15, TL-20 to TL-35 |
| `docs/workflow_bible_finance.md` | TL-33*, TL-34* (*different numbering, see note in Part 2) |
| `docs/workflow_bible_marketing.md` | TL-15, TL-17, TL-18, TL-19, TL-21, TL-35 |
| `workspace-meta-planner/docs/FIX_LITELLM_TIMEOUT.md` | Streaming + compression + block mode diagnosis |
