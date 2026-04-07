# tasks.md — SDD Planner Build Tasks (v2)

**Spec:** docs/specs/planner/spec.md (v4)
**Plan:** docs/specs/planner/plan.md (v2)
**Executor:** Claude Code
**Total tasks:** 40

---

## Phase 1: Core Infrastructure

### TASK-001: Create project structure and planner_state.json schema
- Objective: Set up directory structure and state schema with validation
- Inputs: spec.md §5 (State Persistence schema)
- Outputs: Directory tree, `schemas/planner_state_schema.json`, `state_manager.py` with create/load/save/validate
- Files touched: `planner/__init__.py`, `planner/schemas/planner_state_schema.json`, `planner/state_manager.py`, `planner/tests/test_state_manager.py`
- Done when: `create_run()` produces valid JSON, `load()` validates against schema, `save()` increments state_version, schema version field present for future migration
- depends_on: []
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Clarify schema fields with human
  - CRITICAL: Re-enter spec §5
- Estimated: 25 min

### TASK-002: Implement run locking + project-level admission control
- Objective: Prevent concurrent access to a run AND enforce one active run per project
- Inputs: spec.md §5 (State Persistence), spec.md §4 (V1 Concurrency Limit)
- Outputs: Lock/unlock with TTL, stale lock reclaim, project-level run guard
- Files touched: `planner/state_manager.py`, `planner/tests/test_locking.py`
- Done when: `acquire_lock()` works with TTL, expired locks reclaimable, second `acquire_lock()` raises `RunLockedException`, `check_project_admission(project_id)` rejects if active run exists for that project, lock renewal for long operations
- depends_on: [TASK-001]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Ask human about TTL duration
  - CRITICAL: Re-enter spec §5
- Estimated: 25 min

### TASK-003: Build filter_for_agent context compression
- Objective: Extract only required fields per agent role, deny-by-default, cross-references
- Inputs: spec.md §7.1 (full AGENT_FIELDS mapping)
- Outputs: `filter_for_agent.py` with mappings for ALL roles defined in spec
- Files touched: `planner/filter_for_agent.py`, `planner/tests/test_filter.py`
- Done when: Each role returns only mapped fields, undefined role raises ValueError, cross_references populated when doc references other docs (detected by scanning for doc names/section refs in content), deny-by-default enforced
- depends_on: [TASK-001]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Ask human about cross_references detection logic
  - CRITICAL: Re-enter spec §7.1
- Estimated: 25 min

### TASK-004: Build cost tracker with pricing config
- Objective: Log every API call with tokens/cost/duration, accumulate in state, alert at $30
- Inputs: spec.md §6 (Cost Tracking), current model pricing (March 2026)
- Outputs: `cost_tracker.py` with `log_call()`, `get_summary()`, pricing config
- Files touched: `planner/cost_tracker.py`, `planner/config/pricing.json`, `planner/tests/test_cost_tracker.py`
- Done when: `log_call(model, tokens_in, tokens_out, duration)` computes USD from pricing config, `get_summary()` returns by_model + by_phase + by_document + total, alert triggers at $30, pricing config updatable without code changes
- depends_on: [TASK-001]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Confirm current token prices with human
  - CRITICAL: Re-enter spec §6
- Estimated: 20 min

### TASK-005: Build model gateway with degraded mode
- Objective: Unified interface for ALL LLM calls — retries, error handling, degraded mode fallback
- Inputs: spec.md §4 (Model Selection + Degraded Mode), LiteLLM config
- Outputs: `model_gateway.py` with `call_model(role, prompt, context, provider, model)`, provider health check, degraded mode toggle
- Files touched: `planner/model_gateway.py`, `planner/tests/test_model_gateway.py`
- Done when: `call_model()` routes to correct provider via LiteLLM, catches Anthropic 5xx/timeout → offers degraded mode switch to human via Telegram, human approves → updates primary to GPT-5.4, logs all calls to cost_tracker, handles rate limit 429 with jittered backoff
- depends_on: [TASK-001, TASK-004]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test with real API endpoints with human
  - CRITICAL: Re-enter spec §4
- Estimated: 30 min

### TASK-006: Build document validator
- Objective: Reusable structural validation — no stubs, no TBDs, sections complete, [ASSUMPTION] exceptions
- Inputs: spec.md §2 (Quality criteria), spec.md §8 (Principle 9 — Assumed Defaults)
- Outputs: `validators/document_validator.py` with `validate(doc_content, template_type)`
- Files touched: `planner/validators/document_validator.py`, `planner/tests/test_document_validator.py`
- Done when: Catches "TBD", "placeholder", "TODO", "some_type", empty sections. Allows `[ASSUMPTION — ...]` as valid placeholder. Returns list of violations with line numbers. Returns PASS/FAIL with details.
- depends_on: [TASK-001]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Confirm forbidden patterns with human
  - CRITICAL: Re-enter spec §2
