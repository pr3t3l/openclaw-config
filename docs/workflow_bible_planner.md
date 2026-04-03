# WORKFLOW BIBLE — META-WORKFLOW PLANNER
## Documento técnico autoritativo
### Last verified: 2026-04-03 (audit v3.0)
### Sources: extraction + master_plan_v3 + upgrade_v3.1 + build phases 0-3 + Bible v2 §10 + streaming/compression fixes

> **Source tags:** `[AUDIT]` = machine-verified 2026-03-29. `[EXT]` = from extraction.
> `[V3]` = from master_plan_v3_operational. `[UPG]` = from upgrade_plan_v3.1.
> `[BIBLE]` = from Project Bible v2.

---

# 1. PURPOSE & CONTEXT

The Meta-Workflow Planner is a tool that takes a raw idea and produces a buildable workflow plan through 3 phases with multi-model debate, before any code is written.

It was designed collaboratively by 4 models in 4 rounds of cross-review: Claude Opus 4.6 (v1) → GPT-5.4 (counter-proposal + 2 reviews) → Gemini 3.1 Pro (input) → MiniMax M2.7 (input) → Claude v3 final. `[EXT]`

**Bot:** @Super_Workflow_Creator_bot (Telegram)
**Agent:** Planner (id: planner)
**Workspace:** `~/.openclaw/workspace-meta-planner/` `[AUDIT]`

**When to use it:** For raw, unstructured ideas that need validation and architecture design. When architecture docs are already implementation-ready, skip the planner and go direct to Claude Code. `[EXT]`

### What are the other workflows?

| Workflow | Relationship to Planner |
|----------|------------------------|
| **Declassified Pipeline** | Planner produced `declassified-marketing` plan that became the Marketing System |
| **Marketing System** | Built from planner output. Planner validated the idea before Code implemented it |
| **Finance Tracker** | `finance-test` was an E2E test run through the planner |
| **Platform (Robotin)** | CEO agent routes "Planifica:" commands to this planner |

---

# 2. TIMELINE

| Date | Event | Result | Source |
|------|-------|--------|--------|
| 2026-03-24 04:41 | Initial idea: "un workflow que crea workflows" | Claude reviewed 4 reference files | [EXT] |
| 2026-03-24 05:00 | v1 designed: 10 agents, 4 phases, always-debate, ~$3.88/plan | Shared with GPT for cross-review | [EXT] |
| 2026-03-24 05:30 | GPT counter-proposal: 12 phases, principles P-01 to P-07 | Key insight: Gap Finder BEFORE architecture | [EXT] |
| 2026-03-24 06:00 | v2 merge: 6 fixed + 4 conditional agents, conditional debate | Combined best of Claude + GPT | [EXT] |
| 2026-03-24 06:30 | GPT review of v2: 4 fixes (no symlinks, config routing, gate persistence) | All accepted | [EXT] |
| 2026-03-24 07:00 | **v3 final** with Gemini + M2.7 input | 966-line master plan locked | [EXT] |
| 2026-03-24 08:30 | Build Phase 0: workspace, configs, schemas, start_plan.sh | Commit 174ac87, 6/6 tests pass | [EXT] |
| 2026-03-24 09:30 | Build Phase 1: Fase A (Clarify) — 3 agents + runner | Commit 50cb985. finance-test: 12 gaps, score 38 | [EXT] |
| 2026-03-24 10:30 | Build Phase 2: Fase B (Design) — debate + 3 agents | Commit ff75f65. TL-13 + TL-14 discovered. Debate: $0.76 | [EXT] |
| 2026-03-24 11:30 | Build Phase 3: Fase C (Buildability) — 3 agents + scripts | Commit 30ebae2. Verdict: NEEDS_REVISION (8 items) | [EXT] |
| 2026-03-24 12:00 | Git unification: all workspaces → openclaw-config | Commit 66bd183. 5 zombie workspaces archived | [EXT] |
| 2026-03-24 12:30 | CEO routing attempt: M2.7 ignored AGENTS.md | TL-16: M2.7 not reliable for multi-step routing | [EXT] |
| 2026-03-24 13:00 | Dashboard HTML created | meta_workflow_planner_dashboard.html | [EXT] |
| 2026-03-25 01:00 | Deep Analysis upgrade v3.1 designed | 7 changes: 3-round debate, red team, iterative intake | [UPG] |
| 2026-03-25 12:30 | Token tracking + clean E2E test | Commit 9b9822f. declassified-marketing: $1.148 | [EXT] |
| 2026-03-25 14:30 | Human-readable plan HTML | declassified_marketing_plan_readable.html | [EXT] |
| 2026-03-25 16:00 | upgrade_plan_v3.1 finalized | Ready for implementation, not yet executed | [UPG] |
| 2026-04-03 | Streaming + context compression + block mode | Fixes Anthropic API disconnects on large completions. L-33 added | [FIX] |
| 2026-04-03 | litellm_stream.py created | Shared streaming module replaces non-streaming curl in all scripts | [FIX] |
| 2026-04-03 | spawn_implementation_blocks.py created | Generic block-based C1 fallback (replaces hardcoded blocks script) | [FIX] |

