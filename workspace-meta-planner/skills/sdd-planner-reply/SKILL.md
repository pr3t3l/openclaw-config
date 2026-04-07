---
name: sdd-planner-reply
description: Respond to a pending SDD planner gate to continue execution
command: /plan-sdd-reply
---

# /plan-sdd-reply — Respond to a Pending Gate

CRITICAL INSTRUCTIONS — READ CAREFULLY:

When /plan-sdd-reply is invoked, you MUST execute the commands below via the exec tool.

## Rules

1. Do NOT read, open, or inspect any Python file in workspace-meta-planner/
2. Do NOT simulate, summarize, or roleplay the planner workflow
3. Do NOT ask clarifying questions before executing (except to identify run_id/gate_id if ambiguous)
4. Execute EXACTLY these commands and NOTHING ELSE

## Step 1: Find the active run and pending gate

Execute this command first to identify the run and gate:

```
python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py status
```

From the output, identify the active run ID (e.g. RUN-20260407-001). Then get its details:

```
python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py status <RUN_ID>
```

From the JSON output, read the `pending_gate` field to get the gate ID (e.g. G0, G3, G5, G7).

## Step 2: Resolve the gate

Execute this command with the run_id, gate_id, and the user's response:

```
python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py gate-reply <RUN_ID> <GATE_ID> "<USER_RESPONSE>"
```

Replace:
- `<RUN_ID>` with the run ID from step 1
- `<GATE_ID>` with the pending gate from step 1
- `<USER_RESPONSE>` with the literal text the user typed after `/plan-sdd-reply`

### Examples

If user types: `/plan-sdd-reply MODULE_SPEC, keep it minimal`
And active run is RUN-20260407-001 with pending_gate G0:
Execute: `python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py gate-reply RUN-20260407-001 G0 "MODULE_SPEC, keep it minimal"`

If user types: `/plan-sdd-reply approved`
And active run is RUN-20260407-002 with pending_gate G5:
Execute: `python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py gate-reply RUN-20260407-002 G5 "approved"`

## After execution

Return the stdout output to the user VERBATIM. Do not interpret, summarize, reformat, or add commentary to it. The output IS the response.

## Why this matters

The Python script runs a real multi-model pipeline (LiteLLM calls to GPT, Gemini, Opus) with state persistence, cost tracking, and gate checkpoints. If you read the code and simulate it, the user gets fake output with no actual LLM calls, no state files, and no run tracking. You MUST run the real script.