- Estimated: 20 min

### TASK-007: Build orchestrator phase dispatcher
- Objective: Engine that transitions between phases and dispatches to correct phase handler
- Inputs: spec.md §3 (Phases & Agents, phase order), TASK-001 through TASK-006
- Outputs: `orchestrator/dispatcher.py` with `dispatch_phase()`, phase ordering logic
- Files touched: `planner/orchestrator/__init__.py`, `planner/orchestrator/dispatcher.py`, `planner/tests/test_dispatcher.py`
- Done when: Dispatches to correct phase handler based on current_phase in state, transitions to next phase on completion, handles document loop (more docs → back to Phase 1), handles conditional phases (ideation skip), cost alert at $30 pauses dispatch
- depends_on: [TASK-001, TASK-002, TASK-003, TASK-004, TASK-005, TASK-006]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Clarify phase transition edge cases with human
  - CRITICAL: Re-enter spec §3
- Estimated: 25 min

### TASK-008: Build gate engine
- Objective: Evaluate gate conditions, trigger fail actions, enforce PII gate and other blocking gates
- Inputs: spec.md §3 (Gate Criteria table — G0 through G7)
- Outputs: `orchestrator/gates.py` with `evaluate_gate(gate_id, state)`, fail action dispatch
- Files touched: `planner/orchestrator/gates.py`, `planner/tests/test_gates.py`
- Done when: Each gate from spec (G0, G1, G1.5, G2, G2.5, G3, G4, G5, G6.5, G7) has evaluation logic, PII gate blocks Phase 1 until scan approved, fail actions match spec (re-ask, re-draft, resolve criticals, etc.), gate results logged in state
- depends_on: [TASK-007]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Clarify gate edge cases with human
  - CRITICAL: Re-enter spec §3 Gate Criteria
- Estimated: 25 min

### TASK-009: Build resume/checkpoint manager (async Telegram pattern)
- Objective: Save state at every gate, exit cleanly, resume from Telegram callback
- Inputs: spec.md §5 (State Persistence), Telegram async requirements
- Outputs: `orchestrator/checkpoint.py` with `save_checkpoint()`, `resume_from()`, async state-machine pattern
- Files touched: `planner/orchestrator/checkpoint.py`, `planner/tests/test_checkpoint.py`
- Done when: Orchestrator saves state + exits at every human gate (NOT blocking loop), Telegram callback triggers `resume_from(checkpoint)`, resume loads state, validates version consistency, continues from correct phase/doc, handles stale resume (wrong state_version → reject)
- depends_on: [TASK-007, TASK-008]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test async pattern with human on real Telegram
  - CRITICAL: Re-enter spec §5
- Estimated: 25 min

---

## Phase 2: Telegram Interface

### TASK-010: Wire Telegram command handler to orchestrator
- Objective: Route all commands to correct orchestrator methods
- Inputs: spec.md §7.4 (Telegram Commands), existing bot config
- Outputs: `telegram/handler.py` with routing for /plan, /plan-from-docs, /plan-resume, /plan-status, /plan-fix, /plan-af-approve
- Files touched: `planner/telegram/handler.py`, `planner/tests/test_telegram_handler.py`
- Done when: /plan creates run + dispatches, /plan-resume triggers checkpoint.resume_from(), /plan-status returns formatted state, /plan-fix triggers re-entry, /plan-af-approve triggers AF lifecycle approve flow (implementation extension — not in spec v4 commands but required by AF lifecycle), unknown commands return help
- depends_on: [TASK-009]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Check existing bot config with human
  - CRITICAL: Re-enter spec §7.4
- Estimated: 25 min

### TASK-011: Build Telegram message formatter
- Objective: Format all message templates from spec §8, handle 4096 limit
- Inputs: spec.md §8 (all Message Templates), spec.md §7.3 (Telegram Interface Rules)
- Outputs: `telegram/formatter.py` with template functions for each message type
- Files touched: `planner/telegram/formatter.py`, `planner/tests/test_formatter.py`
- Done when: Every message template from spec §8 has a function (intake_start, section_complete, ideation_results, pre_audit_summary, audit_summary, audit_conflict, document_approval, crossdoc_result, run_complete), messages >3500 chars trigger file mode, all messages include `[RUN-ID] [DOC] [PHASE]` prefix
- depends_on: [TASK-010]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test formatting with human
  - CRITICAL: Re-enter spec §8
- Estimated: 25 min

