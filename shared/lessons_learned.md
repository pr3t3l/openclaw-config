# Lessons Learned — Master Reference

> Source: copied from workspace-declassified/cases/config/lessons_learned.json on 2026-03-24
> This file is the shared reference for all workspaces. Update here, not per-workspace.

## Lessons

### L-01: Orphan Artifacts
Every artifact must have an explicit consumer. If an output has no consumer, it should not exist. If a consumer needs an artifact that no one produces, it's a missing dependency. **FAIL the pipeline if orphan_outputs or missing_required_artifacts are non-empty.**

### L-02: Contracts Before Code
Define the schema/contract for every artifact BEFORE building the agent that produces it. Agents that guess the output structure produce garbage.

### L-03: Single-Item E2E Test
After any infrastructure change, run ONE item end-to-end before batch processing. Never batch-run untested changes.

### L-04: MVP First
Start with the ugliest functional version. "Feo pero funcional" beats "bonito pero incompleto." Define an upgrade path from MVP to Standard without rewriting.

### L-05: Separate "Works" from "Good"
Infrastructure validation ("does it run?") and quality validation ("is it good?") are different phases. Don't mix them.

### L-06: Test File I/O First
Before building complex logic, verify that the spawn method can read inputs and write outputs to the correct paths.

### L-07: Pre-flight Checks
Check for required system tools (zip, node, python3, chromium, etc.) before starting any pipeline.

### L-08: Token Budget Awareness
If an artifact is too large for a single API call's MAX_TOKENS, split it. Know your model's limits.

### L-09: Track Orchestrator Cost
The orchestrator itself consumes tokens. Account for orchestration overhead in cost estimates.

### L-10: No Stub Outputs
Never accept placeholder/stub data in outputs. Validate that all fields have real, meaningful content.

