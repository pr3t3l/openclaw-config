# plan.md — SDD Planner Build Plan (v2)

**Project:** SDD Planner (Meta-Workflow)
**Spec:** docs/specs/planner/spec.md (v4)
**Executor:** Claude Code
**Start date:** 2026-04-07
**Estimated phases:** 9
**Total tasks:** 40
**Dependencies:** OpenClaw Gateway ✅, LiteLLM ✅, @Super_Workflow_Creator_bot ✅

---

## Phase 1: Core Infrastructure
**Goal:** Foundation modules that every other phase depends on.

Build the state manager, model gateway, context compressor, cost tracker,
document validator, and the orchestrator (split into 3 sub-components).

**Deliverables:**
- `state_manager.py` — planner_state.json CRUD, versioning, locking, project-level admission
- `model_gateway.py` — unified LLM interface, retries, degraded mode, provider health
- `filter_for_agent.py` — context compression, deny-by-default, cross-references
- `cost_tracker.py` — per-call logging with pricing config
- `document_validator.py` — structural validation, no stubs, [ASSUMPTION] exceptions
- `orchestrator/dispatcher.py` — phase transitions, agent dispatch
- `orchestrator/gates.py` — gate evaluation, fail actions, PII gate
- `orchestrator/checkpoint.py` — async save/resume, state-machine pattern for Telegram

**Validation gate:**
- [ ] State create/load/save works with version incrementing
- [ ] Lock prevents concurrent access + project-level single-run guard
- [ ] Model gateway calls Opus, falls back to GPT on Anthropic failure
- [ ] filter_for_agent raises error for undefined roles
- [ ] Document validator catches stubs, allows [ASSUMPTION]
- [ ] Orchestrator dispatches phases, stops at gates, resumes from checkpoint

---

## Phase 2: Telegram Interface
**Goal:** Human can interact with the Planner via Telegram commands.

Wire @Super_Workflow_Creator_bot to the orchestrator. Handle all commands
including /plan-af-approve. Respect 4096 limit. Inline keyboards for approvals.

**Deliverables:**
- `telegram/handler.py` — command routing (/plan, /plan-from-docs, /plan-resume, /plan-status, /plan-fix, /plan-af-approve)
- `telegram/formatter.py` — message templates, 4096 char handling, [RUN-ID] [DOC] [PHASE] prefix
- `telegram/files.py` — send/receive .md file attachments
- `telegram/keyboards.py` — inline buttons for approvals + free-text fallback

**Validation gate:**
- [ ] All 6 commands work and route to correct orchestrator methods
- [ ] Documents >3500 chars sent as .md file + inline summary
- [ ] Inline keyboards capture approval, gate callback triggers resume
- [ ] Free-text responses accepted for conflict resolution ("Something else")

---

## Phase 3: Setup + Intake (Phases 0-1)
**Goal:** Planner can receive an idea, detect mode, scan for secrets,
load templates, and conduct section-by-section Q&A.

**Important:** PII scan is a blocking gate — no content goes to providers
until human approves scan results.

**Deliverables:**
- `phases/phase_0_setup.py` — mode detection (new/existing/monolith), doc list, context loading
- `pii_scanner.py` — regex patterns, smart triage (high/low confidence), blocking gate
- `template_loader.py` — load SDD templates, return section structure
- `phases/phase_1_intake.py` — section-by-section Q&A, 5-round limit, Assumed Defaults

**Validation gate:**
- [ ] Mode detection handles new project, existing project, and monolith input
- [ ] PII scan blocks Phase 1 until human approves/redacts
- [ ] Template loader returns correct sections for MODULE_SPEC and WORKFLOW_SPEC
- [ ] Intake captures answers per section, proposes Assumed Default after 5 rounds

---

## Phase 4: Ideation + Draft + Pre-Audit (Phases 1.5-2.5)
**Goal:** Enrich with multi-model suggestions, draft the document,
and pre-check against AUDIT_FINDINGS.md.

Ideation is conditional: runs for spec docs, skipped for foundation docs
unless human overrides.

**Deliverables:**
- `phases/phase_1_5_ideation.py` — send to GPT + Gemini, triage, conditional skip logic
- `phases/phase_2_draft.py` — populate SDD template, structural validation
- `phases/phase_2_5_preaudit.py` — compare vs AUDIT_FINDINGS, safe auto-fix, semantic flag

**Validation gate:**
- [ ] Ideation auto-skips for foundation docs, runs for spec docs
- [ ] Human can manually skip ideation for any doc
- [ ] Drafter produces complete doc, passes document_validator
- [ ] Pre-audit auto-fixes safe AF patterns, highlights semantic with [AF-XXX SUGGESTION]

---

## Phase 5: Audit + Lessons Check (Phases 3-4)
**Goal:** Multi-model adversarial audit with conflict handling,
delta-audit for corrections, conditional second round, lessons validation.

**Deliverables:**
- `phases/phase_3_audit.py` — sequential 4-call queue with jittered backoff
- `audit_triage.py` — categorize findings, Conflict Flag, severity rubric
- `delta_audit.py` — classify change (minor/architecture), delta or conditional full re-audit
- `phases/phase_4_lessons.py` — check doc against LESSONS_LEARNED.md (post-correction)

