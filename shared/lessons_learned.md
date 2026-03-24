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