---

# 3. ARCHITECTURE — 3 PHASES + 9 ARTIFACTS

```
FASE A: CLARIFY              FASE B: DESIGN              FASE C: BUILDABILITY
┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ A1: Intake       │    │ B1: Data Flow Mapper  │    │ C1: Implementation   │
│ A2: Gap Finder   │──→│ B2: Contract Designer │──→│ C2: Cost Estimator   │
│ A3: Scope Framer │    │ B3: Architecture      │    │ C3: Lessons Validator│
│                  │    │     (with debate)      │    │                      │
│ GATE #1          │    │ GATE #2               │    │ GATE #3              │
└─────────────────┘    └──────────────────────┘    └──────────────────────┘

Output: 9 validated JSON artifacts (00-08)
```

| Phase | Agent | What it does | Model | Est. cost |
|-------|-------|-------------|-------|-----------|
| A1 | intake-analyst | Extract structured summary from raw idea | claude-sonnet46 | $0.016 |
| A2 | gap-finder | Adversarial gap analysis (readiness score 0-100) | claude-sonnet46 | $0.074 |
| A3 | scope-framer | MVP/Standard/Advanced scope definition | claude-sonnet46 | $0.057 |
| — | **GATE #1** | Human reviews: idea, gaps, scope, readiness | — | — |
| B1 | data-flow-mapper | Map all artifacts: producer→file→consumer | claude-sonnet46 | $0.046 |
| B2 | contract-designer | JSON schemas for all artifacts | claude-sonnet46 | $0.122 |
| B3 | architecture-planner | Multi-model debate for architecture design | debate (variable) | $0.48 (critical) |
| — | **GATE #2** | Human reviews architecture decision | — | — |
| C1 | implementation-planner | Phased build plan with tests | claude-sonnet46 | $0.162 |
| C2 | cost_estimator.py | Deterministic cost calculation | script ($0) | $0 |
| C3 | lessons-validator | Validate plan against lessons learned | claude-sonnet46 | $0.190 |
| — | **GATE #3** | Human approves final plan | — | — |

---

# 4. SKILLS — 14 TOTAL `[AUDIT]`

### Core skills (8) — used in every run

| Skill | Phase | Model |
|-------|-------|-------|
| intake-analyst | A1 | claude-sonnet46 |
| gap-finder | A2 | claude-sonnet46 |
| scope-framer | A3 | claude-sonnet46 |
| data-flow-mapper | B1 | claude-sonnet46 |
| contract-designer | B2 | claude-sonnet46 |
| architecture-planner | B3 | debate (variable) |
| implementation-planner | C1 | claude-sonnet46 |
| lessons-validator | C3 | claude-sonnet46 |

### Conditional skills (6) — used in Deep Analysis or specific scenarios `[AUDIT]`

| Skill | Purpose | When used |
|-------|---------|-----------|
| capability-mapper | Maps existing system capabilities | Complex ideas involving existing infrastructure |
| compliance-reviewer | Reviews regulatory/legal constraints | Ideas with compliance requirements |
| creative-strategist | Creative direction and brand alignment | Marketing/content ideas |
| landscape-researcher | Market/competitive landscape (web search) | New market entry ideas |
| red-team | Adversarial review of architecture | Critical debate level |
| report-generator | HTML narrative report of plan | Deep Analysis level |

**NOTE:** Bible v1 said 8 skills. Audit found 14. The 6 conditional skills were added as part of the v3.1 upgrade design but are already present in the workspace. `[AUDIT]`

---