### TASK-012: Implement file attachments and inline keyboards
- Objective: Send .md files, receive approval via inline keyboard + free-text fallback
- Inputs: spec.md §7.3 (Telegram Interface Rules), Telegram Bot API
- Outputs: `telegram/files.py`, `telegram/keyboards.py`
- Files touched: `planner/telegram/files.py`, `planner/telegram/keyboards.py`, `planner/tests/test_telegram_files.py`
- Done when: Bot sends .md file + inline summary, inline keyboard renders ✅/🔄/❌, button press captured and routed to gate engine, free-text accepted for conflict resolution ("Something else: [text]"), approval matched to correct run/doc/phase via prefix
- depends_on: [TASK-010, TASK-011]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test with human on real Telegram
  - CRITICAL: Re-enter spec §7.3
- Estimated: 25 min

---

## Phase 3: Setup + Intake (Phases 0-1)

### TASK-013: Build Phase 0 setup (mode detection + context loading)
- Objective: Detect mode (new/existing/monolith), ask MODULE/WORKFLOW, load context docs
- Inputs: spec.md §3 (Phase 0), spec.md §2 (Input modes A/B)
- Outputs: `phases/phase_0_setup.py` with detect_mode(), load_context(), determine_doc_list()
- Files touched: `planner/phases/phase_0_setup.py`, `planner/tests/test_phase_0.py`
- Done when: New idea → new project mode, existing project dir → loads Foundation/Constitution/etc, /plan-from-docs → monolith mode, asks human "MODULE or WORKFLOW?", produces confirmed doc list, monolith mode routes to Phase 8 extraction before normal flow
- depends_on: [TASK-009, TASK-010]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Clarify mode detection heuristics with human
  - CRITICAL: Re-enter spec §3 Phase 0
- Estimated: 20 min

### TASK-014: Build PII/secret scanner (blocking gate)
- Objective: Scan uploaded docs for secrets, smart triage, MUST complete before any content goes to providers
- Inputs: spec.md §7.5 (PII/Secret Detection), spec.md §3 (Phase 0 — PII scan)
- Outputs: `pii_scanner.py` with scan(), classify_confidence(), format_results()
- Files touched: `planner/pii_scanner.py`, `planner/tests/test_pii_scanner.py`
- Done when: HIGH confidence matches (sk-xxx, ghp_xxx, AIza) block until human decision, LOW confidence (emails, variable names) shown as warning and allow continue, results formatted for Telegram, gate G0 enforces PII approval before Phase 1, handles new projects (no files → scan passes automatically), scans ALL user-provided content (attachments, pasted text, fetched docs)
- depends_on: [TASK-013]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review patterns with human
  - CRITICAL: Re-enter spec §7.5
- Estimated: 20 min

### TASK-015: Build template loader
- Objective: Load SDD templates from sdd-system repo, return section structure
- Inputs: sdd-system repo templates (MODULE_SPEC.md, WORKFLOW_SPEC.md, PROJECT_FOUNDATION.md, etc.)
- Outputs: `template_loader.py` with load_template(doc_type)
- Files touched: `planner/template_loader.py`, `planner/tests/test_template_loader.py`
- Done when: load_template("MODULE_SPEC") returns ordered section list, load_template("WORKFLOW_SPEC") returns workflow sections, handles all 7 SDD template types, unknown type raises error, initializes empty AUDIT_FINDINGS.md if missing
- depends_on: [TASK-001]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Confirm template paths with human
  - CRITICAL: Re-enter spec §2
- Estimated: 15 min

### TASK-016: Build Phase 1 intake interviewer
- Objective: Section-by-section Q&A with Opus, max 5 rounds, Assumed Default policy
- Inputs: spec.md §3 (Phase 1), spec.md §8 (Conversation Design), SDD template sections
- Outputs: `phases/phase_1_intake.py` with interview_section(), propose_assumed_default()
- Files touched: `planner/phases/phase_1_intake.py`, `planner/prompts/intake_interviewer.py`, `planner/tests/test_phase_1.py`
- Done when: Opus asks specific questions per template section, captures answers, after 5 rounds proposes Assumed Default with `[ASSUMPTION — validate during implementation]` flag, human confirms "idea captured properly", all sections have content (no empty sections), passes document_validator, uses model_gateway for all LLM calls, uses Decision Logs from previous docs (not raw history)
- depends_on: [TASK-005, TASK-006, TASK-011, TASK-014, TASK-015]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Refine prompt with human feedback
  - CRITICAL: Re-enter spec §3 Phase 1
- Estimated: 30 min

---

## Phase 4: Ideation + Draft + Pre-Audit (Phases 1.5-2.5)

