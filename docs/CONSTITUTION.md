# CONSTITUTION.md — OpenClaw
<!--
SCOPE: Immutable rules, principles, constraints, forbidden patterns.
       These apply to EVERY workflow, module, and AI agent in the project.
NOT HERE: Project vision/roadmap → PROJECT_FOUNDATION.md
NOT HERE: Module/workflow specs → docs/specs/[name]/spec.md
NOT HERE: Database schemas → DATA_MODEL.md
NOT HERE: API details → INTEGRATIONS.md
NOT HERE: Failures/fixes → LESSONS_LEARNED.md

UPDATE FREQUENCY: Rarely. Only when a fundamental rule changes.
-->

**Last updated:** 2026-04-04

---

## 1. Product Principles

1. **Quality is gate, budget is alert.** If an output doesn't pass its quality gate, it does NOT advance — regardless of cost. If cost exceeds threshold, the system alerts but does not auto-stop. The human decides. Exception: hard stop at $75/week as emergency ceiling.

2. **Human-readable at every phase.** Every phase of a workflow must produce a report the operator can read in under 2 minutes. This does NOT mean "no JSON" — it means every JSON that crosses a phase boundary must have a human-readable summary alongside it.

3. **Modular agents, minimal payloads.** Each agent handles one responsibility. The data passed between agents must contain ONLY what the next agent needs — no upstream baggage. If an inter-agent payload exceeds ~4,000 tokens, justify why.

4. **Auditable by default.** For every agent execution: input, output, model used, cost, and duration must be logged. The operator must be able to reconstruct what happened in any run without reading code.

5. **Cost is tracked, never guessed.** Every API call logs: model, tokens in/out, estimated USD, duration. Costs aggregate at three levels: per-agent, per-run, per-workflow. Orchestrator overhead is tracked separately (it is never zero).

---

## 2. Definitions

These terms have exact meanings in this project:

| Term | Definition |
|------|-----------|
| **Workflow** | A complete pipeline with defined input, phases, and output (e.g., Declassified Pipeline, Marketing System) |
| **Phase** | One step in a workflow executed by one agent. Has defined input, output, and gate criteria. A phase boundary is where human audit is possible. |
| **Agent** | A specialized AI executor for one phase. One agent = one responsibility = one output type. |
| **Run** | One complete execution of a workflow from start to finish. Has a unique run_id. |
| **Gate** | A checkpoint between phases. Output must meet gate criteria to advance. |
| **Spec** | A MODULE_SPEC.md or WORKFLOW_SPEC.md document that defines what to build. |

---

## 3. Architecture Rules

1. **Workflows are product-agnostic.** Pipeline, Marketing, Planner, Finance are generic systems that accept configuration via inputs. Product-specific logic (Declassified, Finance categories) lives in config, not in workflow code.

2. **One agent, one phase, one output.** Do not ask an agent to produce multiple artifact types. If output exceeds model context limits, split into sub-phases.

3. **Contracts before agents.** Define the input/output schema between every producer-consumer pair BEFORE building the agent. See WORKFLOW_SPEC.md §2.

4. **Inter-agent data: quality over quantity.** Only pass fields the downstream agent actually uses. Compress upstream context for heavy agents. If you're passing a full JSON "just in case," you're doing it wrong. See LL-ARCH-033.

5. **State persistence after every phase.** Every script must update the run manifest on completion AND on failure. Include: phase name, status, timestamp, cost, output location. This enables resume from any phase.

6. **Platform choice is per-workflow, declared at spec time.** Each workflow spec declares its execution platform (OpenClaw / n8n / scripts). This is set once per workflow, not per run. Platform-specific best practices are referenced in the spec, not in this constitution.

---

## 4. Environment & Infrastructure

### Current Runtime (tactical — may change)

| Item | Value |
|------|-------|
| OS | WSL Ubuntu on Windows |
| Username | robotin (WSL) / robot (Windows) |
| Home | /home/robotin/ |
| Project root | ~/.openclaw/ |
| Orchestration | OpenClaw Gateway (:18789) |
| Model proxy | LiteLLM (:4000) |
| Database | PostgreSQL 16 (:5432) |
| Interface | Telegram Bots (3) |
| Remote access | Tailscale + SSH + tmux |

### Infrastructure Rules (apply regardless of runtime)

1. **Long API calls must use streaming.** In the current WSL environment, Python `requests` fails for calls >30s. Use streaming (SSE) via subprocess or `litellm_stream.py`. This is a tactical workaround — if the root cause is resolved, this rule can be retired. See LL-INFRA-001.

2. **All API calls route through LiteLLM proxy.** Exception: direct Anthropic API for rendering (Phase 8 in Pipeline). LiteLLM is a hard dependency — if it's down, no workflow runs. Recovery: `bash ~/.openclaw/start_all_services.sh`.

