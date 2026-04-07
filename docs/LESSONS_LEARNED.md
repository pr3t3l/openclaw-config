# LESSONS_LEARNED.md — OpenClaw
<!--
SCOPE: ALL failures, fixes, anti-patterns, and operational incidents.
       Single canonical source. No other file contains lessons.
NOT HERE: Project vision → PROJECT_FOUNDATION.md
NOT HERE: Implementation details → docs/specs/
NOT HERE: Rules derived from lessons → CONSTITUTION.md §11 (references back here)

UPDATE FREQUENCY: Continuously. Every significant issue gets logged.

NAMESPACE: LL-[CATEGORY]-[XXX]
  PLAN  — Planning failures (wrong scope, missing requirements)
  ARCH  — Architecture decisions that were wrong
  COST  — Cost surprises and budget issues
  INFRA — Infrastructure, WSL, networking, deployment
  AI    — AI/LLM behavior, prompts, model issues
  DATA  — Database, schema, migration issues
  OPS   — Operational incidents and recovery
  PROC  — Process failures (workflow, git, docs)

TRIGGER POLICY (when to write a lesson):
  - Any bug that took >1 hour to fix
  - Any task that had to be redone
  - Any cost surprise (actual > 2x estimated)
  - Any architectural assumption that proved wrong
  - Any AI/model behavior that was unexpected

MIGRATION NOTE: Entries below were migrated from multiple sources
(L-01→L-33, TL-01→TL-41, PL-07→PL-09, LL-001→LL-019, LL-MTC-01→LL-MTC-04).
Old IDs are preserved in parentheses for cross-reference with archived docs.
Full evidence and context available in docs/archivo/lessons_learned-master.md.
-->

**Last updated:** 2026-04-07
**Total entries:** 82

---

## ID Mapping (old → new)

<!-- Use this to find lessons referenced in archived docs -->