### L-11: Canonical Asset Libraries
When multiple documents need the same asset (e.g., a person's photo), define one canonical version and reuse it. Don't regenerate.

### L-12: Normalize Identifiers
Use consistent IDs across all artifacts. Don't let different phases use different naming for the same entity.

### L-13: Cross-Reference Integrity
When changing a document's type or content, update ALL cross-references: dependencies, timelines, evidence chains.

### L-14: Cost Telemetry
Track token usage and cost per API call. Fail if a completed pipeline shows zero cost (missing telemetry).

### L-15: Cross-Reference Updates on Conversion
Any doc type conversion requires updating ALL references that depend on that document.

### L-16: Trojan Horse Pacing
Early-envelope documents that hint at the solution must be ambiguous. The explicit reveal comes in later envelopes.

### L-17: Concrete Specificity
Details in documents must be concrete and verifiable, not vague. Reject anything that could apply to any project.

### L-18: Image Coverage
Every document type that needs visual support must have image briefs planned. Don't skip "digital" document types.

### L-19: Output Path Conventions
Define where outputs go BEFORE building. Intermediate vs final output directories must be explicit.

### L-20: Self-Contained Specs
If an artifact is the complete spec for a downstream agent, it must be self-contained — no implicit dependencies.

### L-22: Script vs Agent Decision
If the logic is deterministic (no LLM needed), use a script, not an agent. Agents are for tasks requiring judgment.

### L-25: Orchestrator Token Compounding
Main session context grows with each spawn. Keep orchestration messages concise.

### L-26: Retry with Diagnosis
Never retry with identical parameters. Always include failure diagnosis in the retry prompt. Max 2 retries before manual intervention.

### L-28: Human Gates with Justification
Every human gate must have a clear justification for why automation is too risky at that point.

### L-32: No Hardcoded Case Data in Templates
Templates must be 100% data-driven. No static sample content that pretends to be real data.

## Anti-Patterns

- Never accept `some_type` as type_key — always use exact identifiers
- Never accept generic descriptions ("Reveals something about X") — require specifics
- Never count template/form labels toward content quality minimums
- Never include HTML tags in Markdown files
- Never retry with identical parameters
- Never hardcode case-specific data in templates
- Normalize all identifiers consistently across phases
- Verify cross-references exactly match the evidence

## Model Notes

- gemini31pro-thinking hits rate limits after ~15 spawns in 2 hours
- gpt52-thinking is a reliable fallback for QA and narrative tasks
- Sub-agents via sessions_spawn start fresh — token tracking per sub-agent is reliable
- Main session context compounds with each spawn — keep orchestration concise

## L-33: Compress upstream context for heavy agents
When an agent receives upstream artifacts as context, only include fields relevant to that agent's task.
Implementation planner needs artifact names, purposes, and key fields — not full JSON schemas, examples,
or format-level validation rules. Use `compress_contracts()` pattern in `spawn_planner_agent.py`.
If compression isn't enough, use `block_mode` as fallback. See `docs/FIX_LITELLM_TIMEOUT.md`.

## 2026-03-27 — Contract generation failure on large Advanced artifacts

### Lesson
When a planner artifact becomes large and schema-heavy (especially `04_contracts.json` in Advanced scope), do **not** rely on a single monolithic JSON response from one model call. Large contract outputs are prone to two failure modes:
1. JSON extraction failure (mixed prose + JSON or malformed top-level structure)
2. Truncation / unterminated strings from oversized completion payloads

### Evidence
Observed in `strategy-runtime-1` during B2 / Contract Designer:
- First failure: runner could not extract valid JSON after retries.
- Second failure: `JSONDecodeError: Unterminated string...` while parsing a large generated contract.
- The artifact attempted to include many schemas, examples, validation rules, and split strategies in one payload.

### Rule
For any large contract/spec artifact:
- Prefer split generation by domain/module (for example: core manifests, runtime state, marketing interface, Telegram/security) and consolidate after.
- If keeping one artifact, reduce verbosity: keep schema + required fields + validation rules; avoid long examples unless truly needed.
- Always save raw model output on failure before retrying.
- Treat repeated invalid JSON on large outputs as an architectural problem, not just a token-limit problem.

### Operational guidance
- First failed generation → save raw output and diagnose whether failure is extraction vs truncation.
- Second failed generation on large artifact → stop increasing tokens blindly; switch to chunked generation or smaller contracts.
- Record the failure in lessons learned immediately.

## 2026-03-27 — Use domain-split contract generation for B2 when Advanced scope is large

### Lesson
When `04_contracts.json` becomes too large in Advanced scope, generate contracts by domain/module and consolidate after validation instead of forcing one monolithic response.

### Approved split for this planner
1. Core manifests + runtime
2. Strategic artifacts
3. Marketing interface
4. Gates + Telegram + security
5. Invalidation + rollback + observability

### Rule
If any domain block is still too large, split it further before retrying. Validate each block independently, then consolidate into final `04_contracts.json`.

## 2026-03-27 — Even domain-split B2 can fail; identify failing block before retry

### Lesson
When split-domain contract generation fails, the next move is not a blind re-run. First identify which specific block failed and whether prior blocks succeeded. Save raw output per block and inspect the failing block only.

### Rule
For split generation pipelines, checkpoint after each block. On failure:
1. determine the failing block name,
2. preserve successful blocks,
3. retry only the failing block,
4. if that block still fails, split that block further.

## 2026-03-27 — For very large contract phases, use one-contract-per-artifact generation

### Lesson
If split-by-domain still fails, move to one artifact per generation unit. This minimizes truncation risk and isolates failures to a single contract file.

### Rule
Preferred fallback order for large contract phases:
1. monolithic contracts
2. split by domains
3. split by subdomains
4. one contract per artifact/spec

When using one-contract-per-artifact generation, drop examples first if size remains a problem. Keep only schema + required fields + validation rules.

## 2026-03-27 — Compact contract mode for all artifacts improves consistency and reliability

### Lesson
Even one-contract-per-artifact can fail if each contract is too verbose. For schema-heavy planning phases, enforce a compact output format across ALL artifacts, not just failed ones, to keep structure consistent and reduce parse risk.

### Compact format
Generate ONLY:
1. artifact_name
2. schema_definition (pure JSON Schema)
3. produced_by
4. consumed_by
5. validation_rules (short list)

Do NOT include examples, estimated sizes, long prose, long descriptions, or extended defaults.

## 2026-03-27 — Add JSON auto-repair before declaring schema-generation failure

### Lesson
If schema generation fails with small syntax issues (missing comma, unterminated string, unclosed braces), do not immediately treat it as a hard model failure. First apply a lightweight JSON auto-repair pass and validate the repaired result.

### Rule
For contract/schema generation pipelines:
1. attempt normal JSON parse
2. if parse fails, save raw output
3. run lightweight auto-repair
4. if repaired JSON validates, continue
5. only report failure if repair also fails

## 2026-03-27 — Contract generation should auto-retry up to 3 times before surfacing failure

### Lesson
Do not interrupt the human for every single flaky contract-generation failure. For compact, per-artifact schema generation, auto-retry each artifact up to 3 times before escalating.

### Rule
For contract generation pipelines:
- each contract gets up to 3 attempts automatically
- only report back when all contracts complete, or when one contract fails 3 consecutive times

## 2026-03-27 — Apply auto-repair and retry patterns to implementation plans too

### Lesson
The same failure mode seen in contracts (good content, invalid JSON wrapper) can also happen in implementation plans. Reuse the same robustness pattern: save raw output, retry automatically, attempt lightweight repair, and only then escalate.

## 2026-03-27 — Large implementation plans should be generated by blocks with auto-retry

### Lesson
Implementation plans can fail exactly like contracts: good content, broken JSON wrapper. For large multi-phase build plans, generate by blocks, retry each block up to 3 times, then consolidate.

### Rule
For C1 implementation planning:
- split into logical blocks
- auto-retry each block up to 3 times
- consolidate only after all blocks succeed
- do not interrupt the human for per-block flakiness

## 2026-04-03 — LiteLLM server disconnect on large completions is a timeout issue, not a model issue

### Problem
When combining large input context (~8k tokens) with large max_tokens request (8192), the Anthropic API disconnects mid-generation via LiteLLM proxy. The error appears as `litellm.InternalServerError: AnthropicException - Server disconnected`.

### Diagnosis method
Test the same payload with small max_tokens (500) → works. Test with large max_tokens (8192) → disconnects. This proves the issue is generation time / connection stability, not input size.

### Root cause
No explicit `request_timeout` configured in LiteLLM proxy config. Default timeout is insufficient for large Anthropic completions.

### Fix
Add `request_timeout: 600` to `litellm_settings` in the LiteLLM config YAML, or add per-model `timeout: 600` for Anthropic models. Restart LiteLLM after.

### Fallback
Use block-based generation (already implemented) to split large artifacts into smaller units that stay within safe timeout bounds.

### Rule
When a model call fails with InternalServerError/disconnect, always test with reduced max_tokens first to distinguish between input-size issues and generation-time issues. Document the threshold.
