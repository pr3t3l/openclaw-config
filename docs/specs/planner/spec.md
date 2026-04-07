# WORKFLOW_SPEC.md — SDD Planner
<!--
SCOPE: Complete specification for the SDD Planner workflow.
       The system that takes ideas/docs and produces SDD documentation.
NOT HERE: Platform infrastructure → PROJECT_FOUNDATION.md, CONSTITUTION.md
NOT HERE: Database schemas → DATA_MODEL.md
NOT HERE: API details → INTEGRATIONS.md
VERSION: v4 — post-audit round 2 (hardening pass)
-->

**Workflow:** SDD Planner (Meta-Workflow)
**Date:** 2026-04-06
**Version:** v4 (post multi-model audit, 2 rounds)
**Status:** ⬜ Draft → 🔍 Review → ✅ Approved → 🔨 Building → ✅ Complete
**Depends on:** Platform (OpenClaw Gateway, LiteLLM, Telegram bot)
**Execution engine:** OpenClaw (V1), extrapolable to n8n
**Trigger:** Telegram command to Planner bot (@Super_Workflow_Creator_bot)

---

## 1. Purpose & Scope

### What problem does this workflow solve?

Building apps and workflows currently requires 10+ iterations because developers
(human + AI) skip planning, write incomplete specs, miss edge cases, and discover
architectural problems during implementation. The Planner eliminates this by
producing validated, complete SDD documentation BEFORE any code is written.

### What does it produce?

A complete set of SDD documents, ready for Claude Code (or any executor) to
implement without guessing:

**For a new project:**
- PROJECT_FOUNDATION.md
- CONSTITUTION.md (includes CLAUDE.md section)
- DATA_MODEL.md
- INTEGRATIONS.md
- LESSONS_LEARNED.md (initialized with relevant entries)
- MODULE_SPEC.md or WORKFLOW_SPEC.md (per module/workflow)
- plan.md + tasks.md (per module/workflow)

**For a new module/workflow in an existing project:**
- MODULE_SPEC.md or WORKFLOW_SPEC.md
- plan.md + tasks.md

### Success Criteria
- [ ] Output documents pass structural validation (all template sections filled)
- [ ] Output documents pass multi-model audit (2 models, 4 API calls, find no critical gaps)
- [ ] Output documents pass AUDIT_FINDINGS pre-check (known safe patterns pre-corrected)
- [ ] Output documents pass LESSONS_LEARNED check (no known lessons violated)
- [ ] Output documents pass cross-document consistency check (no contradictions)
- [ ] plan.md + tasks.md pass full 2-model audit (4 calls) for spec↔plan alignment
- [ ] Total cost tracked per phase, per model, per document (no hard estimate gates)
- [ ] Hard limit per run: $50 (alert at $30)
- [ ] Human rates the output as "ready to build" without rewriting sections

### In Scope
- [ ] New project: all SDD docs from scratch via conversational intake
- [ ] Existing project: module/workflow spec + plan + tasks
- [ ] Monolith extraction: parse existing docs → distribute to SDD templates with confidence scoring
- [ ] Multi-model ideation: 2 models suggest features/improvements before drafting
- [ ] Multi-model adversarial audit of every document including plan+tasks (4 API calls per doc)
- [ ] Persistent AUDIT_FINDINGS.md with lifecycle states to eliminate repeat findings
- [ ] Lessons learned validation against existing LL database
- [ ] Cross-document consistency validation before plan generation
- [ ] Large plan handling (module-by-module interactive with human)
- [ ] Code re-entry protocol with codebase reconciliation and task dependency tracking
- [ ] PII/secret detection and human-reviewed redaction before sending docs to external model providers

### Out of Scope
- ❌ Code execution — Planner produces the plan, Claude Code executes it
- ❌ Ongoing monitoring — that's the workflow's own responsibility
- ❌ Marketing/GTM docs — only technical SDD documentation
- ❌ Deployment — Planner doesn't deploy anything

### Relationship to Other Workflows

| Workflow | Relationship |
|----------|-------------|
| All OpenClaw workflows | Planner produces the specs that define them |
| Pipeline V9 | Could be re-spec'd through Planner |
| Marketing System | Could be re-spec'd through Planner |
| Finance Tracker | Could be re-spec'd through Planner |
| Healthy Families / MatchMyHome | Planner produces their SDD docs |

---

## 2. Input / Output Contracts

### Input

**Two input modes + two utility commands:**

**Mode A: New idea (free text)**
```
Source: Human via Telegram (text message)
Trigger: /plan [description of idea]
Example: "/plan Sistema de planeación de apps o workflows que 
          corra en Claude Code o n8n, potenciado con IA..."

Validation:
- Must be non-empty
- No minimum length (Planner will ask clarifying questions)
```

**Mode B: Existing documentation**
```
Source: Human provides files (docs, monoliths, specs, code)
Trigger: /plan-from-docs [attach files or paste links]
Example: "/plan-from-docs" + 2 Google Docs of 15,000+ words each

Validation:
- Files must be readable (text, markdown, or parseable format)
- Planner will extract and map content to SDD templates with confidence scoring
- PII/secret scan runs before any content is sent to model providers
```

**Utility commands (not input modes):**
```
/plan-resume [run_id]   — Resume an interrupted run
/plan-status [run_id]   — Check current status
/plan-fix [run_id] [task_id] — Re-entry from Code blocker
```

**Context always loaded (for existing projects):**
```
- PROJECT_FOUNDATION.md (if exists)
- CONSTITUTION.md (if exists)
- LESSONS_LEARNED.md (if exists)
- DATA_MODEL.md (if exists)
- INTEGRATIONS.md (if exists)
- AUDIT_FINDINGS.md (if exists)
```

### Output

**Per document produced:**
```json
{
  "document_name": "string — e.g., PROJECT_FOUNDATION.md",
  "document_version": 1,
  "content": "string — full markdown content following template",
  "status": "draft | pre_audited | audited | human_approved",
  "pre_audit_fixes": {
    "safe_applied": ["AF-001: auto-fixed", "AF-003: auto-fixed"],
    "semantic_flagged": ["AF-007: highlighted for human review"]
  },
  "audit_result": {
    "gpt_technical": { "model": "GPT-5.4", "issues_found": 0, "summary": "string" },
    "gpt_architecture": { "model": "GPT-5.4", "issues_found": 0, "summary": "string" },
    "gemini_technical": { "model": "Gemini 3.1 Pro", "issues_found": 0, "summary": "string" },
    "gemini_architecture": { "model": "Gemini 3.1 Pro", "issues_found": 0, "summary": "string" },
    "conflicts": ["Finding X: GPT says CRITICAL, Gemini says PASS — both arguments presented to human"]
  },
  "lessons_check": {
    "violations": [],
    "recommendations": ["LL-XXX: applies because..."]
  },
  "decision_log": {
    "summary": "string — 500-word executive summary",
    "hard_decisions": {
      "db_choice": "PostgreSQL — self-hosted, no vendor lock",
      "auth_model": "JWT with refresh — mobile + web clients"
    }
  },
  "_summary": "Human-readable: what this document contains and why"
}
```