| Old ID | New ID | Short title |
|--------|--------|-------------|
| L-01 | LL-PLAN-001 | Plan data flow before building agents |
| L-02 | LL-PLAN-002 | Define contracts between producer-consumer |
| L-03 | LL-PLAN-003 | Test one item E2E before batch |
| L-04 | LL-PLAN-004 | Don't build V2 until V1 produces value |
| L-05 | LL-PLAN-005 | Separate "does it work" from "is it good" |
| L-06 | LL-ARCH-006 | Test file I/O on day 1 |
| L-07 | LL-ARCH-007 | Direct API calls > agent spawning |
| L-08 | LL-ARCH-008 | One agent = one skill = one output |
| L-09 | LL-COST-009 | Track orchestrator cost |
| L-10 | LL-PLAN-010 | No stub outputs |
| L-11 | LL-ARCH-011 | Canonical asset libraries |
| L-12 | LL-ARCH-012 | Normalize identifiers |
| L-13 | LL-ARCH-013 | Cross-reference integrity |
| L-14 | LL-COST-014 | Cost telemetry mandatory |
| L-15 | LL-ARCH-015 | Cross-reference updates on conversion |
| L-16 | LL-PLAN-016 | Trojan horse pacing |
| L-17 | LL-PLAN-017 | Concrete specificity |
| L-18 | LL-PLAN-018 | Image coverage planning |
| L-19 | LL-ARCH-019 | Output path conventions |
| L-20 | LL-PLAN-020 | Self-contained specs |
| L-21 | LL-AI-021 | Tell model what NOT to do |
| L-22 | LL-ARCH-022 | Script vs agent decision |
| L-23 | LL-ARCH-023 | Validate structurally before quality check |
| L-24 | LL-COST-024 | Set budget alarm before starting |
| L-25 | LL-COST-025 | Track orchestrator costs separately |
| L-26 | LL-PROC-026 | Retry with diagnosis, never identical |
| L-27 | LL-AI-027 | Different models for different tasks |
| L-28 | LL-PROC-028 | Human gates with justification |
| L-29 | LL-PROC-029 | Save state after every phase |
| L-30 | LL-PROC-030 | Backup before overwriting |
| L-31 | LL-PROC-031 | Use Claude Code for edits, not chat |
| L-32 | LL-ARCH-032 | Multi-agent debates require structured output |
| L-33 | LL-ARCH-033 | Compress upstream context for heavy agents |
| TL-01 | LL-INFRA-001 | Python requests fails in WSL >30s |
| TL-02 | LL-COST-002 | POI portraits: JPEG q70 = 15x cheaper |
| TL-03 | LL-CODE-003 | None-safe access with .get() or 0 |
| TL-04 | LL-ARCH-004 | sessions_spawn cannot write files |
| TL-05 | LL-INFRA-005 | subprocess timeout > curl timeout |
| TL-06 | LL-INFRA-006 | wget not curl for DALL-E downloads |
| TL-07 | LL-INFRA-007 | MAX_TOKENS per doc type |
| TL-08 | LL-AI-008 | Never dark backgrounds in HTML |
| TL-09 | LL-INFRA-009 | Always mkdir -p before writing |
| TL-10 | LL-INFRA-010 | All file paths absolute |
| TL-11 | LL-INFRA-011 | OpenClaw doesn't resolve ENV vars |
| TL-12 | LL-INFRA-012 | LiteLLM dashboard: UI creds in litellm.env |
| TL-13 | LL-AI-013 | SKILL.md must include exact JSON schema |
| TL-14 | LL-INFRA-014 | asyncio parallel fails in WSL |
| TL-15 | LL-INFRA-015 | LiteLLM model names ≠ provider names |
| TL-16 | LL-AI-016 | M2.7 ignores complex AGENTS.md routing |
| TL-17 | LL-AI-017 | Sonnet truncates JSON above ~8K tokens |
| TL-18 | LL-DATA-018 | PostgreSQL GENERATED columns no TEXT cast |
| TL-19 | LL-DATA-019 | ON CONFLICT with GENERATED: use column name |
| TL-20 | LL-INFRA-020 | WSL auto-start: WSL.lnk + wsl.conf |
| TL-21 | LL-AI-021b | Veo 3 model names use -001 suffix |
| TL-22 | LL-PROC-022 | echo >> for .env creates duplicates |
| TL-23 | LL-INFRA-023 | isolatedSession needs gateway >=v2026.4 |
| TL-24 | LL-PROC-024 | CEO MEMORY.md must be workspace-specific |
| TL-25 | LL-COST-025b | sessions_spawn invisible for cost tracking |
| TL-27 | LL-INFRA-027 | $(cat file) fails >8KB in bash |
| TL-28 | LL-PROC-028b | Git identity config |
| TL-29 | LL-INFRA-029 | Google Sheets OAuth port 18900 |
| TL-30 | LL-INFRA-030 | Google Sheets needs both scopes |
| TL-31 | LL-PROC-031b | Lovable: Publish button, not git push |
| TL-32 | LL-PROC-032 | One Claude Code instance per repo |
| TL-33 | LL-INFRA-033 | LiteLLM Prisma duplicate model warning |
| TL-34 | LL-DATA-034 | verify_db_parity needs psycopg2 |
| TL-35 | LL-INFRA-035 | litellm.env: only API keys + UI creds |
| TL-36 | LL-INFRA-029 | (duplicate of TL-29) |
| TL-37 | LL-INFRA-030 | (duplicate of TL-30) |
| TL-38 | LL-CODE-038 | Receipt amounts: findall+max beats search |
| TL-39 | LL-CODE-039 | Chase CSV: payments are POSITIVE |
| TL-40 | LL-CODE-040 | Spanish payment keywords needed |
| TL-41 | LL-COST-041 | AI batch classification ~$0.01/50 merchants |
| PL-07 | LL-ARCH-PL07 | Cross-critique > independent proposals |
| PL-08 | LL-ARCH-PL08 | Alternative paths diverge without integration |
| PL-09 | LL-PROC-PL09 | Gate auto-approval hides quality issues |
| — | LL-INFRA-036 | command-dispatch:tool fails for Python wrapping |
| — | LL-INFRA-037 | OpenClaw LLM simulates instead of exec |
| — | LL-INFRA-038 | Skill hyphens → underscores in Telegram |
| — | LL-CODE-041 | StubHandler tests miss real schema errors |
| — | LL-ARCH-034 | additionalProperties:false vs transient data |
| — | LL-ARCH-035 | OpenClaw skills need ultra-strict SKILL.md |
| — | LL-AI-028 | Model audit benchmarks (GPT-5.4 vs Gemini) |
| — | LL-PROC-033 | 500+ tests need real integration test |