### TASK-017: Build Phase 1.5 ideation (conditional, 2-model)
- Objective: Send concept to GPT + Gemini for feature ideas, Opus triages, human filters. Auto-skip for foundation docs.
- Inputs: spec.md §3 (Phase 1.5), intake answers from Phase 1
- Outputs: `phases/phase_1_5_ideation.py` with ideate(), triage_ideas(), should_skip()
- Files touched: `planner/phases/phase_1_5_ideation.py`, `planner/prompts/ideation_agent.py`, `planner/tests/test_phase_1_5.py`
- Done when: `should_skip(doc_type)` returns True for foundation docs (PROJECT_FOUNDATION, CONSTITUTION, DATA_MODEL, INTEGRATIONS, LESSONS_LEARNED), GPT and Gemini called via model_gateway, Opus triages and recommends, human accepts/rejects/skips via Telegram, produces no-op output on skip (empty accepted list)
- depends_on: [TASK-005, TASK-016]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Refine ideation prompts with human
  - CRITICAL: Re-enter spec §3 Phase 1.5
- Estimated: 25 min

### TASK-018: Build Phase 2 document drafter
- Objective: Populate SDD template with intake + ideation, validate completeness
- Inputs: spec.md §3 (Phase 2), intake answers, accepted ideation (or empty set if skipped)
- Outputs: `phases/phase_2_draft.py` with draft_document()
- Files touched: `planner/phases/phase_2_draft.py`, `planner/prompts/drafter.py`, `planner/tests/test_phase_2.py`
- Done when: Opus produces complete markdown following template, accepts empty ideation gracefully (no hard dependency on ideation), passes document_validator (no stubs except [ASSUMPTION]), all LLM calls via model_gateway
- depends_on: [TASK-006, TASK-015, TASK-017]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Refine drafter prompt if sections weak
  - CRITICAL: Re-enter spec §3 Phase 2
- Estimated: 25 min

### TASK-019: Build Phase 2.5 pre-audit checker
- Objective: Compare draft against AUDIT_FINDINGS.md, safe auto-fix, semantic flag
- Inputs: spec.md §3 (Phase 2.5), spec.md §11 (AF lifecycle — only ACTIVE entries used)
- Outputs: `phases/phase_2_5_preaudit.py` with check_against_af(), apply_safe_fixes(), flag_semantic()
- Files touched: `planner/phases/phase_2_5_preaudit.py`, `planner/tests/test_phase_2_5.py`
- Done when: Loads AUDIT_FINDINGS.md (or initializes empty if missing), only processes ACTIVE entries (ignores PROPOSED/DEPRECATED/ARCHIVED), safe_autofix entries applied silently, requires_review entries add `[AF-XXX SUGGESTION]: ...` markers, reports count of fixes + flags, AF markers preserved in doc for human review in Phase 5
- depends_on: [TASK-018]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review AF classification with human
  - CRITICAL: Re-enter spec §11
- Estimated: 20 min

---

## Phase 5: Audit + Lessons Check (Phases 3-4)

### TASK-020: Build Phase 3 audit executor (4 sequential calls)
- Objective: Send doc to GPT (tech + arch) and Gemini (tech + arch) with jittered backoff
- Inputs: spec.md §3 (Phase 3), spec.md §4 (Model Selection), filter_for_agent
- Outputs: `phases/phase_3_audit.py` with run_audit()
- Files touched: `planner/phases/phase_3_audit.py`, `planner/prompts/technical_auditor.py`, `planner/prompts/architecture_reviewer.py`, `planner/tests/test_phase_3.py`
- Done when: 4 calls execute sequentially via model_gateway (GPT-tech, GPT-arch, Gemini-tech, Gemini-arch), 5-10s jittered backoff between calls, each call uses filtered context from filter_for_agent (not full state), raw results saved to `planner_runs/{run_id}/audits/{doc}_{role}_{model}.json`, role prompts are meaningfully different (tech focuses on flaws/gaps/contradictions, arch focuses on missing architecture/ops)
- depends_on: [TASK-003, TASK-005, TASK-019]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test with real API calls, adjust prompts
  - CRITICAL: Re-enter spec §3 Phase 3
- Estimated: 30 min

### TASK-021: Build audit triage with conflict detection and severity rubric
- Objective: Opus filters 4 audit results, categorizes by severity, detects conflicts on CRITICALs
- Inputs: spec.md §3 (Phase 3 triage + conflict rule), spec.md §8 (audit summary templates)
- Outputs: `audit_triage.py` with triage(), detect_conflicts(), format_summary()
- Files touched: `planner/audit_triage.py`, `planner/prompts/audit_triager.py`, `planner/tests/test_triage.py`
- Done when: Categorizes findings as CRITICAL/IMPORTANT/MINOR/NOISE with defined rubric (CRITICAL: breaks architecture or violates spec, IMPORTANT: affects quality, MINOR: style/editorial, NOISE: not applicable to project scope), Conflict Flag fires when 2+ auditors disagree on CRITICAL (both raw arguments presented to human — triager cannot filter these), human receives formatted summary via Telegram, free-text option for "Something else" resolution
- depends_on: [TASK-020, TASK-011]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Refine severity rubric with human
  - CRITICAL: Re-enter spec §3 Phase 3