# 5. DEBATE SYSTEM `[VERIFIED 2026-03-31]`

### Debate levels (conditional, not ritual)

| Level | When | Models | Judge | Red Team | Est. cost |
|-------|------|--------|-------|----------|-----------|
| Simple | Straightforward ideas | claude-sonnet46 (1 model) | none | none | ~$0.15 |
| Complex | Multi-component systems | claude-opus46 + chatgpt-gpt54 | claude-sonnet46 | none | ~$0.45 |
| Critical/Deep | Infrastructure, high-cost, novel | claude-opus46 + chatgpt-gpt54 + gemini31pro-none | claude-opus46 | claude-opus46 | ~$0.48 |

### 3-round debate (LIVE — v3.1 confirmed) `[VERIFIED]`

```
Round 1: Each model produces independent proposal
Round 2: Cross-critique — each model sees others' proposals, critiques, and revises own
Round 3: Consolidation — synthesize best ideas into unified proposal
Then (critical/deep only): Red Team attacks the consolidated proposal
Judge: Evaluates final proposal
```

### Iterative intake (LIVE) `[VERIFIED]`

- Up to 5 rounds × 3 questions
- History saved in `intake_qa_history.json`
- If max rounds reached, forces status to READY
- Implemented in `spawn_planner_agent.py`

### Human gates with adjust (LIVE) `[VERIFIED]`

Gates show summary with options: yes / no / adjust. On adjust, phase re-runs with changes.

### Cross-critique prompt template (in use) `[EXT]`

```
You previously proposed this architecture:
{my_proposal_v1}

Here are proposals from other models:
=== Proposal from {model_B} ===
{proposal_B_v1}

Your tasks:
1. CRITIQUE each other proposal
2. REVISE your own proposal incorporating the best ideas
3. Be specific about what you changed and why
```

---

# 6. SCRIPTS `[AUDIT 2026-04-03]`

### Core pipeline (12)

| Script | Purpose |
|--------|---------|
| `litellm_stream.py` | Shared streaming LLM module — all scripts import this (L-33) |
| `spawn_planner_agent.py` | Spawns individual agents via streaming curl + context compression |
| `spawn_debate.py` | Multi-model debate with judge + optional red team (streaming) |
| `spawn_implementation_blocks.py` | Block-based implementation plan generation (fallback for C1) |
| `cost_estimator.py` | Deterministic cost calculator (no API, $0) |
| `validate_schema.py` | Validate artifacts against JSON schemas |
| `human_gate.py` | Interactive human gate handler |
| `generate_report.py` | Generate HTML narrative report |
| `build_fact_pack.py` | Build context pack for report review |
| `json_repair.py` | Attempt to fix malformed JSON from agents |
| `start_plan.sh` | Initialize new plan (creates run folder + manifest) |
| `start_plan_from_file.sh` | Init from file (for large idea descriptions) |

### Pipeline runners (4)

| Script | Purpose |
|--------|---------|
| `run_phase_a.sh` | Execute Fase A (Clarify): A1→A2→A3 |
| `run_phase_b.sh` | Execute Fase B (Design): B1→B2→B3(debate) |
| `run_phase_c.sh` | Execute Fase C (Buildability): C1→C2→C3 (block mode routing) |
| `run_full_plan.sh` | Full pipeline with interactive gates |

### Utility & rescue (8)

| Script | Purpose |
|--------|---------|
| `resume_plan.sh` | Show plan status / resume from last gate |
| `generate_contracts_atomic.py` | Generate contracts one at a time |
| `generate_contracts_by_domain.py` | Generate contracts grouped by domain |
| `generate_implementation_by_blocks.py` | Legacy block generator (hardcoded to strategy-runtime-1) |
| `continue_contracts_with_retries.py` | Resume contract generation with retries |
| `regenerate_one_contract.py` | Regenerate a single failed contract |
| `rerun_contracts_advanced.py` | Advanced contract regeneration |
| `rescue_implementation_plan.py` | Rescue a partially failed implementation plan |

**Total: 24 scripts** (12 core + 4 runners + 8 utility/rescue)

---

# 7. SCHEMAS — 9 JSON ARTIFACTS `[AUDIT]`