---

## PLAN — Planning Failures

| ID | Lesson | Evidence | Prevention Rule | Applies to |
|----|--------|----------|----------------|------------|
| LL-PLAN-001 | Plan data flow BEFORE building agents. Every artifact must have a consumer. | Experience Designer output was never consumed by renderer. | FAIL if orphan_outputs or missing_required_artifacts are non-empty. | both |
| LL-PLAN-002 | Define the contract (schema) between every producer-consumer pair BEFORE building. | Narrative Architect produced `usage_map` arrays, Art Director expected `for_doc` strings. Silent mismatch. | Contracts in spec §2 with JSON examples. | both |
| LL-PLAN-003 | Test ONE item end-to-end BEFORE batch. Never batch-run untested changes. | Applied 15 audit fixes, ran full case ($6+), renders still broken. Could have tested 1 doc for $0.10. | implementation-planner requires `test_minimum` per phase. | both |
| LL-PLAN-004 | Don't build V2 until V1 produces value. "Feo pero funcional" beats "bonito pero incompleto." | Multiple V2 rewrites before V1 was validated. | scope-framer never recommends Advanced as starting point. | both |
| LL-PLAN-005 | Separate "does it work?" from "is it good?" Never mix infra fixes with quality improvements. | Hours spent mixing pipeline plumbing with quality tuning. | Separate sessions for infra vs quality. | both |
| LL-PLAN-010 | No stub outputs. Never accept placeholder data. Validate ALL fields have real content. | clue_catalog had type_key='some_type', reveals='Reveals something about DOC-XX'. | Structural validator rejects any stub pattern. | both |
| LL-PLAN-016 | Trojan horse pacing: early-envelope hints must be ambiguous. Explicit reveal in later envelopes. | DoorDash receipt revealed key detail too early. | Product-specific but pattern applies: don't leak conclusions in early phases. | workflows |
| LL-PLAN-017 | Details must be concrete and verifiable, not vague. Reject anything that could apply to any project. | Interview slips were "remembers the timestamp perfectly" instead of specific states. | Reject generic descriptions in quality gate. | both |
| LL-PLAN-018 | Every document type that needs visual support must have image briefs planned. | Art Director only generated portraits for 18 docs. Digital evidence got zero images. | Image coverage checklist in spec. | workflows |
| LL-PLAN-020 | If an artifact is the complete spec for a downstream agent, it must be self-contained. | Visual instructions split across 2 files; renderer only read 1. | One spec file per consumer. | both |

---

## ARCH — Architecture Decisions