- Estimated: 25 min

### TASK-022: Build delta-audit + conditional second round
- Objective: After human fixes criticals, classify change and apply appropriate re-validation
- Inputs: spec.md §4 (delta-audit rule + conditional second round)
- Outputs: `delta_audit.py` with classify_change(), run_delta(), should_full_reaudit()
- Files touched: `planner/delta_audit.py`, `planner/tests/test_delta_audit.py`
- Done when: Change taxonomy implemented: WORDING_ONLY → Opus sanity check (1 call), LOCAL_LOGIC → 1 auditor on affected section, ENTITY_API_RULE_CHANGE → 1 auditor + flag for cross-doc impact, CROSS_DOC_EFFECT → 1 auditor + mandatory cross-doc re-validation. `should_full_reaudit()` returns True if doc changed >30% OR human requests OR doc is WORKFLOW_SPEC. Full re-audit = 4 calls via existing audit executor.
- depends_on: [TASK-020, TASK-021]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Clarify change classification threshold with human
  - CRITICAL: Re-enter spec §4
- Estimated: 25 min

### TASK-023: Build Phase 4 lessons check (post-correction)
- Objective: Compare CORRECTED document against LESSONS_LEARNED.md for violations
- Inputs: spec.md §3 (Phase 4), LESSONS_LEARNED.md
- Outputs: `phases/phase_4_lessons.py` with check_lessons()
- Files touched: `planner/phases/phase_4_lessons.py`, `planner/tests/test_phase_4.py`
- Done when: Runs against post-correction document (after delta-audit, NOT pre-fix version), Opus checks doc against relevant LL entries via model_gateway, reports violations + recommendations, 0 violations required to pass gate G4
- depends_on: [TASK-022]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review which LL entries apply with human
  - CRITICAL: Re-enter spec §3 Phase 4
- Estimated: 20 min

---

## Phase 6: Finalize + Records (Phases 5-6)

### TASK-024: Build Phase 5 finalize (inline summary + file)
- Objective: Apply fixes, send inline summary + .md file for approval, AF markers visible
- Inputs: spec.md §3 (Phase 5), spec.md §8 (document approval template)
- Outputs: `phases/phase_5_finalize.py` with apply_fixes(), present_for_approval()
- Files touched: `planner/phases/phase_5_finalize.py`, `planner/tests/test_phase_5.py`
- Done when: All audit/lessons fixes applied, AF markers visible in document, human receives INLINE SUMMARY (key changes, AF markers applied, cost) + .md file attachment, human can approve from summary or open file for full review, approval captured via inline keyboard, AF markers defined as review-only (removed from final approved version)
- depends_on: [TASK-023, TASK-012]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Adjust summary format with human
  - CRITICAL: Re-enter spec §3 Phase 5
- Estimated: 20 min

### TASK-025: Build history archive + Decision Log builder
- Objective: Archive raw chat history, generate structured Decision Log (summary + Hard Decisions)
- Inputs: spec.md §7.2 (Conversation History Management), spec.md §3 (Phase 6)
- Outputs: `decision_log.py` with build_log(), extract_hard_decisions()
- Files touched: `planner/decision_log.py`, `planner/tests/test_decision_log.py`
- Done when: Raw history → `history_archive/{doc_name}.json`, Decision Log generated with: 500-word executive summary + Hard Decisions (key:value pairs, e.g., `db_choice: PostgreSQL — self-hosted, no vendor lock`), Decision Log replaces raw history in active context, Hard Decisions searchable by key
- depends_on: [TASK-024]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review Decision Log quality with human
  - CRITICAL: Re-enter spec §7.2
- Estimated: 25 min

### TASK-026: Build Entity Map generator with heading paths
- Objective: Extract entities/IDs/APIs/rules/states from approved doc with source heading paths
- Inputs: spec.md §3 (Phase 6 — Entity Map), spec.md §3 (Phase 6.5 — on-demand loading)
- Outputs: `entity_map.py` with extract_entities(), entity map JSON schema
- Files touched: `planner/entity_map.py`, `planner/schemas/entity_map_schema.json`, `planner/tests/test_entity_map.py`
- Done when: Extracts entities, IDs, API endpoints, constitution rules, state machines/transitions from markdown doc. Each entry includes heading path (e.g., `## 3. Data Model > ### User Schema`) for on-demand section loading. Output is structured JSON. Entity Map validates against schema.
- depends_on: [TASK-024]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review entity extraction coverage with human
  - CRITICAL: Re-enter spec §3 Phase 6