| # | Schema | What it captures |
|---|--------|-----------------|
| 00 | intake_summary | Structured summary of raw idea, clarification questions |
| 01 | gap_analysis | Missing info, blockers, readiness score 0-100 |
| 02 | scope_decision | MVP/Standard/Advanced with included/excluded features |
| 03 | data_flow_map | All artifacts: producer→file→consumer |
| 04 | contracts | JSON schemas for all data artifacts |
| 05 | architecture_decision | Winning architecture with debate evidence |
| 06 | implementation_plan | Phased build plan with tasks, tests, effort |
| 07 | cost_estimate | Per-phase and total cost breakdown |
| 08 | plan_review | Final validation against lessons learned |

Each artifact is validated against its schema by `validate_schema.py`. `[V3]`

---

# 8. CONFIGURATION `[AUDIT 2026-04-03]`

### planner_config.json

```json
{
    "version": "1.0.0",
    "debate": {
        "execution_mode": "sequential",
        "fallback_to_sequential": true,
        "rounds": 3,
        "timeout_per_model_seconds": 300,
        "subprocess_timeout_seconds": 350
    },
    "defaults": {
        "max_tokens_standard": 8192,
        "max_tokens_debate": 12288,
        "curl_max_time": 300,
        "subprocess_buffer": 50
    },
    "schema_validation": {
        "enabled": true,
        "fail_on_orphan_outputs": true,
        "fail_on_missing_consumer": true
    },
    "block_mode": {
        "implementation_planner": {
            "enabled": true,
            "max_tokens_per_block": 5000,
            "max_retries_per_block": 3,
            "fallback_model": "gemini31pro-none",
            "blocks": ["01_foundation", "02_core_components",
                       "03_orchestration_and_gates",
                       "04_entrypoints_and_integration",
                       "05_testing_and_validation"]
        }
    }
}
```

### models.json

All 8 core agents use `claude-sonnet46` via LiteLLM proxy (`http://127.0.0.1:4000`).

Debate models:
- **Simple:** claude-sonnet46
- **Complex:** claude-opus46 + chatgpt-gpt54 (judge: claude-sonnet46)
- **Critical:** claude-opus46 + chatgpt-gpt54 + gemini31pro-none (judge: claude-opus46, red team: claude-opus46)

Report generator: narrator=claude-sonnet46, reviewer=chatgpt-gpt54

---

# 9. TOKEN TRACKING `[AUDIT 2026-04-03]`

Real token tracking per artifact in manifest.json:
- `model`, `input_tokens`, `output_tokens`, `cost_usd` (calculated from real tokens)
- `debate_detail` with per-model breakdown
- `total_cost_usd` recalculated from all artifacts
- Block mode artifacts show `model: "{model}|by-blocks|{retries}"`

Pricing dict in spawn scripts (PRICING constant):

| Model | Input $/1M | Output $/1M | Notes |
|-------|-----------|------------|-------|
| claude-sonnet46 | $3.00 | $15.00 | Primary for all agents |
| claude-opus46 | $5.00 | $25.00 | Judge, red team, critical debates |
| chatgpt-gpt54 | $0.00 | $0.00 | OAuth subscription — $0 to planner |
| gemini31pro-none | $1.25 | $10.00 | Block fallback model |
| gemini31lite-none | $0.00 | $0.00 | Free tier |
| minimax-m27 | $0.30 | $1.20 | |
| kimi-k25 | $0.60 | $3.00 | |
| step35-flash | $0.10 | $0.30 | |

**NOTE:** GPT models are $0/token via OAuth subscription. Planner correctly reflects this.

---

# 10. COMPLETED RUNS `[AUDIT 2026-04-03]`

| Run | Type | Debate level | Total cost | Key result | Date |
|-----|------|-------------|-----------|------------|------|
| declassified-marketing | E2E test | Critical | $1.148 | Architecture for Marketing System (became real system) | 2026-03-25 |
| finance-test | E2E test | Simple | $0.577 | Finance tracker validation (12 gaps, score 38) | 2026-03-24 |
| marketing-workflow-1 | Production | ? | ? | 13 NEEDS_REVISION items | ~2026-03-26 |
| strategy-runtime-1 | Production | ? | ? | Completed, triggered Marketing System build | ~2026-03-28 |
| test-verification-upgrade | Verification | ? | ? | Used to verify streaming, compression, and block mode fixes | 2026-04-03 |

### Detailed cost breakdown: declassified-marketing `[EXT]`