**Final deliverable (all docs combined):**
```
project-root/
├── docs/
│   ├── PROJECT_FOUNDATION.md    ← if new project
│   ├── CONSTITUTION.md          ← if new project
│   ├── DATA_MODEL.md            ← if new project
│   ├── INTEGRATIONS.md          ← if new project
│   ├── LESSONS_LEARNED.md       ← if new project
│   ├── AUDIT_FINDINGS.md        ← persistent, grows over time
│   └── specs/
│       └── [module-or-workflow]/
│           ├── spec.md          ← always
│           ├── plan.md          ← always
│           └── tasks.md         ← always
└── planner_runs/
    └── [run_id]/
        ├── planner_state.json   ← full state, committed to repo
        ├── decision_logs/       ← per-document decision summaries
        ├── drafts/              ← intermediate drafts
        ├── audits/              ← raw audit results
        ├── history_archive/     ← raw chat history (moved after doc approval)
        └── output/              ← final approved docs
```

**Quality criteria:**
- All template sections filled (no empty placeholders)
- No stubs: "TBD", "placeholder", "some_type" → FAIL
- Audit by 2 models (4 calls) finds 0 critical issues (applies to ALL docs including plan+tasks)
- Pre-audit check catches all previously-known safe patterns
- Lessons check finds 0 violations
- Cross-document consistency check passes (no contradictions between docs)
- Human approves each document before moving to next

---

## 3. Phases & Agents

### Flow Overview

```
┌─────────────────────────────────────────────────────┐
│ PHASE 0: SETUP                                       │
│ Detect mode (new project / existing / monolith)      │
│ Load context. Determine which docs to produce.       │
│ Ask human: "Is this a module/app or workflow/pipeline?"│
│ PII/secret scan on any uploaded documents (Mode B)   │
│ HUMAN GATE: confirm mode + doc list + scan results   │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 1: INTAKE (per document, looping)              │
│ AI evaluates idea → asks questions → user answers    │
│ Max 5 rounds per section, then:                      │
│   → Propose "Assumed Default" based on context       │
│   → Mark as [ASSUMPTION — validate during impl]      │
│   → Or escalate to choice between concrete options   │
│ HUMAN GATE: "Was idea captured properly?"            │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 1.5: IDEATION (2 models) — conditional         │
│ Send captured concept to GPT-5.4 + Gemini 3.1 Pro   │
│ Each suggests features/improvements human may have   │
│ missed. Primary triages and presents best ideas.     │
│ HUMAN GATE: accept/reject/modify OR skip ideation    │
│ Note: runs for spec docs; skipped for foundation docs│
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 2: DRAFT (per document)                        │
│ AI populates the SDD template with intake answers    │
│ + accepted ideation suggestions                      │
│ Produces human-readable document                     │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 2.5: PRE-AUDIT CHECK                           │
│ Compare draft against AUDIT_FINDINGS.md              │
│ Safe fixes (formatting/structure): auto-apply        │
│ Semantic fixes (logic/architecture): highlight with  │
│   > [AF-XXX SUGGESTION]: ... for human review        │
│ Goal: auditors find NEW issues only                  │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 3: AUDIT (per document, 2 models × 2 roles)   │
│ Sequential queue with jittered backoff (5-10s)       │
│ GPT-5.4 as adversarial technical auditor             │
│ GPT-5.4 as senior systems architect                  │
│ Gemini 3.1 Pro as adversarial technical auditor      │
│ Gemini 3.1 Pro as senior systems architect           │
│ = 4 API calls total                                  │
│ Primary (Opus) triages all results into summary      │
│ CONFLICT RULE: if auditors disagree on CRITICAL,     │
│   both raw arguments go to human, no triage filter   │
│ DELTA-AUDIT RULE: after human fixes criticals:       │
│   Minor fix → Primary (Opus) sanity check (1 call)   │
│   Architecture change → 1 auditor re-audits section  │
│   Never full 4-call re-audit after corrections       │
│ CONDITIONAL 2ND ROUND: full re-audit (4 calls) only  │
│   if doc changed >30%, human requests it, or doc is  │
│   WORKFLOW_SPEC / high complexity                    │
│ HUMAN GATE: resolve critical audit findings          │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 4: LESSONS CHECK (per document)                │
│ Compare document against LESSONS_LEARNED.md          │
│ Flag any rule violations or missing applications     │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 5: FINALIZE (per document)                     │
│ Apply fixes from audit + lessons check               │
│ All AF-applied changes visible with [AF-XXX] markers │
│ Send to human: inline summary (key changes, AF       │
│   markers, cost) + .md file attachment               │
│ Human can approve from summary or open full file     │
│ HUMAN GATE: approve or request another round         │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 6: UPDATE RECORDS                              │
│ Archive raw chat history → history_archive/          │
│ Generate Decision Log:                               │
│   - 500-word executive summary                       │
│   - Hard Decisions list (key:value, indexable)       │
│   - Orchestrator can "recall" from history_archive   │
│     if ambiguity detected in future phases           │
│ Generate Entity Map for this doc (entities, IDs,     │
│   APIs, rules, states) for cross-doc validation      │
│ Update LESSONS_LEARNED.md with any new findings      │
│ Update AUDIT_FINDINGS.md (propose new entries, human │
│   approves before they become active)                │
│ Update PROJECT_FOUNDATION.md doc registry            │
│ Log run data to planner_state.json                   │
└────────────────────┬────────────────────────────────┘
                     ▼
              More documents?
              ┌─── Yes → Loop to PHASE 1 for next doc
              └─── No  → PHASE 6.5
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 6.5: CROSS-DOCUMENT VALIDATION                 │
│ Validate consistency using Entity Maps (NOT full     │
│ docs). Each Entity Map contains: entities, IDs,      │
│ API endpoints, rules, state machines from that doc.  │
│ If conflict detected → load ONLY the specific        │
│ sections involved, not the entire documents.         │
│ Checks: entity names, API refs, constitution rules,  │
│   naming/ID conflicts, state transitions             │
│ HUMAN GATE: resolve any contradictions found         │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 7: GENERATE PLAN + TASKS                       │
│ From approved spec → plan.md (phases + gates)        │
│ From plan → tasks.md (atomic, <30 min each)          │
│ Each task includes:                                  │
│   - depends_on: [TASK-XXX, ...]                      │
│   - if_blocked: MINOR/MODERATE/CRITICAL actions      │
│ For large projects: module-by-module with human      │
│ Full 2-model audit (4 calls) on plan+tasks           │
│ HUMAN GATE: approve plan + tasks                     │
└────────────────────┬────────────────────────────────┘
                     ▼
                  COMPLETE
         → Ready for Claude Code execution
         → Re-entry protocol defined in tasks.md
```

### Document Processing Order

**New project:**
```
1. PROJECT_FOUNDATION.md   ← establishes context for everything
2. CONSTITUTION.md         ← rules that constrain everything
3. DATA_MODEL.md           ← data structures
4. INTEGRATIONS.md         ← external dependencies
5. LESSONS_LEARNED.md      ← initialize with relevant existing entries
6. spec.md                 ← the actual module/workflow spec
── Phase 6.5: Cross-doc validation ──
7. plan.md + tasks.md      ← execution plan (generated from spec)
```

**Existing project (new module/workflow):**
```
0. READ: Foundation, Constitution, Lessons, Data Model, Integrations, Audit Findings
1. spec.md                 ← the new module/workflow spec
── Phase 6.5: Cross-doc validation (spec vs existing docs) ──
2. plan.md + tasks.md      ← execution plan
```

