---
name: sdd-planner-reply
description: Respond to a pending SDD planner gate to continue execution
command: /plan-sdd-reply
---

# /plan-sdd-reply — Respond to a Pending Gate

This skill handles human responses to SDD planner gates (G0, G1, G1.5, G3, G5, G6.5, G7).

## How to use

When a user responds to a pending gate, determine from their message:

1. **Which run** — Check the most recent active run if not specified.
   Run `python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py status`
   to list runs and find the one with a pending gate.

2. **Which gate** — Read the `pending_gate` field from the run status.
   Run `python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py status <run_id>`
   to get the pending gate ID.

3. **The response** — The user's message text is the gate response.

Then execute:

```bash
python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py gate-reply <run_id> <gate_id> "<response>"
```

## Gate response patterns

- **G0** (Mode confirmation): User says doc type, e.g. "MODULE_SPEC" or "WORKFLOW_SPEC, keep it minimal"
- **G1** (Idea confirmation): "approved", "looks good", or corrections
- **G1.5** (Ideation): "approved", "skip", or feedback
- **G3** (Audit triage): "approved" or specific issues to fix
- **G5** (Document approval): "approved" or revision requests
- **G6.5** (Cross-doc validation): "approved" or contradictions to resolve
- **G7** (Final approval): "approved" or revision requests

Keywords that mean rejection: "reject", "rejected", "no", "deny", "denied", "redo"
Everything else is treated as approval with notes.

## What happens

The script resolves the gate, then continues executing phases until:
- The next human gate is reached (pauses again), or
- The run completes, or
- A cost limit is hit

The output is printed to stdout for the user to see.

## Examples

```
/plan-sdd-reply MODULE_SPEC, keep it minimal
/plan-sdd-reply approved
/plan-sdd-reply rejected, the scope is too broad
```