```
Fase A: $0.147 (intake $0.016 + gap $0.074 + scope $0.057)
Fase B: $0.648 (data flow $0.046 + contracts $0.122 + debate $0.480)
  Debate: Opus $0.174 + GPT $0.073 + Gemini $0.043 + Judge $0.118 + Red Team $0.072
Fase C: $0.353 (implementation $0.162 + cost $0 + review $0.190)
TOTAL: $1.148
```

---

# 11. BOT & ACCESS `[VERIFIED]`

The planner has its OWN dedicated bot. It does NOT run through the CEO.

**Bot:** @Super_Workflow_Creator_bot
**Agent ID:** planner
**Workspace:** `~/.openclaw/workspace-meta-planner/`

### How to use

Send messages directly to @Super_Workflow_Creator_bot on Telegram:

```
Planifica: [tu idea aquí]
```

Or describe what you want naturally — the planner agent handles it.

### CEO routing (secondary — less reliable)

CEO bot (@Robotin1620_Bot) CAN route "Planifica:" prefixed messages to the planner, but direct access via @Super_Workflow_Creator_bot is preferred. M2.7 (CEO fallback) sometimes ignores routing (TL-16).

---

# 12. UPGRADE v3.1 — STATUS: IMPLEMENTED `[VERIFIED 2026-03-31]`

All 7 changes confirmed live by @Super_Workflow_Creator_bot:

| # | Change | Status |
|---|--------|--------|
| 1 | 3-round debate (propose → cross-critique → consolidate) | ✅ LIVE |
| 2 | Red Team attacks consolidated proposal | ✅ LIVE (critical/deep) |
| 3 | Iterative intake (up to 5 rounds × 3 questions) | ✅ LIVE (PATCH-1) |
| 4 | Real human gates (yes/no/adjust → re-run) | ✅ LIVE (PATCH-3) |
| 5 | Two analysis levels (regular vs deep) | ✅ LIVE |
| 6 | Report Generator (HTML narrative + GPT review) | ✅ LIVE |
| 7 | Updated scripts | ✅ LIVE |

Version tracking: `scripts/VERSION` file in workspace. `[VERIFIED]`

---

# 13. KEY DESIGN DECISIONS

| # | Decision | Why | Source |
|---|----------|-----|--------|
| 1 | Gap Finder BEFORE architecture | Unanimous across 4 models — analyze what's missing first | [EXT] P-01 |
| 2 | Data flow + contracts BEFORE architecture | Define what data moves before who moves it | [EXT] P-02 |
| 3 | Debate is conditional, not ritual | Simple ideas don't need 3-model debate — waste of money | [EXT] P-04 |
| 4 | Cost estimator = script, not LLM | Math is deterministic. Don't waste tokens | [EXT] P-05 |
| 5 | No symlinks — pinned copies for shared scripts | Symlinks create cross-workspace dependencies that break | [EXT] GPT fix |
| 6 | Model routing in config, not hardcoded | One file to update when models change | [EXT] P-07 |
| 7 | SKILL.md MUST include inline JSON schemas | Without them, models produce incompatible output (TL-13) | [EXT] |
| 8 | Sequential execution, not parallel | asyncio fails in WSL (TL-14). Sequential works fine for 3 models | [EXT] |
| 9 | Dedicated bot, not CEO as router | M2.7 ignores complex AGENTS.md routing (TL-16) | [EXT] |
| 10 | Cross-model review > single model | The planner itself was designed this way and produced better results | [EXT] |

### GPT's 7 principles (P-01 to P-07) `[EXT]`

These emerged from GPT's v1 review and became the planner's design philosophy:
- P-01: Gap Finder first
- P-02: Data flow before architecture
- P-03: Contracts before code
- P-04: Debate conditional, not ritual
- P-05: Cost estimator is script
- P-06: Human gates persist decisions
- P-07: Model routing in config

---

# 14. TECHNICAL LESSONS

| ID | Lesson | Impact |
|----|--------|--------|
| TL-13 | SKILL.md MUST include exact JSON schema inline with types | Critical — all planner skills needed this fix |
| TL-14 | asyncio parallel debate fails in WSL ("future belongs to different loop") | Sequential fallback works. WSL limitation |
| TL-15 | LiteLLM model names ≠ provider names (claude-sonnet46 not claude-sonnet-4-6) | Config — discovered during Phase 0 |
| TL-16 | M2.7 ignores complex AGENTS.md routing — not reliable for orchestration | Led to dedicated bot decision |
| PL-07 | Cross-critique produces better results than independent proposals | Basis for 3-round debate upgrade |
| PL-08 | Alternative paths diverge and the wrong one stays active | Avoid creating parallel paths that aren't integrated |
| PL-09 | Gate auto-approval hides quality issues | Basis for real human gates upgrade |