**Monolith extraction:**
```
0. SANITIZE: PII/secret scan on all uploaded files
1. PARSE: Identify content blocks in monolith
2. MAP: Auto-assign each block to target SDD template
   - Confidence score per block (high/medium/low)
   - Multi-tagging: one block can feed multiple templates
   - Low-confidence blocks (<80%) flagged for human review
3. AUDIT MAPPING: Send low-confidence blocks to 1 auditor model for validation
4. PRESENT: Show mapping to human for validation (document by document)
5. FILL: Populate templates, question rounds per document as needed
6. AUDIT: Normal audit flow per document
```

**Large projects (10+ modules):**
```
0. Master plan: list all modules with 1-line description + dependency order
1. HUMAN confirms order and priorities
2. Loop: one module at a time through full Phases 1-7
3. After each module: human decides whether to continue or pause
```

### Agent Details

| Phase | Agent Role | What it does | Model | Provider | Est. Cost (ref only) |
|-------|-----------|-------------|-------|----------|---------------------|
| 0 | Setup Analyzer | Detect mode, doc list, PII scan | Claude Opus 4.6 | Anthropic | ~$0.10 |
| 1 | Intake Interviewer | Ask questions, capture answers, max 5 rounds/section | Claude Opus 4.6 | Anthropic | ~$0.50-2.00/doc |
| 1.5a | Ideation Agent A | Suggest features/improvements (conditional) | GPT-5.4 | OpenAI | ~$0.20-0.50 |
| 1.5b | Ideation Agent B | Suggest features/improvements (conditional) | Gemini 3.1 Pro | Google | ~$0.10-0.30 |
| 1.5t | Ideation Triager | Filter + merge ideation results | Claude Opus 4.6 | Anthropic | ~$0.10 |
| 2 | Document Drafter | Convert intake + ideation into SDD template | Claude Opus 4.6 | Anthropic | ~$0.20-0.50/doc |
| 2.5 | Pre-Audit Checker | Compare draft vs AF (safe auto-fix, semantic flag) | Claude Opus 4.6 | Anthropic | ~$0.10/doc |
| 3a | Technical Auditor | Find flaws, gaps, contradictions (adversarial) | GPT-5.4 | OpenAI | ~$0.30-0.50/doc |
| 3b | Architecture Reviewer | Find missing architecture/ops concerns | GPT-5.4 | OpenAI | ~$0.30-0.50/doc |
| 3c | Technical Auditor | Find flaws, gaps, contradictions (adversarial) | Gemini 3.1 Pro | Google | ~$0.15-0.30/doc |
| 3d | Architecture Reviewer | Find missing architecture/ops concerns | Gemini 3.1 Pro | Google | ~$0.15-0.30/doc |
| 3t | Audit Triager | Filter 4 results; force Conflict Flags to human | Claude Opus 4.6 | Anthropic | ~$0.15/doc |
| 4 | Lessons Validator | Check doc against LESSONS_LEARNED.md | Claude Opus 4.6 | Anthropic | ~$0.10/doc |
| 5 | Document Finalizer | Apply fixes, produce final version | Claude Opus 4.6 | Anthropic | ~$0.20-0.50/doc |
| 6 | Record Updater | Archive history, generate decision log, update AF/LL | Claude Opus 4.6 | Anthropic | ~$0.10/doc |
| 6.5 | Cross-Doc Validator | Check consistency across all approved docs | Claude Opus 4.6 | Anthropic | ~$0.20-0.50 |
| 7a | Plan Generator | Spec → plan.md with phases and gates | Claude Opus 4.6 | Anthropic | ~$0.30-0.50 |
| 7b | Task Generator | Plan → tasks.md with depends_on + if_blocked | Claude Opus 4.6 | Anthropic | ~$0.30-0.50 |
| 7c-f | Plan+Tasks Auditors | Full 2-model audit (4 calls) on plan+tasks | GPT-5.4 + Gemini 3.1 | Both | ~$0.60-1.20 |

> **Note:** Cost estimates are reference only, not gates. Actual costs are tracked per call
> and will calibrate after ~10 runs. What matters is the running total vs the $30/$50 limits.

### Gate Criteria

| Gate | After Phase | Pass Condition | Fail Action |
|------|------------|----------------|-------------|
| G0 | Phase 0 | Mode detected, doc type confirmed, PII scan clean, doc list confirmed | Clarify / redact secrets |
| G1 | Phase 1 | Human confirms "idea captured properly" (max 5 rounds/section) | Propose Assumed Default with [ASSUMPTION] flag, or escalate to choice |
| G1.5 | Phase 1.5 | Human accepted/rejected ideation OR skipped | N/A (conditional phase) |
| G2 | Phase 2 | Document has all sections filled, no stubs | Re-draft failing sections |
| G2.5 | Phase 2.5 | Safe AF patterns auto-fixed; semantic flags highlighted | Human reviews semantic flags |
| G3 | Phase 3 | Audit triage: 0 critical issues remaining; Conflict Flags resolved by human | Human resolves criticals + conflicts |
| G4 | Phase 4 | 0 lesson violations | Fix violations or justify exceptions |
| G5 | Phase 5 | Human approves document (delivered as .md file, not inline text) | Another round or accept with notes |
| G6.5 | Phase 6.5 | 0 cross-document contradictions | Fix contradictions before plan generation |
| G7 | Phase 7 | Plan+tasks pass full 2-model audit (4 calls), human approves | Revise plan |

---

## 4. Model Selection

### Model Assignment (Benchmark-Justified)

| Task | Model | Provider | Why this model |
|------|-------|----------|---------------|
| Primary (Intake, Draft, Finalize, Plan, Tasks) | Claude Opus 4.6 | Anthropic | #1 SWE-bench (80.8%), #1 Mazur Writing (8.561), #1 EQ-Bench Creative (1932 Elo). Best at writing + coding = best for producing SDD docs |
| Ideation Agent A | GPT-5.4 | OpenAI | Strong general reasoning (Intelligence Index 57.17), good at edge case discovery |
| Ideation Agent B | Gemini 3.1 Pro | Google | #1 GPQA Diamond (94.3%), precise & concise suggestions, cheapest ($2/$12 per M) |
| Technical Auditor | GPT-5.4 | OpenAI | Aggressive finding patterns (20+ specific issues in testing), τ2-bench 97% |
| Architecture Reviewer | GPT-5.4 | OpenAI | Same call, different prompt/role |
| Technical Auditor | Gemini 3.1 Pro | Google | Precise, finds fewer but higher-signal issues (7-8 items in testing, all valid) |
| Architecture Reviewer | Gemini 3.1 Pro | Google | Same call, different prompt/role |
| Audit Triager | Claude Opus 4.6 | Anthropic | Must understand context deeply to filter noise from signal |
| Plan+Tasks Auditors | GPT-5.4 + Gemini 3.1 | Both | Same standard as document audit — plan is the most execution-critical artifact |
| Degraded Mode Primary (fallback) | GPT-5.4 | OpenAI | If Anthropic is down, switch to GPT-5.4. Alert human: quality may differ. |