**Validation gate:**
- [ ] 4 audit calls with 5-10s backoff, raw results saved
- [ ] Conflict Flag fires on CRITICAL disagreement, both arguments to human
- [ ] Minor fix → Opus check; architecture change → 1 auditor; >30% change → full 4-call re-audit
- [ ] Lessons check runs against corrected document (not pre-fix version)

---

## Phase 6: Finalize + Records (Phases 5-6)
**Goal:** Apply fixes, present to human, archive history, build Decision Logs
and Entity Maps, manage AF lifecycle, enable history recall.

**Deliverables:**
- `phases/phase_5_finalize.py` — apply fixes, inline summary + .md file, AF markers visible
- `phases/phase_6_records.py` — coordinate all record-keeping sub-modules
- `decision_log.py` — summary + Hard Decisions (key:value) builder
- `entity_map.py` — extract entities/IDs/APIs/rules/states with heading paths
- `recall.py` — search history_archive by keyword/entity, return specific section
- `af_manager.py` — propose/dedupe/approve/deprecate AF entries, lifecycle states

**Validation gate:**
- [ ] Human receives inline summary + .md attachment, approves via keyboard
- [ ] Decision Log has summary + Hard Decisions, searchable by key
- [ ] Entity Map includes heading paths for on-demand section loading
- [ ] Recall finds specific historical section by keyword
- [ ] AF entries follow full lifecycle (PROPOSED, human approves to ACTIVE)
- [ ] /plan-af-approve command works via Telegram

---

## Phase 7: Cross-Doc Validation + Plan Generation (Phases 6.5-7)
**Goal:** Validate consistency across all docs via Entity Maps,
then generate plan + tasks with full audit lifecycle.

**Deliverables:**
- `phases/phase_6_5_crossdoc.py` — validate Entity Maps, load sections on conflict
- `phases/phase_7_plan.py` — spec → plan.md, module-by-module for large projects
- `phases/phase_7_tasks.py` — plan → tasks.md with all 8 required fields
- `task_validator.py` — verify fields present, cross-reference validation, atomicity check
- Full 2-model audit on plan+tasks with correction loop + conflict handling

**Validation gate:**
- [ ] Cross-doc catches planted contradiction between 2 Entity Maps
- [ ] On conflict, loads only specific sections (not full docs)
- [ ] Plan has phases with gates, handles large projects module-by-module
- [ ] Every task has all 8 fields, validator passes
- [ ] Task input references verified against actual doc sections
- [ ] Plan+tasks pass full audit lifecycle (4 calls, triage, corrections, delta-audit)

---

## Phase 8: Monolith Extraction
**Goal:** Build the complete Mode B path for extracting SDD docs from
existing documentation/monoliths.

**Deliverables:**
- `monolith/parser.py` — identify content blocks in uploaded docs
- `monolith/mapper.py` — assign blocks to SDD templates, multi-tagging
- `monolith/confidence.py` — score each mapping (high/medium/low)
- `monolith/reviewer.py` — send low-confidence blocks to 1 auditor, present mapping to human

**Validation gate:**
- [ ] Parser identifies distinct content blocks from a test monolith
- [ ] Mapper assigns blocks to correct templates with multi-tagging
- [ ] Confidence scoring flags ambiguous blocks (<80%)
- [ ] Low-confidence blocks audited by 1 model before human review
- [ ] Human approves final mapping before templates are populated

---

## Phase 9: Re-Entry Protocol + E2E Test
**Goal:** Build /plan-fix flow and validate everything end-to-end
across multiple scenarios.

**Deliverables:**
- `reentry/reconciler.py` — scan git diff + file tree, map files to original tasks
- `reentry/impact.py` — compute impact radius from task dependency graph
- `reentry/patcher.py` — update affected spec sections
- `reentry/reaudit.py` — selective re-audit + cross-doc validation post-patch
- `reentry/delta_tasks.py` — generate delta tasks for VOID items
- `reentry/coordinator.py` — orchestrate full /plan-fix flow end-to-end
- E2E tests: new project, existing module, monolith extraction, PII hit, audit conflict, re-entry

**Validation gate:**
- [ ] /plan-fix reconciles codebase, shows impact, patches spec
- [ ] Cross-doc validation runs after spec patch, before delta tasks
- [ ] Impact analysis marks tasks as VALID/NEEDS_REVIEW/VOID with evidence
- [ ] Delta tasks generated only for VOID items, NEEDS_REVIEW flagged
- [ ] E2E: new project completes full run
- [ ] E2E: at least 3 additional scenarios pass without crashes

---

## Phase Dependencies

```
Phase 1 (Core Infrastructure) 
  ├──→ Phase 2 (Telegram)
  ├──→ Phase 3 (Setup + Intake)     ← can parallel with Phase 2
  │      └──→ Phase 4 (Ideation + Draft + Pre-Audit)
  │             └──→ Phase 5 (Audit + Lessons)
  │                    └──→ Phase 6 (Finalize + Records)
  │                           └──→ Phase 7 (Cross-Doc + Plan/Tasks)
  │                                  └──→ Phase 9 (Re-Entry + E2E)
  └──→ Phase 8 (Monolith) ← can start after Phase 3, parallel with 4-7
```

**Parallelizable within Phase 1:** TASK-001 through TASK-006 can mostly run in parallel
after TASK-001 completes. TASK-007/008/009 depend on 001-006.