| ID | Lesson | Evidence | Prevention Rule | Applies to |
|----|--------|----------|----------------|------------|
| LL-ARCH-004 | `sessions_spawn` cannot write files. Use spawn scripts with direct file I/O. | Sub-agents completed with "(no output)" and 0 tokens. Confirmed broken 6+ times. | All AGENTS.md entries say "NEVER use sessions_spawn for file writing." | workflows |
| LL-ARCH-006 | Test file I/O on day 1. Before complex logic, verify spawn method reads/writes correctly. | sessions_spawn file writing failure discovered after 6 attempts. | Phase 1 of any implementation always tests I/O. | both |
| LL-ARCH-007 | Direct API calls > agent spawning for deterministic tasks. Use agents for orchestration, direct calls for generation. | spawn_agent.py (direct curl) replaced sessions_spawn. More reliable, exact cost tracking. | Script for deterministic, agent for judgment. | workflows |
| LL-ARCH-008 | One agent = one skill = one output type. Split large outputs into separate calls. | Narrative Architect asked to produce both case-plan AND clue_catalog — catalog truncated. | Max one output artifact per agent call. | workflows |
| LL-ARCH-011 | Canonical asset libraries: one version of shared assets, reuse it. Don't regenerate. | Art briefs requested separate mugshots for same POI across docs. | Define canonical assets in spec, reference by ID. | both |
| LL-ARCH-012 | Normalize identifiers across all artifacts. Don't let phases use different naming. | Same entity had different names in different phases. | Identifier registry in spec. | both |
| LL-ARCH-013 | Cross-reference integrity: when changing a doc, update ALL references. | Type conversion left stale cross-references. | Validator checks all references resolve. | both |
| LL-ARCH-015 | Any doc type conversion requires updating ALL dependent references. | Converting evidence_mosaic → interrogation_transcript left stale refs. | Same as LL-ARCH-013 but specific to type changes. | workflows |
| LL-ARCH-019 | Define output paths BEFORE building. Intermediate vs final must be explicit. | Render output went to layout_specs/ but validators expected envelope_X/. | Output paths in spec §2 contracts. | both |
| LL-ARCH-022 | If logic is deterministic (no LLM needed), use a script, not an agent. | 20-line Python did image injection perfectly; LLM prompt engineering failed for hours. | Decision matrix: deterministic=script, judgment=agent. | both |
| LL-ARCH-023 | Validate outputs structurally BEFORE quality-checking. Structural first, LLM QA second. | QA agent spent tokens analyzing structurally broken data. | Structural validators are phase prerequisites. | both |
| LL-ARCH-032 | Multi-agent debates: define JSON schema for "proposal", each model fills it, judge compares. | Unstructured debates produced incomparable outputs. | spawn_debate.py uses JSON schema for all rounds. | workflows |
| LL-ARCH-033 | Compress upstream context for heavy agents. Only include fields relevant to the agent's task. | Full contracts passed to implementation planner caused timeouts. 67% reduction via compress_contracts(). | Compress function + block_mode fallback. | workflows |
| LL-ARCH-PL07 | Cross-critique produces better results than independent proposals. | Basis for 3-round debate design. | Use debate pattern for architecture decisions. | workflows |
| LL-ARCH-PL08 | Alternative paths diverge without integration. Avoid parallel paths that aren't merged. | Planner produced divergent proposals that were never reconciled. | Single proposal → critique → revision. | workflows |
| LL-ARCH-034 | `planner_state.json` schema has `additionalProperties: false` — transient data (`_intake_answers`, `_draft_content`, `_audit_result`, etc.) must go to files in `planner_runs/{run_id}/`, NOT in the state dict. The Dispatcher pops `_gate_pending` before save, but all other transient fields cause schema validation errors. | Transient data → files in run dir. State dict = schema fields only. | Schema validation catches at save time, not at runtime. | both |
| LL-ARCH-035 | OpenClaw skills use normal mode (not `command-dispatch: tool`). The SKILL.md must have ultra-strict instructions: "MUST execute via exec tool", "Do NOT read Python files", "Do NOT simulate". Even with these instructions, `/reset` before invocation is required to prevent LLM from reading and simulating the Python code. | Ultra-strict SKILL.md + `/reset` before invocation. | Tested April 2026 with Planner integration. | both |

---

## COST — Cost Surprises