### Model Rules
- Primary work uses Claude Opus 4.6 — quality over cost for the Planner
- **Degraded Mode:** If Opus is unreachable (Anthropic outage), offer to switch to GPT-5.4 as temporary primary. Human must approve. Alert: "Running in degraded mode — quality may differ from Opus."
- Audit ALWAYS uses 2 DIFFERENT models from different providers
- Each auditor runs BOTH roles (technical + architecture) = 4 API calls per document
- **Plan + tasks get the SAME 4-call audit** as every other document
- NEVER use the same model for drafting AND auditing the same document
- If a model truncates output (>8K tokens), switch to block mode (LL-AI-017)
- Audit results are presented as human-readable summary, not raw JSON
- **Conflict Flag:** If 2 auditors disagree on a CRITICAL finding, BOTH raw arguments go to human — triager cannot filter these out
- **Delta-Audit after corrections:** Minor fix → Opus sanity check (1 call). Architecture change → 1 auditor re-audits affected section only. Never full 4-call re-audit post-correction.
- **Conditional second round:** Full re-audit (4 calls) on a document only if: doc changed >30% after first audit, human explicitly requests it, or doc is WORKFLOW_SPEC / high complexity. Standard flow is 1 round.
- **Sequential audit queue:** 5-10 second jittered backoff between audit API calls to avoid 429 rate limits

> **V1 Concurrency Limit:** This system is designed for single-operator, low-concurrency use.
> Multi-run concurrency is not guaranteed. One active Planner run at a time per project.

### Benchmark Reference (March 2026)

| Benchmark | Claude Opus 4.6 | GPT-5.4 | Gemini 3.1 Pro |
|-----------|-----------------|---------|----------------|
| SWE-bench Verified | **80.8%** | 79.8% | 80.6% |
| Mazur Writing | **8.561** | 8.511 | — |
| EQ-Bench Creative Writing | **1932 Elo** | — | — |
| GPQA Diamond (PhD reasoning) | — | — | **94.3%** |
| Intelligence Index | — | **57.17** | **57.18** (tied) |
| τ2-bench (tool use) | — | **97%** | — |
| Terminal-Bench | **65.4** | 78.2 | 68.5 |
| API Cost (input/output per M) | $5/$25 | ~$2/$10 | $2/$12 |

> These benchmarks should be stored in LESSONS_LEARNED as LL-AI-XXX and
> re-evaluated quarterly as models evolve rapidly.

---

## 5. Failure & Recovery

### Failure Taxonomy

| Category | Failure Mode | Detection | Recovery | Max Retries |
|----------|-------------|-----------|----------|-------------|
| **Transient** | Model timeout/disconnect | No response within timeout | Retry with streaming mode | 2 |
| **Transient** | API rate limit (429) | HTTP 429 response | Jittered backoff, retry after delay | 3 |
| **Transient** | Provider 5xx errors | HTTP 5xx response | Wait 30s, retry; if persistent → switch provider | 2 |
| **Transient** | Output truncation | Response ends mid-sentence | Switch to block mode, section by section | 2 |
| **Persistent** | Auth failure to model provider | HTTP 401/403 | Alert human, check API keys | 0 |
| **Persistent** | Auth failure to Google Docs/Drive | Access denied | Alert human, request permissions | 0 |
| **Persistent** | Malformed model output (unparseable) | JSON/markdown parse fails | Re-prompt with stricter format instructions | 2 |
| **Data-Corrupt** | planner_state.json corrupted | Schema validation fails on load | Restore from last git commit | 0 |
| **Data-Corrupt** | Partial write (draft saved, audit lost) | Consistency check on resume | Mark run DEGRADED, re-run failed phase | 1 |
| **Data-Corrupt** | Stale context after resume | Document versions don't match | Reload all docs from filesystem, re-validate | 1 |
| **Human-Blocked** | Human doesn't respond (Telegram) | No response >24 hours | Send reminder, save state for resume | 0 (wait) |
| **Human-Blocked** | Audit models disagree on critical | Conflict Flag detected | Both arguments to human, human decides | 0 |
| **Provider-Degraded** | Primary model (Opus) unavailable | Connection failures to Anthropic | Offer Degraded Mode (GPT-5.4 as primary) | 0 (human decides) |
| **Logical** | Stub/placeholder in output | Structural validator catches "TBD" | Re-draft that section | 2 |
| **Logical** | Cost exceeds alert threshold | Cost tracker at $30 | Alert human, continue only with approval | 0 |

### Escalation Chain
```
1. Retry with diagnosis (different prompt, same model)
2. Retry with different model (if available)
3. Split into smaller chunks
4. Alert human with full context, human decides
RULE: Always save partial output before retrying
RULE: Never retry with identical parameters (LL-PROC-026)
RULE: On resume, run consistency_check before continuing
```

### State Persistence

**planner_state.json schema:**
```json
{
  "run_id": "RUN-20260406-001",
  "run_status": "active | paused | degraded | completed | failed",
  "locked_by": "planner_orchestrator | null",
  "locked_until": "ISO timestamp | null",
  "state_version": 47,
  "current_phase": "3",
  "current_document": {
    "name": "CONSTITUTION.md",
    "version": 2,
    "phase_status": "audit_in_progress",
    "phase_attempt": 1
  },
  "last_checkpoint": "Phase 2.5 complete for CONSTITUTION.md v2",
  "documents_completed": ["PROJECT_FOUNDATION.md"],
  "documents_pending": ["DATA_MODEL.md", "INTEGRATIONS.md", "..."],
  "decision_logs": {
    "PROJECT_FOUNDATION.md": "500-word summary of decisions..."
  },
  "cost": {
    "total_usd": 4.23,
    "by_model": { "opus": 2.10, "gpt": 1.50, "gemini": 0.63 },
    "by_phase": { "0": 0.10, "1": 1.80, "1.5": 0.45, "..." : "..." },
    "by_document": { "PROJECT_FOUNDATION.md": 2.15, "..." : "..." }
  }
}
```

**Rules:**
- Updated after every phase completion and every human gate
- `state_version` increments on every write (optimistic concurrency)
- `locked_by` prevents duplicate `/plan-resume` from corrupting state
- On resume: validate `state_version` matches filesystem, run consistency check
- Committed to project repo (small files, valuable history)
- All intermediate outputs (drafts, audit results) saved in `planner_runs/{run_id}/`

---

## 6. Cost Tracking

### Budget

| Metric | Limit |
|--------|-------|
| Alert threshold | $30 (Telegram notification) |
| Hard limit per run | $50 (requires human approval to continue) |

> Cost estimates per phase are reference only (see Agent Details table).
> Actual per-phase costs will calibrate after ~10 runs. The system tracks
> real costs per call; estimates are not used as gates.

### How Costs are Tracked
- Each agent call logs: model, tokens in/out, estimated USD, duration
- planner_state.json accumulates cost per document, per phase, and per model
- After each phase: cost summary sent to human via Telegram
- At end of run: total cost report with breakdown by model and phase
- Cost data feeds into future optimization (identify expensive phases)