- Estimated: 25 min

### TASK-027: Build history recall capability
- Objective: Search history_archive by keyword/entity, return specific historical section
- Inputs: spec.md §7.2 ("Recall" capability), history_archive files from TASK-025
- Outputs: `recall.py` with recall_history(doc_name, topic), search_all_archives(keyword)
- Files touched: `planner/recall.py`, `planner/tests/test_recall.py`
- Done when: `recall_history("CONSTITUTION", "cost ceiling")` returns the specific discussion fragment about cost decisions, searches by keyword across Hard Decisions first (fast), falls back to full-text search of archived history (slower), returns specific section not entire file, intake_interviewer can invoke recall when ambiguity detected
- depends_on: [TASK-025]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test recall quality with human
  - CRITICAL: Re-enter spec §7.2
- Estimated: 25 min

### TASK-028: Build AF lifecycle manager
- Objective: Full AUDIT_FINDINGS lifecycle: propose, dedupe, approve, deprecate, archive
- Inputs: spec.md §11 (AUDIT_FINDINGS lifecycle, entry classification, format)
- Outputs: `af_manager.py` with propose(), dedupe(), approve(), deprecate(), classify()
- Files touched: `planner/af_manager.py`, `planner/tests/test_af_manager.py`
- Done when: `propose(finding)` creates PROPOSED entry with confidence score, `dedupe(finding)` checks similarity to existing entries, `approve(af_id)` moves to ACTIVE (triggered by /plan-af-approve), `deprecate(af_id)` moves to DEPRECATED, classifies entries as safe_autofix or requires_review, entries not triggered in 3+ months auto-flagged for deprecation review (not auto-deprecated)
- depends_on: [TASK-001]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review dedup threshold with human
  - CRITICAL: Re-enter spec §11
- Estimated: 25 min

### TASK-029: Build Phase 6 record coordinator
- Objective: Coordinate all Phase 6 sub-modules: archive, Decision Log, Entity Map, AF proposals, LL updates, doc registry
- Inputs: spec.md §3 (Phase 6), TASK-025 through TASK-028
- Outputs: `phases/phase_6_records.py` with update_all_records()
- Files touched: `planner/phases/phase_6_records.py`, `planner/tests/test_phase_6.py`
- Done when: Calls in order: archive history → build Decision Log → generate Entity Map → propose AF entries → update LESSONS_LEARNED → update doc registry in PROJECT_FOUNDATION. All operations are idempotent (can re-run safely on resume). Partial failure marks run as DEGRADED.
- depends_on: [TASK-025, TASK-026, TASK-028]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test partial failure handling with human
  - CRITICAL: Re-enter spec §3 Phase 6
- Estimated: 20 min

---

## Phase 7: Cross-Doc + Plan/Tasks (Phases 6.5-7)

### TASK-030: Build Phase 6.5 cross-document validation via Entity Maps
- Objective: Validate Entity Maps for contradictions, load specific sections on conflict
- Inputs: spec.md §3 (Phase 6.5), Entity Maps from TASK-026
- Outputs: `phases/phase_6_5_crossdoc.py` with validate_entities(), load_conflict_sections()
- Files touched: `planner/phases/phase_6_5_crossdoc.py`, `planner/tests/test_phase_6_5.py`
- Done when: Compares entity names, IDs, API refs, constitution rules, state machines/transitions across all Entity Maps. On conflict: uses heading paths to load ONLY the specific sections (not full docs). Presents contradictions to human with both sides. 0 contradictions required to pass gate G6.5.
- depends_on: [TASK-026, TASK-029]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review entity comparison logic with human
  - CRITICAL: Re-enter spec §3 Phase 6.5
- Estimated: 25 min

### TASK-031: Build Phase 7 plan generator (with large project support)
- Objective: Convert approved spec into plan.md with phases, gates, dependencies
- Inputs: spec.md §3 (Phase 7), spec.md §9 (Large Plan Handling), approved spec
- Outputs: `phases/phase_7_plan.py` with generate_plan(), generate_master_plan()
- Files touched: `planner/phases/phase_7_plan.py`, `planner/prompts/plan_generator.py`, `planner/tests/test_phase_7_plan.py`
- Done when: Opus generates plan.md from spec via model_gateway, plan has phases with validation gates and dependency order, `generate_master_plan()` handles 10+ modules (1-line per module + dependency order), module-by-module loop with human confirmation between modules, pause/continue state saved for resume
- depends_on: [TASK-030]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review plan structure with human
  - CRITICAL: Re-enter spec §3 Phase 7
- Estimated: 25 min