| ID | Lesson | Evidence | Prevention Rule | Applies to |
|----|--------|----------|----------------|------------|
| LL-COST-002 | POI portraits: 100px JPEG q70 = $0.004/image (15x cheaper than 200px PNG). | Cost comparison during image optimization. | Use cheapest format that meets quality. | workflows |
| LL-COST-009 | Orchestrator itself consumes tokens. Account for ~10% overhead in estimates. | Tracked $2.42 direct but actual bill was $5+. | cost_estimator.py includes orchestrator_overhead field. | workflows |
| LL-COST-014 | Track token usage and cost per API call. FAIL if pipeline shows zero cost (missing telemetry). | manifest.json cost_tracking remained zero despite completed pipeline. | Cost logging mandatory in every spawn script. | both |
| LL-COST-024 | Set budget alarm BEFORE starting. Check actual spend every 30 minutes during dev. | Discovered $37+ spent only by checking billing dashboard hours later. | Budget alert in CONSTITUTION §6. | both |
| LL-COST-025 | Two cost buckets: (1) direct API = manifest.json, (2) orchestrator = LiteLLM /spend. | manifest tracked $2.42, actual was $5+. | Track both, report both. | workflows |
| LL-COST-025b | sessions_spawn phases are invisible for cost tracking. | Phases 2-7 cost untracked when using sessions_spawn. | Use spawn scripts with explicit cost logging. | workflows |
| LL-COST-041 | AI batch classification ~$0.01/50 merchants — always cheaper than defaulting to "Other." | Finance tracker merchant categorization. | Use AI for classification when rule-based fails. | both |

---

## INFRA — Infrastructure

| ID | Lesson | Prevention Rule |
|----|--------|----------------|
| LL-INFRA-001 | Python `requests` FAILS in WSL for long API calls (>30s). Use streaming curl via subprocess. All scripts use `litellm_stream.py`. | Always streaming. See CONSTITUTION §4. |
| LL-INFRA-005 | subprocess timeout MUST exceed curl --max-time. Buffer: subprocess_buffer (50s). | timeout = curl_max_time + 50s. |
| LL-INFRA-006 | Use wget not curl for DALL-E image downloads (special chars in URLs). | wget for image downloads. |
| LL-INFRA-007 | MAX_TOKENS: 32000 visual docs, 16384 text docs, 8192 standard, 5000 per block. | Set per doc type, never default. |
| LL-INFRA-009 | Always `mkdir -p` target directories before writing files. | In every script preamble. |
| LL-INFRA-010 | ALL file paths must be absolute. Include WORKSPACE_ROOT in every spawn preamble. | No relative paths in agents. |
| LL-INFRA-011 | OpenClaw doesn't resolve ${ENV_VARS} in apiKey — hardcode or skip master_key. | Don't use env vars in OpenClaw config. |
| LL-INFRA-012 | LiteLLM dashboard: UI_USERNAME/UI_PASSWORD in litellm.env (not master_key). | Separate UI creds from API auth. |
| LL-INFRA-014 | asyncio parallel debate fails in WSL ("future belongs to different loop"). Sequential fallback works. | Sequential execution in WSL. |
| LL-INFRA-015 | LiteLLM model names ≠ provider names (e.g., `claude-sonnet46` not `claude-sonnet-4-6`). | Check LiteLLM config for exact names. |
| LL-INFRA-020 | WSL auto-start: WSL.lnk in shell:startup + wsl.conf boot hook (NOT .bat keepalive). | start_all_services.sh pattern. |
| LL-INFRA-023 | isolatedSession + lightContext need gateway >=v2026.4 — not available yet. | Don't use these features until gateway upgrade. |
| LL-INFRA-027 | `$(cat file.md)` in bash fails >~8KB — use file-based wrapper. | Pass files by path, not by content injection. |
| LL-INFRA-029 | Google Sheets OAuth: use run_local_server(port=18900, open_browser=False) in WSL. | Port 18900, no browser. |
| LL-INFRA-030 | Google Sheets needs BOTH spreadsheets AND drive scopes. | Both scopes always. |
| LL-INFRA-033 | LiteLLM Prisma: duplicate model LiteLLM_DeletedTeamTable — warning, not blocking. | Ignore this warning. |
| LL-INFRA-035 | litellm.env: only API keys + UI creds. Extra vars (TELEGRAM_*, GATEWAY_*) crash LiteLLM. | Keep litellm.env minimal. |
| LL-INFRA-036 | OpenClaw `command-dispatch: tool` does NOT work for Python script wrapping. The `exec` tool receives raw args as a shell command — you cannot prefix `python3 /path/to/script.py` or any command. Tested and confirmed April 2026. | Use normal skill mode with strict exec instructions instead. |
| LL-INFRA-037 | OpenClaw LLM reads Python files in workspace and simulates the workflow instead of executing via exec tool. Workaround: `/reset` before skill invocation clears LLM context and forces exec execution. This is fragile — any prior conversation in the session can cause the LLM to bypass exec and simulate. | `/reset` before every skill invocation session. |
| LL-INFRA-038 | OpenClaw skill names with hyphens become underscores in Telegram commands (`sdd-planner` dir → `/sdd_planner` command). The skill directory name determines the command, not the `command:` field in SKILL.md frontmatter. | Name skill directories with the Telegram command in mind. |