3. **API keys live in .env files ONLY.** Master: `~/.openclaw/.env`. LiteLLM: `~/.config/litellm/litellm.env`. NEVER in docs, code, or chat logs.

4. **Telegram bot isolation.** Each bot handles one domain. CEO (Robotin): personal assistant, finance, system admin. Declassified: case pipeline. Planner: workflow planning. Auth: allowFrom.json ACL per bot.

---

## 5. Execution Rules

### Concurrency
- **Max concurrent workflows: 2.** WSL on a laptop cannot handle more. If a third is requested, it queues.
- **No hot-patching.** Never modify a workflow while a run is active. Finish or abort first.

### Retry Policy
- Max 2 retries per agent failure, with diagnosis included in retry prompt.
- Never retry with identical parameters. See LL-PROC-026.
- After 2 failures: STOP, save partial output, alert human.

### Checkpoints & Resume
- Run manifest (manifest.json or equivalent) updated after every phase.
- If a workflow fails at Phase N, it must be resumable from Phase N without re-running Phases 1 to N-1.
- Intermediate outputs saved per-phase in `phase_N/` or equivalent directory.

### Heartbeat (Telegram UX)
- For any agent execution >30 seconds, send a progress message to Telegram: "[Agent Name] is processing... (est. X seconds)"
- On completion: send summary with cost and duration.
- On failure: send error description with phase and suggested action.

---

## 6. Cost Guardrails

### Tracking

| Level | What's tracked |
|-------|---------------|
| Per-agent | Model, tokens in/out, estimated USD, duration |
| Per-run | Sum of all agents + orchestrator overhead |
| Per-workflow | Aggregate of all runs over time |

### Budgets

| Budget | Threshold | Action |
|--------|-----------|--------|
| Per-run (production) | $10 target | Alert if exceeded, human decides |
| Weekly (all activity) | $50 | Alert via Telegram |
| Weekly (emergency) | $75 | Hard stop — no API calls until human approves |
| Development | No fixed limit | Track and report, but don't block |

### Cost Attribution
- Orchestrator tokens (routing, decisions) are tracked separately — they are never zero.
- When LiteLLM does retries or fallbacks, the total cost of all attempts is attributed to the phase that triggered them.
- Shared infrastructure costs (LiteLLM, PostgreSQL) are not prorated per workflow — they are overhead.

---

## 7. Quality & Validation

### Development & Testing: Full Audit Policy

During development and testing phases, EVERY artifact is audited — no exceptions, no shortcuts, no sampling:

- Every schema → validated against the spec
- Every JSON output → verified for completeness, no stubs, no placeholders
- Every .py and .sh → reviewed for correctness and documented purpose
- Every agent input/output pair → compared against plan expectations
- Every phase completion → audited: "Did it produce EXACTLY what the spec said?"
- Every phase completion → analyzed: "How can this be improved?"

This applies even when it is slower and more expensive. The cost of finding problems in development is 10x cheaper than finding them in production runs.

This policy relaxes ONLY in production, where auto-pass gates handle structural validation and human review is reserved for critical gates.

Rule: If ANY output contains "TBD", "placeholder", "some_type", "example_value", "TODO", or generic descriptions like "Reveals something about X" — the gate FAILS immediately. There is no "fix it later." See LL-PLAN-010.

### Validation Layers (in order)

1. **Structural validation first** — deterministic checks (schema, required fields, file existence). Cheap, fast. Run BEFORE any LLM quality check. See LL-ARCH-023.
2. **Semantic validation second** — LLM-as-judge or cross-model review for content quality. Only for critical phases. See LL-ARCH-010.
3. **Human review last** — for gates that require judgment the system can't make.

### Gate Types

| Gate Type | When to use | Who decides |
|-----------|------------|-------------|
| Auto-pass | Structural validation only (schema valid, files exist) | Script |
| Auto-pass + flag | Structural passes but quality score is borderline | Script alerts, human can override |
| Human-required | Decisions that change outcomes, publishing, spending >$X | Human explicitly approves |

---

## 8. Data & Retention

### What's stored permanently
- Run metadata: run_id, workflow, status, total cost, timestamps, quality score
- Cost records: per-agent breakdown per run
- Lessons learned: all LL entries

### What's stored temporarily (14 days default)
- Full agent I/O (input prompts, raw outputs)
- Intermediate files (phase_N/ directories)
- Detailed logs

### What's never stored
- API keys or credentials in any log or output
- Full Telegram chat history (Telegram retains its own)

### Versioning for Reproducibility
Each run records:
- Git commit hash of the workflow code
- Prompt version ID (if prompts are versioned files)
- Model name and provider used per agent
- LiteLLM config snapshot (which models were available)

---

## 9. Documentation Rules