### TASK-032: Build Phase 7 task generator with validator
- Objective: Convert plan into tasks.md, validate all 8 fields, cross-reference inputs
- Inputs: spec.md §3 (Phase 7), spec.md §10 (task schema example), plan.md
- Outputs: `phases/phase_7_tasks.py`, `task_validator.py`
- Files touched: `planner/phases/phase_7_tasks.py`, `planner/task_validator.py`, `planner/prompts/task_generator.py`, `planner/tests/test_phase_7_tasks.py`
- Done when: Opus generates tasks.md with all 8 fields per task (objective, inputs, outputs, files_touched, done_when, depends_on, if_blocked, estimated), `task_validator` checks: 0 missing fields, inputs reference existing doc sections (cross-reference validation), tasks are atomic (<30 min), no circular dependencies in depends_on, estimated total is reasonable
- depends_on: [TASK-031]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Refine task granularity with human
  - CRITICAL: Re-enter spec §10
- Estimated: 25 min

### TASK-033: Audit plan+tasks with full lifecycle
- Objective: Full 2-model audit on plan+tasks including correction loop and conflict handling
- Inputs: spec.md §4 (plan+tasks full audit), TASK-020/021/022 audit infrastructure
- Outputs: Reuse audit infrastructure on plan.md + tasks.md
- Files touched: `planner/phases/phase_7_plan.py` (add audit call), `planner/prompts/plan_auditor.py`, `planner/tests/test_phase_7_audit.py`
- Done when: plan.md and tasks.md each pass 4-call audit via existing phase_3_audit, specialized prompts for plan/task review (not generic doc review — focuses on executability, ambiguity, dependency correctness), triage + conflict handling applies, delta-audit after corrections, conditional second round if >30% change, human approves final plan+tasks
- depends_on: [TASK-020, TASK-021, TASK-022, TASK-032]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Adjust audit prompts for plan/task context
  - CRITICAL: Re-enter spec §4
- Estimated: 25 min

---

## Phase 8: Monolith Extraction

### TASK-034: Build monolith parser and block mapper
- Objective: Parse existing docs into content blocks, assign to SDD templates with confidence scoring and multi-tagging
- Inputs: spec.md §3 (Monolith extraction flow), spec.md §2 (Mode B)
- Outputs: `monolith/parser.py`, `monolith/mapper.py`, `monolith/confidence.py`
- Files touched: `planner/monolith/parser.py`, `planner/monolith/mapper.py`, `planner/monolith/confidence.py`, `planner/tests/test_monolith.py`
- Done when: Parser splits doc into content blocks (by heading, paragraph, or semantic break), mapper assigns each block to 1+ SDD templates (multi-tagging), confidence scorer rates each mapping (HIGH >80%, MEDIUM 50-80%, LOW <50%), non-HIGH blocks (<80%) flagged for review
- depends_on: [TASK-005, TASK-015]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test with real monolith doc with human
  - CRITICAL: Re-enter spec §3 Monolith
- Estimated: 30 min

### TASK-035: Build monolith review flow (auditor + human validation)
- Objective: Send low-confidence blocks to 1 auditor, present full mapping to human for approval
- Inputs: spec.md §3 (Monolith extraction steps 3-4), TASK-034 parser/mapper output
- Outputs: `monolith/reviewer.py` with audit_low_confidence(), present_mapping()
- Files touched: `planner/monolith/reviewer.py`, `planner/tests/test_monolith_review.py`
- Done when: Low-confidence blocks sent to 1 auditor model for validation, auditor confirms or re-assigns mapping, full mapping presented to human document-by-document, human approves/adjusts, approved mapping feeds into normal Phase 1-7 flow per document
- depends_on: [TASK-034, TASK-005, TASK-012]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test with real monolith with human
  - CRITICAL: Re-enter spec §3 Monolith
- Estimated: 25 min

---

## Phase 9: Re-Entry Protocol + E2E Test

### TASK-036: Build codebase reconciler
- Objective: Scan git diff + file tree, map existing files to original tasks, produce implementation status
- Inputs: spec.md §10 (Re-Entry Protocol Step 1)
- Outputs: `reentry/reconciler.py` with scan_codebase(), map_files_to_tasks(), produce_status()
- Files touched: `planner/reentry/reconciler.py`, `planner/tests/test_reconciler.py`
- Done when: Scans git diff and file tree, maps existing files to original task outputs (which task created/modified each file), produces structured status report: files_created, files_modified, tasks_completed, tasks_partial, tasks_not_started, current state vs original plan
- depends_on: [TASK-009]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test with real repo with human
  - CRITICAL: Re-enter spec §10
- Estimated: 30 min