---

## AI — Model Behavior

| ID | Lesson | Prevention Rule |
|----|--------|----------------|
| LL-AI-008 | NEVER dark backgrounds in rendered HTML — documents are printed on paper. | Negative instruction in every render prompt. |
| LL-AI-013 | SKILL.md MUST include exact JSON schema inline with types. Without them, models produce incompatible output. | Schema examples mandatory in skills. |
| LL-AI-016 | M2.7 ignores complex AGENTS.md routing — not reliable for orchestration. Led to dedicated bot. | Don't use M2.7 for multi-step routing. |
| LL-AI-017 | Sonnet truncates JSON above ~8K tokens. Generate by blocks. | Block mode for large structured output. |
| LL-AI-021 | Tell the model what NOT to do. Negative instructions prevent common failures. | Include "NEVER" rules in prompts. |
| LL-AI-021b | Veo 3 model names use -001 suffix, not -preview. | Check exact model identifiers. |
| LL-AI-027 | Different models for different tasks. Expensive for creative, cheap for formatting. | Model selection table in spec §4. |
| LL-AI-028 | Model audit benchmarks (March 2026): GPT-5.4 is aggressive auditor (20+ findings, 15K chars per audit). Gemini 3.1 Pro is precise architect (7-8 findings, 3K chars, cheapest at $2/$12/M tokens). Audit pattern: 4 sequential calls (GPT tech + arch, Gemini tech + arch) with 5-10s jittered backoff. Todo CLI test run: $0.61 total for 7 docs + plan + 21 tasks. | Use 4-call audit pattern with model-appropriate expectations. |

### Model Notes

| Model | Behavior | Source |
|-------|----------|--------|
| gemini31pro-thinking | Hits rate limits after ~15 spawns in 2 hours | Operational |
| gpt52-thinking | Reliable fallback for QA and narrative tasks | Operational |
| nano-banana-2-gemini | Needs exponential backoff (2s, 5s, 10s) for RESOURCE_EXHAUSTED | Operational |
| M2.7 | Not reliable for multi-step routing (ignores complex AGENTS.md) | LL-AI-016 |
| Claude Sonnet | Truncates JSON above ~8K tokens | LL-AI-017 |
| GPT-5.4 | Aggressive auditor: 20+ findings, 15K chars per audit call | LL-AI-028 |
| Gemini 3.1 Pro | Precise architect: 7-8 findings, 3K chars, cheapest ($2/$12/M tokens) | LL-AI-028 |

---

## CODE — Code-Level

| ID | Lesson | Prevention Rule |
|----|--------|----------------|
| LL-CODE-003 | cost_tracker.py: always use `(totals.get('field') or 0)` for None-safe access. | Default-safe access patterns. |
| LL-CODE-038 | Receipt amounts: re.findall + max() beats re.search (first match). | Use findall for numeric extraction. |
| LL-CODE-039 | Credit card payments are POSITIVE in Chase CSV — check payment keywords before sign split. | Validate sign logic per bank format. |
| LL-CODE-040 | Spanish payment keywords needed in classifier (SU PAGO, PAGO AUTOMATICO). | i18n in financial classifiers. |
| LL-CODE-041 | Claude Code builds modules with StubHandler unit tests that all pass, but real PhaseHandlers were never integration-tested through the Dispatcher with schema validation. Result: `_intake_answers` field caused schema validation crash at runtime that 573 unit tests missed. | Always require at least 1 integration test that runs real handlers through the full dispatcher loop with `state_manager.save()` and schema validation. |