### Cost Optimization
- Primary model is Claude Opus 4.6 — premium cost justified by output quality
- Gemini 3.1 Pro used where possible for audit (cheapest at $2/$12 per M)
- Context compression via Python filter before every agent call (see §7.1)
- Conversation history partitioned per document (see §7.2)
- Monolith chunks processed sequentially (not all loaded at once)
- Pre-audit check (Phase 2.5) reduces wasted audit cycles
- Audit triage filters noise before presenting to human (reduces human time)
- Sequential audit queue prevents rate limit retries (which waste tokens)

---

## 7. Operational Playbook

### 7.1 Context Compression Rule

**Every agent receives ONLY the fields it needs.** The orchestrator is Python code
(not an LLM) that filters `planner_state.json` before passing to any agent.

```python
def filter_for_agent(full_state: dict, agent_role: str) -> dict:
    """
    Static mapping: each agent role → list of required fields.
    No LLM involved. No tokens consumed. Cannot be blocked by context limits.
    
    DENY-BY-DEFAULT: if a field is not in the mapping, it is NOT sent.
    If a new field is added to the state, it must be explicitly added
    to relevant agent mappings before it becomes available.
    """
    AGENT_FIELDS = {
        "intake_interviewer": [
            "current_document.type",
            "current_document.template",
            "current_document.sections_completed",
            "project_context.foundation_summary",
            "decision_logs",          # past doc decisions, NOT raw history
            # NOT: full foundation, cost data, audit results
        ],
        "technical_auditor": [
            "current_document.content",
            "current_document.type",
            "constitution.rules",
            # CROSS-DOC: if doc references other docs, include referenced sections
            "cross_references",       # populated by orchestrator scan
            # NOT: cost history, telegram config, run metadata
        ],
        "architecture_reviewer": [
            "current_document.content",
            "current_document.type",
            "project_context.stack",
            "project_context.integrations_summary",
            "cross_references",
            # NOT: conversation history, ideation results, cost data
        ],
        "plan_generator": [
            "approved_spec.content",
            "constitution.execution_rules",
            "lessons_learned.relevant_entries",
            "data_model.summary",
            "integrations.summary",
            # NOT: audit history, draft versions, raw audit results
        ],
        "cross_doc_validator": [
            "all_entity_maps",            # NOT full docs — maps generated in Phase 6
            "constitution.rules",
            # If conflict detected: orchestrator loads specific sections on demand
        ],
        "codebase_reconciler": [     # for re-entry protocol
            "git_diff_summary",
            "existing_files_list",
            "original_tasks",
            "blocker_description",
        ],
    }
    
    fields = AGENT_FIELDS.get(agent_role)
    if fields is None:
        raise ValueError(f"No field mapping defined for agent role: {agent_role}")
    return extract_fields(full_state, fields)
```

**Rules:**
- No agent ever receives the full `planner_state.json`
- If a new agent role is added, its field mapping MUST be defined before the first call
- `cross_references`: when a document references entities/APIs/rules from another doc, the orchestrator scans for those references and includes the relevant source sections (not summaries)
- Raises error (not silent empty) if an undefined agent role is requested

> This pattern applies to ALL workflows the Planner generates, not just the Planner
> itself. Every plan.md and tasks.md produced by the Planner must include this
> compression pattern in the architecture section.

### 7.2 Conversation History Management

**Problem:** After 7+ documents, raw conversation history can reach 40,000+ tokens,
causing the Intake Interviewer to spend $2+ per message just processing old context.

**Solution: Per-Document History Partitioning**

```
Document approved → Phase 6 triggers:
1. Raw chat history for that document → history_archive/{doc_name}.json
2. Generate "Decision Log" — structured, NOT just prose:

   EXECUTIVE SUMMARY (500 words max):
   Free-text summary of what was decided and why.
   
   HARD DECISIONS (indexable key:value pairs):
   - db_choice: PostgreSQL (not Supabase) — because self-hosted, no vendor lock
   - auth_model: JWT with refresh tokens — because mobile + web clients
   - cost_ceiling: $10/run — because solo dev budget
   - rejected_feature: real-time sync — because complexity vs MVP value
   
3. Decision Log replaces raw history in active context.
4. "Recall" capability: if Intake Interviewer detects ambiguity
   that might have been resolved in a previous document's discussion,
   orchestrator can load the SPECIFIC section from history_archive
   (not the entire file) to resolve it.

Result: Document #7's Intake receives ~3,500 tokens of Decision Logs
        instead of ~40,000 tokens of raw conversation history.
        Hard Decisions are searchable by key for quick lookups.
```

### 7.3 Telegram Interface Rules

**Telegram has a 4,096-character message limit.** The Planner respects this:

| Content Type | Delivery Method |
|-------------|----------------|
| Questions, summaries, status updates | Inline text (within 4096 chars) |
| Cost reports, progress updates | Inline text |
| Audit triage summaries | Inline text (summary only) |
| Draft documents for review | **.md file attachment** |
| Final approved documents | **.md file attachment** |
| Diff reviews (what changed) | Inline summary + file if needed |
| Human approval | Inline keyboard buttons (✅ / 🔄 / ❌) |

