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