---

## DATA — Database

| ID | Lesson | Prevention Rule |
|----|--------|----------------|
| LL-DATA-018 | PostgreSQL GENERATED columns can't use ::TEXT casts — use IMMUTABLE functions. | Use IMMUTABLE functions for generated cols. |
| LL-DATA-019 | ON CONFLICT with GENERATED columns: use column_name not expression. | Column name, not expression in ON CONFLICT. |
| LL-DATA-034 | verify_db_parity.py needs psycopg2 installed in the venv that runs it. | pip install psycopg2-binary in target venv. |

---

## PROC — Process

| ID | Lesson | Prevention Rule |
|----|--------|----------------|
| LL-PROC-022 | `echo >>` for .env files creates duplicates — edit with nano instead. | Never append to .env with echo. |
| LL-PROC-024 | CEO MEMORY.md must be CEO-specific — never copy from Declassified workspace. | Workspace-specific memory files. |
| LL-PROC-026 | Never retry with identical parameters. Always include failure diagnosis. Max 2 retries. | Diagnosis in retry prompt. See CONSTITUTION §5. |
| LL-PROC-028 | Every human gate must have clear justification for why automation is too risky. | human_gate.justification required. |
| LL-PROC-028b | Git identity: Alfredo Pretel, 30666965+pr3t3l@users.noreply.github.com. | Set git config before first commit. |
| LL-PROC-029 | Every script must update manifest on completion AND on failure. | Manifest update in finally block. |
| LL-PROC-030 | Always backup before regenerating content. Compare before discarding. | Backup step before overwrite. |
| LL-PROC-031 | For file modifications, use Claude Code directly. Chat is for planning, not execution. | Code for edits, chat for planning. |
| LL-PROC-031b | Lovable Publish after Code edits: git push doesn't deploy — Publish button required. | Use Publish button, not git push. |
| LL-PROC-032 | One Claude Code instance per repo — two on same repo causes git conflicts. | One instance per repo. |
| LL-PROC-PL09 | Gate auto-approval hides quality issues. Human gates exist for a reason. | Real human review at gates. |
| LL-PROC-033 | When Claude Code builds a system with 500+ tests, verify that at least some tests exercise the REAL integration path (real handlers → real dispatcher → real schema validation). A "Full Audit Policy" should be added to every build: after Code finishes all tasks, run one real integration test that flows through the actual system, not mocks. | Add integration test requirement to every build checklist. |

---

## Anti-Patterns

### Content & Quality
- ❌ Never accept `some_type` as type_key — always exact identifiers (LL-PLAN-010)
- ❌ Never accept generic descriptions ("Reveals something about X") — require specifics (LL-PLAN-017)
- ❌ Never count template/form labels toward content quality minimums
- ❌ Never include HTML tags in Markdown files
- ❌ Never hardcode case-specific data in templates — content comes from JSON/config

### Operations
- ❌ Never retry with identical parameters (LL-PROC-026)
- ❌ Never batch-run untested changes (LL-PLAN-003)
- ❌ Never use Python `requests` in WSL for API calls (LL-INFRA-001)
- ❌ Never use `sessions_spawn` to write files (LL-ARCH-004)
- ❌ Never use relative paths in agent prompts (LL-INFRA-010)
- ❌ Never use `echo >>` for .env files (LL-PROC-022)

### Architecture
- ❌ Never pass full upstream JSON to downstream agents (LL-ARCH-033)
- ❌ Never build V2 until V1 produces value (LL-PLAN-004)
- ❌ Never mix infra fixes with quality improvements (LL-PLAN-005)
- ❌ Never split specs across multiple files for one consumer (LL-PLAN-020)
- ❌ Normalize all identifiers consistently across phases (LL-ARCH-012)
- ❌ Never put transient data in state dicts with `additionalProperties: false` — use files (LL-ARCH-034)
- ❌ Never use `command-dispatch: tool` for Python script wrapping in OpenClaw (LL-INFRA-036)
- ❌ Never trust 500+ unit tests without at least 1 integration test through the real system (LL-CODE-041, LL-PROC-033)