---

# 15. STREAMING, COMPRESSION & BLOCK MODE `[2026-04-03]`

These three features were added to fix Anthropic API disconnects on large completions (L-33).

### Streaming (`litellm_stream.py`)

All LLM calls use streaming via SSE (Server-Sent Events). The shared module `litellm_stream.py` is imported by all three spawn scripts.

```
Request: curl --data-binary @payload.json → proxy with stream:true
Response: SSE chunks → parsed line by line → accumulated into full content
Usage: Extracted from final chunk via stream_options.include_usage
```

- Never uses Python `requests` (TL-01)
- Returns `(content_str, {prompt_tokens, completion_tokens, total_tokens})`
- Handles non-streaming error responses (JSON error objects)

### Context compression (`compress_contracts()`, `compress_architecture()`)

When `implementation_planner` runs, `spawn_planner_agent.py` compresses upstream context:

| Artifact | Compression | What's stripped | Reduction |
|----------|-------------|-----------------|-----------|
| 04_contracts.json | `compress_contracts()` | Full JSON schemas, examples, format-level validation rules | ~67% |
| 05_architecture_decision.json | `compress_architecture()` | `red_team_findings`, `infrastructure_validation.notes` | Only if >30KB |

Compressed contracts output format:
```
### artifact_name
Format: json
Est. size: N tokens
Fields:
  - field_name: type (req) — description or structure summary
    Arrays show: array of [field1, field2, ...]
    Objects show: object: {sub1, sub2}
Key rules:
  - business-logic rules only (no pattern/regex/format rules)
```

Compressed output saved to `runs/<slug>/debug_contracts_compressed.txt` for audit.

### Block-based generation (`spawn_implementation_blocks.py`)

Configurable fallback for C1 (implementation_planner). When enabled in `planner_config.json`:

```
block_mode.implementation_planner.enabled: true
```

`run_phase_c.sh` routes C1 to `spawn_implementation_blocks.py` instead of `spawn_planner_agent.py`.

5 blocks, each with `max_tokens=5000`:
1. `01_foundation` — directory layout, config, preflight, validators
2. `02_core_components` — core scripts from architecture
3. `03_orchestration_and_gates` — runtime flow, gates, rollback
4. `04_entrypoints_and_integration` — CLI, external integrations, auth
5. `05_testing_and_validation` — tests, E2E, rollout, deferred_to_v2

Each block retries 3x with primary model, then 3x with `fallback_model` (gemini31pro-none). Intermediate blocks saved to `runs/<slug>/implementation_blocks/` for debugging.

Final artifact: merged `06_implementation_plan.json` with phases sorted by `phase_number`.

### Defense-in-depth summary

| Layer | Mechanism | When active |
|-------|-----------|-------------|
| Streaming | `litellm_stream.py` (SSE) | Always — all LLM calls |
| Context compression | `compress_contracts()` | Always — for implementation_planner |
| Architecture compression | `compress_architecture()` | When raw file > 30KB |
| LiteLLM timeout | `request_timeout: 600` in config.yaml | Always — server-side |
| Block-based generation | `spawn_implementation_blocks.py` | When `block_mode.enabled: true` |

See `docs/FIX_LITELLM_TIMEOUT.md` for full diagnosis and evidence.

---

# 16. KEY FILES `[AUDIT 2026-04-03]`
> (was §15 in v2.1)