1. **Every doc must be in PROJECT_FOUNDATION.md §Doc Registry.** If it's not registered, it doesn't exist.
2. **Reference, never copy.** Use "See [DOC.md §section]" format.
3. **One concept, one canonical location.** Two docs covering the same topic = merge and delete one.
4. **No code in docs.** Docs describe intent. Code lives in src/.
5. **No API keys in docs.** Ever.
6. **Every .py and .sh must have a docstring or header comment** explaining: purpose, inputs, outputs, and which workflow/phase it belongs to.
7. **JSON artifacts that cross phase boundaries** must include a `_summary` field or companion `_summary.txt` with human-readable description of contents.

### Document Precedence (when sources conflict)

```
CONSTITUTION.md (this file)
  ↓ overrides
PROJECT_FOUNDATION.md
  ↓ overrides
docs/specs/[workflow]/spec.md
  ↓ overrides
Code comments and inline docs
  ↓ overrides
Chat history or session notes (lowest authority)
```

### When to Write a Lesson Learned
- Any bug that took >1 hour to fix
- Any task that had to be redone
- Any cost surprise (actual > 2x estimated)
- Any architectural assumption that proved wrong
- Any AI/model behavior that was unexpected

---

## 10. Emergency Controls

### Kill Switches
- **Stop all workflows:** `pkill -f spawn_agent && pkill -f litellm` (nuclear option)
- **Stop one bot:** kill the specific Telegram bot process
- **Stop API spending:** revoke or rotate the active API key in `.env`
- **Stop LiteLLM:** `curl -X POST http://127.0.0.1:4000/shutdown` or kill process

### When to Pull the Emergency Brake
- Cost exceeds $75/week (auto-triggered)
- A workflow produces output that could be published/sent without human review
- Any sign of prompt injection or unexpected command execution

---

## 11. Forbidden Patterns

See LESSONS_LEARNED.md for full context on each.

### Operations
- ❌ Never retry with identical parameters — always include failure diagnosis (LL-PROC-026)
- ❌ Never batch-run untested changes — test ONE item E2E first (LL-PLAN-003)
- ❌ Never use Python `requests` for long API calls in WSL — use streaming (LL-INFRA-001)
- ❌ Never use `sessions_spawn` for file writing — use direct file I/O scripts (LL-ARCH-004)
- ❌ Never accept stub/placeholder data in outputs (LL-PLAN-010)

### Architecture
- ❌ Never pass full upstream JSON to downstream agents — compress to what's needed (LL-ARCH-033)
- ❌ Never build V2 until V1 produces value (LL-PLAN-004)
- ❌ Never mix infrastructure fixes with quality improvements in the same session (LL-PLAN-005)

### Documentation
- ❌ Never copy content between docs — reference with "See [DOC §section]"
- ❌ Never start an AI chat by re-explaining the project — load existing docs as context
- ❌ Never put API keys in documentation files

---

## 12. For AI Agents (CLAUDE.md)

Copy this section to CLAUDE.md in the repo root.

```markdown
# CLAUDE.md — OpenClaw

## Before ANY implementation
1. Read CONSTITUTION.md for project-wide rules
2. Read the relevant docs/specs/[workflow]/spec.md
3. Read docs/specs/[workflow]/plan.md for implementation order
4. Identify which TASK-XX you are implementing — do NOT do multiple tasks

## Execution rules
- Implement ONE task at a time
- Run tests/validators after each task
- If a task fails 2x: STOP and report what's failing
- If requirements are ambiguous: ASK, don't assume
- Commit after each completed task: [TASK-XX] description

## Technical rules
- Use streaming for API calls (litellm_stream.py or subprocess + curl)
- All file paths must be absolute
- mkdir -p target directories before writing files
- Use logging module, never print() for debug output
- Type hints on all Python function signatures

## Quality rules (Development & Testing)
- Audit EVERY output against the spec — no exceptions
- If ANY output contains "TBD", "placeholder", "some_type", or generic text — FAIL
- Validate structurally BEFORE quality-checking with LLM
- After each phase: verify output matches plan, then ask "how can this be improved?"

## Forbidden
- Never use Python requests for long API calls
- Never use sessions_spawn for file writing
- Never accept placeholder/stub data in outputs
- Never pass full upstream JSON to downstream agents
- Never modify files outside the current task scope
- Never copy content between documentation files
```

---

## 13. Change Process

This constitution changes rarely. When it does:
1. Propose change with rationale
2. Evaluate impact on existing workflows
3. Update this file with date in Change Log
4. Commit as `[CONST] description of change`

### Exception Process
If a constitution rule must be violated temporarily:
1. Document WHY in the run manifest
2. Log as LL entry after the run
3. Evaluate if the rule needs updating

### Change Log

| Date | Section | Change | Reason |
|------|---------|--------|--------|
| 2026-04-04 | All | Initial version | SDD system implementation |