### Documentation
- ❌ Never copy content between docs — reference with "See [DOC §section]"
- ❌ Never start an AI chat by re-explaining the project — load existing docs
- ❌ Never put API keys in documentation files

---

## Pre-Flight Checklist (Master)

Run this before starting ANY new module or workflow build.

### Planning
- [ ] Spec complete and approved (See README.md §Process)
- [ ] Data flow clear: every input has a source, every output has a consumer (LL-PLAN-001)
- [ ] Schemas defined for all inter-agent files (LL-PLAN-002)
- [ ] Budget set with monitoring plan (LL-COST-024)
- [ ] V1 scope defined — minimum viable output (LL-PLAN-004)
- [ ] Edge cases / failure modes documented (spec §5 or §7)
- [ ] Human gates identified and justified (LL-PROC-028)

### Architecture
- [ ] File I/O confirmed working (trivial test) (LL-ARCH-006)
- [ ] Direct API vs agent spawn decided per task type (LL-ARCH-007)
- [ ] Model selection per task complexity documented (LL-AI-027)
- [ ] Cost tracking built into every script from day 1 (LL-COST-014)
- [ ] All file paths use absolute paths (LL-INFRA-010)

### Development
- [ ] Single-item E2E test passes before batch (LL-PLAN-003)
- [ ] Infrastructure fixes separated from quality improvements (LL-PLAN-005)
- [ ] Deterministic tasks use scripts, not LLMs (LL-ARCH-022)
- [ ] Structural validators run before LLM quality checks (LL-ARCH-023)
- [ ] Backups created before content regeneration (LL-PROC-030)
- [ ] Large outputs split into blocks if >8K tokens (LL-ARCH-008, LL-AI-017)

### Operations
- [ ] Max 2 retries before diagnosis (LL-PROC-026)
- [ ] Both direct and orchestrator costs tracked (LL-COST-025)
- [ ] Manifest updated on every phase completion/failure (LL-PROC-029)
- [ ] Context compressed for heavy downstream agents (LL-ARCH-033)
- [ ] Streaming curl used for all API calls in WSL (LL-INFRA-001)
- [ ] At least 1 integration test through real dispatcher + schema validation (LL-CODE-041, LL-PROC-033)
- [ ] Transient data stored in files, not state dicts with strict schema (LL-ARCH-034)

---

## Escalation Chains

### Pattern: Large AI Output Failure
```
1. Monolithic generation fails → split by domain/section
2. Domain-split fails → identify failing block, retry only that block
3. Per-block still fails → compact mode (schema + required + rules only)
4. JSON parse failure → auto-repair before declaring failure
5. Auto-retry up to 2 times before surfacing to human
RULE: Always save raw model output on failure before retrying
```

### Pattern: LiteLLM Server Disconnect
```
1. Verify with small max_tokens (500) — if works, issue is generation time
2. Add request_timeout: 600 to LiteLLM config
3. Switch to streaming via litellm_stream.py
4. Compress input context via compress_contracts()
5. If still fails: block-based generation via spawn_implementation_blocks.py
```

---

## Template for New Entries

```markdown
### LL-[CAT]-[XXX]: [Short title]
- **Date:** YYYY-MM-DD
- **Severity:** 🔴 Critical / 🟡 Moderate / 🟢 Minor
- **Problem:** [What went wrong]
- **Evidence:** [Logs, cost, time lost, error message]
- **Root Cause:** [Why it happened]
- **Fix:** [What resolved it]
- **Prevention Rule:** [One sentence — the lesson]
- **Enforced by:** [Script, validator, process — NOT "manual discipline"]
- **Time/Cost Lost:** [e.g., "~4 hours + $12"]
- **Applies to:** apps / workflows / both
- **Verified:** ⬜ Not yet / ✅ YYYY-MM-DD
```