**Rules:**
- NEVER send raw document content inline if it exceeds 3,500 characters
- Use Telegram inline keyboard buttons for structured approvals
- Every prompt includes: `[RUN-ID] [DOC] [PHASE]` prefix for context
- Human replies are matched to the correct run/doc/phase by the orchestrator
- If human replies without context, ask for clarification (don't guess)

### 7.4 Telegram Commands

> **NOTE:** Skill directory names with hyphens become underscores in Telegram
> commands (e.g., `sdd-planner/` → `/sdd_planner`). See LL-INFRA-038.
>
> **IMPORTANT:** Run `/reset` before the first skill invocation in a session
> to prevent the LLM from reading Python files and simulating the workflow
> instead of executing via exec tool. See LL-INFRA-037.

```bash
# Start a new project from an idea:
/sdd_planner [description of idea in free text]
# Executes: python3 scripts/run_sdd_planner.py start "<args>"
# Runs Phase 0, creates run, presents Gate G0.
# Human must reply with MODULE_SPEC or WORKFLOW_SPEC.

# Respond to a pending gate (G0, G1, G3, G5, G6.5, G7):
/sdd_planner_reply [response text]
# Executes: status to find run/gate, then gate-reply <run_id> <gate_id> "<response>"
# Resolves the gate, continues phases until next gate or completion.

# Start from existing documentation:
# ⬜ NOT YET IMPLEMENTED — /plan-from-docs [attach files or paste links]

# Re-entry from Code blocker:
# ⬜ NOT YET IMPLEMENTED — /plan-fix [run_id] [task_id]

# Via CLI (alternative — all commands available):
cd ~/.openclaw/workspace-meta-planner
python3 scripts/run_sdd_planner.py start "Build a todo CLI app"
python3 scripts/run_sdd_planner.py gate-reply RUN-xxx G0 "MODULE_SPEC"
python3 scripts/run_sdd_planner.py status [run_id]
python3 scripts/run_sdd_planner.py resume [run_id]
python3 scripts/run_sdd_planner.py test-call
```

### 7.5 PII / Secret Detection (Phase 0)

Before any uploaded document content is sent to model providers (Anthropic, OpenAI, Google),
a Python-based scanner checks for potential secrets. **This is detection, not guaranteed
scrubbing.** The human is the final authority on what is sensitive in their context.

```python
PATTERNS = [
    r'(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*\S+',
    r'sk-[a-zA-Z0-9]{20,}',           # OpenAI-style keys
    r'AIza[a-zA-Z0-9_-]{35}',         # Google API keys
    r'ghp_[a-zA-Z0-9]{36}',           # GitHub PATs
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # emails
    r'\b\d{3}-\d{2}-\d{4}\b',         # SSN-like
]
```

**If matches found:**
- **High confidence** (API keys like `sk-...`, `ghp_...`, `AIza...`): Block and require human decision
- **Low confidence** (emails in spec docs, variable names matching patterns): Show as warning, allow to continue
- Human can: redact, skip file, or approve as-is
- **No auto-redaction** — human decides what's sensitive in their context

> This is a best-effort defense, not a guarantee. The human remains responsible
> for reviewing content before it is sent to external providers.

### 7.6 Common Issues

```bash
# If model truncates output:
# → System auto-switches to block mode and retries

# If audit triggers 429 rate limit:
# → Sequential queue with jittered backoff handles this automatically

# If human needs to pause:
# → Just stop responding. State is saved. Use /sdd_planner_reply or CLI resume later.

# If cost alert triggers at $30:
# → Telegram notifies. Human decides: continue or optimize.

# If Opus is down:
# → System offers Degraded Mode with GPT-5.4. Human approves.
```

---

## 8. Conversation Design

### Principles (how the Planner talks to the human)

1. **Concise, concrete, actionable.** No filler. No "Great question!" Every message has a purpose.
2. **Questions are specific.** Not "Tell me about your project" but "What problem does this solve for the end user?"
3. **AI proposes, human decides.** The Planner suggests answers based on context, the human confirms or corrects.
4. **Summarize before moving on.** After each section, the Planner shows what it understood and asks "Is this right?"
5. **Audit results are triaged — except conflicts.** Human sees "3 critical need input, 9 noise I'll handle." But if auditors DISAGREE on a critical, both arguments are shown raw.
6. **Progress is visible.** After each phase: "✅ PROJECT_FOUNDATION complete. Cost so far: $1.20. Next: CONSTITUTION.md. Ready?"
7. **Technical depth matches the human.** If the human gives technical answers, respond technically. If they give business answers, translate to technical in the doc but keep the conversation accessible.
8. **Never tedious.** The conversation should feel like a productive strategy session with a skilled colleague.
9. **Max 5 rounds per section.** After 5 rounds of questions on a single section, the Planner either proposes a best-guess answer for confirmation, defers the section with explicit unknowns, or escalates to a choice between concrete options.
10. **Documents delivered as files.** Full documents are sent as .md file attachments, never as inline text walls.

### Message Templates

**Intake start:**
```
📋 Starting SDD Planner [RUN-20260406-001]

I detected this is a [new project / new module for existing project].
Document type: [MODULE_SPEC / WORKFLOW_SPEC] — confirmed by you.
Documents to produce: [list]

Let's start with [DOCUMENT]. I'll ask you questions section by section.

First question: [specific question]
```

**Section complete:**
```
✅ [RUN-ID] [DOC] Section [X] captured:

[2-3 sentence summary in prose, NOT JSON]

Is this correct? (yes / needs changes)
```

**Ideation results:**
```
💡 [RUN-ID] Feature suggestions from 2 models:

GPT-5.4 suggested:
1. [feature] — My take: [worth adding / skip because...]
2. [feature] — My take: [worth adding / skip because...]

Gemini 3.1 suggested:
1. [feature] — My take: [worth adding / skip because...]

I recommend adding #1 and #3. Your call — accept/reject/modify each.
Or skip ideation entirely for this document.
```

**Pre-audit summary:**
```
🔧 [RUN-ID] Pre-audit check for [DOC]:
- [N] safe patterns auto-fixed (formatting/structure)
- [M] semantic suggestions highlighted with [AF-XXX] markers for your review

Sending to auditors now.
```

**Audit summary (no conflicts):**
```
🔍 [RUN-ID] Audit complete for [DOC]

4 audit calls completed:
- GPT-5.4 Technical: [X] issues
- GPT-5.4 Architecture: [Y] issues
- Gemini 3.1 Technical: [Z] issues
- Gemini 3.1 Architecture: [W] issues

After triage — [N] need your input:

1. [CRITICAL]: [plain language description]
   My suggestion: [proposed resolution]
   Your call: accept / modify / reject

[M] minor issues I'll fix automatically.
[K] items were noise (not applicable to this project scope).
```

**Audit summary (WITH conflicts):**
```
⚠️ [RUN-ID] Audit CONFLICT for [DOC]

The auditors DISAGREE on a critical finding:

GPT-5.4 says: "[their argument summarized]"
Gemini 3.1 says: "[their counter-argument summarized]"

I'm not filtering this one — your call:
A) Side with GPT's concern
B) Side with Gemini's assessment
C) Something else: [tell me]
```

**Document approval:**
```
📄 [RUN-ID] [DOC] ready for review

Key changes in this version:
- [1-2 sentence summary of what changed since last draft]
- AF markers applied: [list]
- Audit findings resolved: [count]

📎 [attached: DOCUMENT_NAME.md] — open for full review if needed

Cost for this document: $X.XX | Total so far: $X.XX

✅ Approve | 🔄 Another round | ❌ Start over
```

**Cross-doc validation:**
```
🔗 [RUN-ID] Cross-document validation complete

Checked: [list of docs] for consistency.
[N] contradictions found:

1. DATA_MODEL says "user_id is UUID" but SPEC says "user_id is integer"
   → Which is correct?

0 contradictions → ✅ Ready for plan generation.
```

**Run complete:**
```
🎉 [RUN-ID] SDD Planning complete!

📎 All documents attached.

Total cost: $X.XX (Opus $X | GPT $X | Gemini $X)
Your time: ~X minutes

Next step: Pass tasks.md to Claude Code:
"Read docs/specs/[name]/spec.md and plan.md. Start with TASK-001."
```

---

## 9. Large Plan Handling

### When plans exceed model context limits

**Problem:** A complex project (like MatchMyHome with 10+ modules) could produce
a tasks.md with 100+ tasks that exceeds any model's output limit.

**Solution: Module-by-module interactive loop**

```
Level 1: Master plan (1 page)
  Lists all modules/workflows with 1-line description and dependency order
  HUMAN GATE: confirm order and priorities

Level 2: Per-module loop (interactive with human)
  For each module in order:
    Phase 1-6: spec the module (full flow)
    Phase 6.5: cross-doc validation (this module vs all existing docs)
    Phase 7: generate plan.md + tasks.md for THAT module only
    Full 2-model audit (4 calls) on plan+tasks
    HUMAN GATE: approve or adjust before next module

Level 3: Per-module tasks.md (variable)
  Atomic tasks for that module only
```

**Rule:** Claude Code receives Level 2 + Level 3 for ONE module at a time.
Never load all tasks for all modules simultaneously.

**Rule:** If a single module's tasks.md exceeds ~100 tasks, split into
sub-modules and re-spec each sub-module separately.

**Rule:** After each module is complete, human decides: continue to next module
or pause the Planner run. State is saved for resume.

---

## 10. Code Re-Entry Protocol

### When Claude Code encounters problems during execution

The Planner defines a re-entry protocol in every tasks.md it produces. Each task
includes `depends_on` and `if_blocked` fields:

```markdown
### TASK-007: Implement authentication flow
- Objective: Enable user login via email/password with JWT token response
- Inputs: User schema from DATA_MODEL.md §users, auth config from INTEGRATIONS.md §auth
- Outputs: /api/auth/login endpoint returning JWT, auth middleware, user session model
- Files touched: src/auth/login.py, src/middleware/auth.py, tests/test_auth.py
- Done when: User can login via email/password and receive JWT; tests pass
- Estimated: 25 min
- depends_on: [TASK-003, TASK-005]
- if_blocked:
  - MINOR (typo, missing import, simple fix): Code fixes and documents in commit
  - MODERATE (unclear requirement, ambiguous spec): Code pauses, reports to human 
    via Telegram with specific question, human decides
  - CRITICAL (spec is wrong, architecture won't work): Code stops. Triggers
    /plan-fix with codebase reconciliation before re-planning.
```

> **Audit rule for tasks:** Every task must have ALL fields above populated.
> The plan+tasks auditor marks "0 tasks with missing fields" as a pass condition.
> "Executable without clarification" is verified by: all fields present + auditor
> finds 0 ambiguous objectives/inputs/outputs.

### Re-entry flow:
```
Code hits CRITICAL blocker
  → Code saves current state + description of blocker
  → Telegram notification to human: "TASK-007 blocked: [reason]"
  → Human triggers: /plan-fix [run_id] [task_id]
  
  STEP 1: CODEBASE RECONCILIATION
  → Specialized agent scans: git diff, file tree, partially implemented files
  → Produces: "Implementation Status Report" — what exists, what's broken, 
    what's half-done
  → This is fed to the Planner so delta tasks reflect ACTUAL repo state
  
  STEP 2: IMPACT ANALYSIS
  → Using task dependency graph (depends_on fields):
  → Compute impact radius of the blocker
  → Mark downstream tasks as:
     - VALID: not affected by this change
     - NEEDS_REVIEW: might be affected, human should verify
     - VOID: definitely invalidated, must be regenerated
  → Present impact analysis to human
  
  STEP 3: SPEC PATCH
  → Planner updates affected spec section(s)
  → Re-audit only changed sections (not full doc)
  → HUMAN GATE: approve spec changes
  
  STEP 4: DELTA TASKS
  → Generate new tasks for VOID items only
  → NEEDS_REVIEW items flagged for human confirmation
  → New tasks are aware of existing code (from Step 1)
  → HUMAN GATE: approve delta tasks before Code resumes
```

### Re-entry classes:
| Class | When | Special handling |
|-------|------|-----------------|
| Pre-merge | Code blocked before any commits | Simple: update spec, regenerate remaining tasks |
| Post-merge | Code already committed partial work | Codebase reconciliation required |
| Post-migration | Database changes already applied | Cannot auto-rollback; human must decide approach |
| Post-release | Live system affected | Emergency protocol; Planner only patches, human executes |

**Rule:** Re-entry never starts from scratch. It patches the existing spec and
generates delta tasks, not a full re-plan.

**Rule:** Codebase reconciliation is MANDATORY for any re-entry class except pre-merge.

---

## 11. AUDIT_FINDINGS.md — Persistent Audit Knowledge

### Purpose

A living document that accumulates patterns auditors find repeatedly. Before
sending any document to auditors (Phase 2.5), the Primary checks the draft against
this document and pre-corrects known safe patterns. This ensures auditors always
find NEW issues, never repeat old ones.

### Entry Lifecycle

```
PROPOSED → APPROVED → ACTIVE → DEPRECATED → ARCHIVED
   ↑          ↑         ↑          ↑             ↑
 Auto-created  Human    Working   Not triggered   Removed from
 after audit   confirms  in       in 3+ months    pre-audit check
               entry    pre-audit
```

**Rules:**
- New entries are auto-PROPOSED after every audit cycle (Phase 6)
- Human must APPROVE before entry becomes ACTIVE and used in pre-audit checks
- Duplicate detection: before proposing, check if similar pattern already exists
- Entries not triggered in 3+ months → auto-DEPRECATED, human can archive
- Each entry has a confidence score (how reliably it applies)

### Entry Classification

| Class | Auto-fix in Phase 2.5? | Example |
|-------|----------------------|---------|
| `safe_autofix` | Yes — apply silently | Missing "Failure & Recovery" section header |
| `requires_review` | No — highlight with `[AF-XXX SUGGESTION]` marker | Logic change to error handling flow |

**Rule:** Only `safe_autofix` entries are auto-applied. All `requires_review` entries
are highlighted in the document for human review in Phase 5.

### Format

```markdown
# AUDIT_FINDINGS.md

## Active Patterns

### AF-001: Missing error handling in data flow specs
- Status: ACTIVE
- Class: safe_autofix
- Confidence: HIGH
- First found: RUN-20260406-001, WORKFLOW_SPEC for Pipeline V9
- Pattern: Specs define happy path but no failure/retry for inter-agent data
- Fix: Add "Failure & Recovery" row to every data flow table
- Applies to: WORKFLOW_SPEC, MODULE_SPEC
- Last triggered: RUN-20260410-003

### AF-002: Constitution rules referenced but not enforced
- Status: ACTIVE
- Class: requires_review
- Confidence: MEDIUM
- First found: RUN-20260406-001, CONSTITUTION.md
- Pattern: Rules listed but no gate or check references them
- Fix: Every rule must link to a gate ID or pre-flight check item
- Applies to: CONSTITUTION, MODULE_SPEC, WORKFLOW_SPEC
- Last triggered: RUN-20260408-002

### AF-003: JSON contracts include unnecessary fields
- Status: ACTIVE
- Class: safe_autofix
- Confidence: HIGH
- First found: strategy-runtime-1 testing
- Pattern: Inter-agent payloads include full schema instead of only needed fields
- Fix: Apply filter_for_agent pattern
- Applies to: ALL workflow specs, all inter-agent contracts
- Last triggered: RUN-20260407-001

## Deprecated Patterns
(entries not triggered in 3+ months, pending archive)

## Archived Patterns
(historical reference only, not used in pre-audit)
```

---

## 12. Pre-Flight Checklist

- [ ] SDD templates available in repo (sdd-system or local copy)
- [ ] CONSTITUTION.md exists for the target project (or will be created)
- [ ] LESSONS_LEARNED.md accessible (OpenClaw's or project-specific)
- [ ] AUDIT_FINDINGS.md accessible (or will be initialized)
- [ ] Claude Opus 4.6 accessible via API/LiteLLM
- [ ] GPT-5.4 accessible via API (for audit + ideation)
- [ ] Gemini 3.1 Pro accessible via API (for audit + ideation)
- [ ] Fallback provider accessible (for Degraded Mode if needed)
- [ ] PII scan patterns up to date
- [ ] Budget limits configured ($30 alert, $50 hard)
- [ ] Telegram bot (@Super_Workflow_Creator_bot) operational
- [ ] Human available for interactive session (~30-90 min depending on project size)
- [ ] Relevant lessons reviewed:
  - [ ] LL-PLAN-001: Data flow planned before building
  - [ ] LL-PLAN-002: Contracts defined between producers/consumers
  - [ ] LL-PLAN-003: Test one item E2E before batch
  - [ ] LL-PLAN-010: No stub outputs
  - [ ] LL-ARCH-033: Compress context for heavy agents
  - [ ] LL-AI-017: Block mode for >8K token outputs

---

## 13. Definition of Done

- [ ] All target documents produced and human-approved
- [ ] Each document passed pre-audit check (AUDIT_FINDINGS.md — safe fixes applied, semantic flagged)
- [ ] Each document passed 2-model audit (4 calls) with 0 critical issues and 0 unresolved conflicts
- [ ] Each document passed lessons check with 0 violations
- [ ] Cross-document consistency check passed (Phase 6.5) with 0 contradictions
- [ ] Ideation phase completed or explicitly skipped by human
- [ ] plan.md + tasks.md passed full 2-model audit (4 calls)
- [ ] plan.md has phases with validation gates
- [ ] tasks.md has atomic tasks (<30 min each) with ALL required fields:
      objective, inputs, outputs, files_touched, done_when, depends_on, if_blocked
- [ ] Plan+tasks auditor finds 0 tasks with missing or ambiguous fields
- [ ] Total cost tracked and within hard limit ($50 max)
- [ ] planner_state.json committed with complete run data + cost breakdown
- [ ] Decision logs generated for all documents (raw history archived)
- [ ] LESSONS_LEARNED.md updated with any new findings from this run
- [ ] AUDIT_FINDINGS.md updated (new entries PROPOSED, human approves to ACTIVE)
- [ ] PROJECT_FOUNDATION.md §Doc Registry updated with new documents
- [ ] This spec status → ✅ Complete

---

## Resolved Decisions

| Decision | Resolution | Rationale |
|----------|-----------|-----------|
| Primary model | Claude Opus 4.6 | #1 writing + coding benchmarks. Planner output quality is everything. |
| Primary fallback | GPT-5.4 (Degraded Mode) | If Anthropic is down, human approves switch. Prevents total SPOF. |
| Auditor models | GPT-5.4 + Gemini 3.1 Pro | Different providers, different strengths. 4 calls (2 roles × 2 models). |
| Plan+tasks audit | Full 2-model audit (4 calls) | Plan is the most execution-critical artifact. Same standard as docs. |
| Audit conflict handling | Both raw arguments to human | Triager cannot filter out disagreements on CRITICAL findings. |
| MODULE vs WORKFLOW detection | Always ask human | 2-second question, prevents auto-detection errors. |
| Telegram document delivery | .md file attachments | 4096-char limit makes inline delivery unreliable for docs. |
| Telegram commands | /sdd_planner, /sdd_planner_reply (CLI: start, gate-reply, status, resume) | Skill dir names → underscore commands. /plan-from-docs and /plan-fix not yet implemented. |
| planner_runs/ storage | Inside project repo, committed (no gitignore) | Small files (~5KB), valuable run history. |
| Conversation history | Per-doc partitioning + Decision Logs | Prevents 40K+ token bloat by doc #7. ~500 words per doc summary. |
| Large project handling | Module-by-module interactive with human | Prevents context overflow, maintains human control. |
| Inter-agent payloads | Python filter (deny-by-default), cross-doc refs included | Prevents token bloat. Raises error for undefined roles. |
| Persistent audit patterns | AUDIT_FINDINGS.md with lifecycle (PROPOSED→APPROVED→ACTIVE→DEPRECATED) | Human approves new entries. Safe vs semantic classification. |
| Pre-audit auto-fix scope | Safe fixes only (formatting/structure). Semantic = flagged. | Prevents silent semantic changes without human review. |
| Monolith extraction | Confidence scoring + multi-tagging + auditor for low-confidence blocks | Prevents mapping errors from poisoning downstream docs. |
| Intake loop limit | Max 5 rounds per section | Prevents infinite loops. After 5: propose, defer, or escalate. |
| API rate limiting | Sequential audit queue with 5-10s jittered backoff | Prevents 429 errors during Phase 3's 4 rapid API calls. |
| PII/secret scanning | Python regex in Phase 0, human approves redactions | Prevents credential leakage to 3 different model providers. |
| Re-entry protocol | Codebase reconciliation + impact analysis + task dependencies | Delta tasks reflect actual repo state, not just spec changes. |
| Cost tracking | Track real costs, no estimate gates | Estimates calibrate after ~10 runs. $30 alert / $50 hard limit. |
| Cross-doc validation | Entity Maps (not full docs) + on-demand section loading | Prevents context explosion in large projects. |
| Deferred sections | "Assumed Default" with [ASSUMPTION] flag, not stubs/TBDs | Resolves contradiction between defer policy and no-stubs rule. |
| Decision Logs | 500-word summary + Hard Decisions (key:value) + recall capability | Prevents loss of technical nuance while saving tokens. |
| Delta-audit after corrections | Minor→Opus check, Architecture→1 auditor on section | Prevents cost explosion from full re-audit after every fix. |
| Conditional second audit round | Only if doc changed >30%, human requests, or high complexity | 1 round standard. 2nd round is option, not requirement. |
| Telegram document delivery | Inline summary + .md file attachment | Human can approve from summary or open full file. Reduces friction. |
| Task schema | 8 required fields per task, auditor verifies completeness | "Executable without clarification" is now measurable. |
| PII handling | Detection + human review (not guaranteed scrubbing) | Best-effort with smart triage (high/low confidence). |
| V1 concurrency | Single-operator, one active run per project | Explicit limit prevents over-promising. |

---

## Open Questions

- [ ] n8n node structure for future n8n implementation (after OpenClaw V1 works)
- [ ] Quarterly model benchmark re-evaluation process (who runs it, where results go)

---

## Audit Trail

**Round 1:** This spec was audited by 4 model calls:
- GPT-5.4 as adversarial technical auditor (20+ findings)
- GPT-5.4 as senior systems architect (7 findings)
- Gemini 3.1 Pro as adversarial technical auditor (8 findings)
- Gemini 3.1 Pro as senior systems architect (7 findings)

Key v3 incorporations: Telegram 4096 limit, planner_state.json versioning/locking,
cross-document consistency phase, codebase reconciliation in re-entry, task dependency graphs,
AUDIT_FINDINGS lifecycle states, pre-audit safe/semantic classification, conversation history
partitioning, monolith confidence scoring, PII scanning, API rate limit handling, primary SPOF
fallback, audit conflict flags, expanded failure taxonomy, plan+tasks full audit.

**Round 2:** v3 was re-audited by 4 model calls:
- GPT-5.4 as adversarial technical auditor (12 findings)
- GPT-5.4 as senior systems architect (7 findings)
- Gemini 3.1 Pro as adversarial technical auditor (5 findings)
- Gemini 3.1 Pro as senior systems architect (7 findings)

Key v4 incorporations: Assumed Default policy for deferred sections, hierarchical Decision
Logs with Hard Decisions + recall, Entity Maps for cross-doc validation, delta-audit rule,
conditional second round, inline summary + file for Telegram, measurable task schema,
smart PII triage (high/low confidence), V1 concurrency limit.

Items rejected across both rounds (enterprise overhead for solo dev): event-sourcing,
formal control-plane decomposition, scheduler/fleet management, database-backed state,
git branching strategy, weighted voting systems, message-version binding, separate
operational store, approval batching, global architecture skeleton.
