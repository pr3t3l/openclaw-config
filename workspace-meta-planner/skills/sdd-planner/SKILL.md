---
name: sdd-planner
description: Start a new SDD planning run from a project idea
command: /plan-sdd
---

# /plan-sdd — SDD Planner

CRITICAL INSTRUCTIONS — READ CAREFULLY:

When /plan-sdd is invoked, you MUST execute the command below via the exec tool.

## Rules

1. Do NOT read, open, or inspect any Python file in workspace-meta-planner/
2. Do NOT simulate, summarize, or roleplay the planner workflow
3. Do NOT ask clarifying questions before executing
4. Do NOT modify the command in any way
5. Execute EXACTLY this command and NOTHING ELSE first

## Command to execute

```
python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py start "<USER_ARGS>"
```

Replace `<USER_ARGS>` with the literal text the user typed after `/plan-sdd`.

### Examples

If user types: `/plan-sdd Build a CLI todo app with SQLite`
Execute: `python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py start "Build a CLI todo app with SQLite"`

If user types: `/plan-sdd E-commerce API with Stripe integration`
Execute: `python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py start "E-commerce API with Stripe integration"`

## After execution

Return the stdout output to the user VERBATIM. Do not interpret, summarize, reformat, or add commentary to it. The output IS the response.

## Why this matters

The Python script runs a real multi-model pipeline (LiteLLM calls to GPT, Gemini, Opus) with state persistence, cost tracking, and gate checkpoints. If you read the code and simulate it, the user gets fake output with no actual LLM calls, no state files, and no run tracking. You MUST run the real script.