```
~/.openclaw/workspace-meta-planner/
├── AGENTS.md                           — Planner orchestrator
├── MASTER_PLAN.md                      — Source of truth for design
├── planner_config.json                 — Debate settings, timeouts, block_mode
├── models.json                         — Model routing with pricing
├── system_configuration.md             — Infrastructure snapshot for agents
├── HEARTBEAT.md, IDENTITY.md, SOUL.md, TOOLS.md, USER.md
├── README.md
├── inputs/                             — Raw idea inputs
├── memory/                             — Daily notes
├── schemas/                            — 9 JSON schemas (00-08)
├── skills/                             — 14 skills (SKILL.md each)
│   ├── intake-analyst/
│   ├── gap-finder/
│   ├── scope-framer/
│   ├── data-flow-mapper/
│   ├── contract-designer/
│   ├── architecture-planner/
│   ├── implementation-planner/
│   ├── lessons-validator/
│   ├── capability-mapper/              — conditional
│   ├── compliance-reviewer/            — conditional
│   ├── creative-strategist/            — conditional
│   ├── landscape-researcher/           — conditional
│   ├── red-team/                       — conditional
│   └── report-generator/               — conditional
├── scripts/                            — 24 scripts
│   ├── litellm_stream.py              — Shared streaming module (all scripts)
│   ├── spawn_planner_agent.py         — Agent spawner + context compression
│   ├── spawn_debate.py                — Multi-model debate (streaming)
│   ├── spawn_implementation_blocks.py — Block-based C1 fallback
│   ├── cost_estimator.py              — Deterministic cost calculator
│   ├── validate_schema.py / human_gate.py / generate_report.py
│   ├── build_fact_pack.py / json_repair.py
│   ├── start_plan.sh / start_plan_from_file.sh
│   ├── run_phase_a.sh / run_phase_b.sh / run_phase_c.sh
│   ├── run_full_plan.sh / resume_plan.sh
│   └── [rescue/retry scripts: 8 utility scripts]
├── docs/
│   └── FIX_LITELLM_TIMEOUT.md         — Timeout diagnosis + fixes
└── runs/                               — Generated plans
    ├── declassified-marketing/         — $1.148
    ├── finance-test/                   — $0.577
    ├── marketing-workflow-1/           — NEEDS_REVISION
    ├── strategy-runtime-1/             — Completed
    └── test-verification-upgrade/      — Streaming/compression verification
```

---

# 17. CURRENT STATE `[AUDIT 2026-04-03]`

### Working ✅
- 14 skills deployed
- 24 scripts present (12 core + 4 runners + 8 utility)
- 9 JSON schemas for validation
- 5 runs (2 E2E test, 2 production, 1 verification)
- Real token tracking in manifest.json
- **3-round debate LIVE** (propose → cross-critique → consolidate)
- **Iterative intake LIVE** (5 rounds × 3 questions)
- **Human gates with adjust LIVE**
- **Two analysis levels LIVE** (regular vs deep)
- **Report generator LIVE**
- **Streaming LLM calls LIVE** — all scripts use `litellm_stream.py` (SSE parsing via curl)
- **Context compression LIVE** — `compress_contracts()` reduces ~67% tokens for implementation_planner
- **Block-based generation LIVE** — configurable via `block_mode` in planner_config.json
- Own bot: @Super_Workflow_Creator_bot

### Issues ⚠️
- **CEO AGENTS.md says Fases B+C "not implemented"** — INCORRECT, they are live. Need to update CEO.
- **MASTER_PLAN.md** is outdated — doesn't reflect streaming, compression, or block mode changes

### Resolved since last audit
- ~~GPT pricing overestimate~~ → Fixed: chatgpt-gpt54 now $0/$0 in PRICING dict (OAuth)
- ~~Anthropic API disconnects on large completions~~ → Fixed: streaming + context compression + block fallback
- ~~spawn_core.py sync~~ → No longer relevant; scripts use `litellm_stream.py` directly

---

# 18. PENDING ITEMS (prioritized)

| Priority | Item | Blocker | Est. effort |
|----------|------|---------|-------------|
| 🔴 | Update CEO AGENTS.md to reflect Fases B+C are LIVE | None | 15 min |
| 🟡 | Run a full Deep Analysis on a real new idea (post-upgrade test) | None | 2 hours |
| 🟡 | Update MASTER_PLAN.md with current v3.1+ state | None | 1 hour |
| 🟢 | Extend `block_mode` to other heavy agents (contract_designer) if needed | Only if timeouts recur | 30 min |
| 🟢 | Add `compress_architecture()` size threshold to planner_config.json | Nice-to-have | 15 min |

---

**END OF WORKFLOW BIBLE — META-WORKFLOW PLANNER**

*Consolidates: 1 extraction (2026-03-24/25), master_plan_v3 (966 lines), upgrade_plan_v3.1 (42K), 4 build phase prompts, review package, and Project Bible v2 §10. Verified against system audit 2026-03-29.*