### TASK-037: Build impact analyzer
- Objective: Compute impact radius from blocker using task dependency graph, mark downstream tasks
- Inputs: spec.md §10 (Re-Entry Step 2), tasks.md depends_on fields
- Outputs: `reentry/impact.py` with build_graph(), compute_impact(), mark_tasks()
- Files touched: `planner/reentry/impact.py`, `planner/tests/test_impact.py`
- Done when: Builds directed graph from depends_on fields, computes transitive closure from blocker task, marks downstream: VALID (no path from blocker), NEEDS_REVIEW (indirect dependency), VOID (direct dependency on changed output), produces structured impact report with dependency path and rationale per task
- depends_on: [TASK-036]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Review classification logic with human
  - CRITICAL: Re-enter spec §10
- Estimated: 25 min

### TASK-038: Build spec patcher + selective re-audit
- Objective: Update affected spec sections, re-audit only changed sections, run cross-doc validation
- Inputs: spec.md §10 (Re-Entry Steps 3-4), TASK-020 audit, TASK-030 cross-doc
- Outputs: `reentry/patcher.py` with patch_spec(), `reentry/reaudit.py` with selective_reaudit()
- Files touched: `planner/reentry/patcher.py`, `planner/reentry/reaudit.py`, `planner/tests/test_patcher.py`
- Done when: Loads blocker context + original spec, Opus patches affected section(s) only, re-audits ONLY changed sections (1 auditor, not full 4-call), runs cross-doc validation on affected Entity Maps post-patch, human approves spec changes before delta tasks
- depends_on: [TASK-020, TASK-022, TASK-030, TASK-037]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test patch quality with human
  - CRITICAL: Re-enter spec §10
- Estimated: 25 min

### TASK-039: Build delta task generator + /plan-fix coordinator
- Objective: Generate new tasks for VOID items, coordinate full /plan-fix flow
- Inputs: spec.md §10 (Re-Entry Step 4), TASK-036 through TASK-038
- Outputs: `reentry/delta_tasks.py`, `reentry/coordinator.py`
- Files touched: `planner/reentry/delta_tasks.py`, `planner/reentry/coordinator.py`, `planner/tests/test_plan_fix.py`
- Done when: Generates delta tasks only for VOID items (not full re-plan), NEEDS_REVIEW items flagged for human confirmation, delta tasks aware of existing code (from reconciler), `/plan-fix` command triggers full flow: reconcile → impact → patch → re-audit → cross-doc → delta tasks → human approval, all state saved for resume at every step
- depends_on: [TASK-036, TASK-037, TASK-038]
- if_blocked:
  - MINOR: Fix and document
  - MODERATE: Test full flow with mock blocker with human
  - CRITICAL: Re-enter spec §10
- Estimated: 25 min

### TASK-040: E2E test — multiple scenarios
- Objective: Run Planner end-to-end across multiple scenarios to validate full system
- Inputs: All previous tasks, test scenarios
- Outputs: Passing E2E tests, bug fixes discovered during testing
- Files touched: `planner/tests/test_e2e.py`, various files for bug fixes
- Done when: All scenarios pass without crashes or unhandled errors:
  1. **New project:** /plan "build a CLI todo app" → full run, all docs produced
  2. **Existing project module:** Add a new module to existing project with context docs
  3. **Monolith extraction:** Feed a test monolith doc → correct mapping and doc generation
  4. **PII hit:** Upload doc with fake API key → scanner catches it, blocks until approved
  5. **Audit conflict:** Plant contradictory content → Conflict Flag fires, human resolves
  6. **Degraded mode:** Simulate Anthropic down → offers GPT-5.4 switch
  Total cost tracked and reported for each scenario.
- depends_on: [TASK-033, TASK-035, TASK-039]
- if_blocked:
  - MINOR: Fix bugs found during E2E
  - MODERATE: Adjust flows based on E2E results
  - CRITICAL: Fundamental flow issue — revisit plan phases
- Estimated: 90 min

---

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| 1: Core Infrastructure | TASK-001 to TASK-009 | 9 |
| 2: Telegram Interface | TASK-010 to TASK-012 | 3 |
| 3: Setup + Intake | TASK-013 to TASK-016 | 4 |
| 4: Ideation + Draft + Pre-Audit | TASK-017 to TASK-019 | 3 |
| 5: Audit + Lessons | TASK-020 to TASK-023 | 4 |
| 6: Finalize + Records | TASK-024 to TASK-029 | 6 |
| 7: Cross-Doc + Plan/Tasks | TASK-030 to TASK-033 | 4 |
| 8: Monolith Extraction | TASK-034 to TASK-035 | 2 |
| 9: Re-Entry + E2E | TASK-036 to TASK-040 | 5 |
| **Total** | | **40 tasks** |

> Time estimates are reference only, not gates. Actual execution time will vary.
> Phase 1 is the critical path — everything else depends on it.
