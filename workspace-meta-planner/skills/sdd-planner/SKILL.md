---
name: sdd-planner
description: Start a new SDD planning run from a project idea
command: /plan-sdd
command-dispatch: tool
command-tool: exec
command-arg-mode: raw
---

# /plan-sdd — Start SDD Planner

Execute the following command with the raw arguments passed by the user:

```bash
python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py start "<args>"
```

Where `<args>` is the raw text the user provided after `/plan-sdd`.

## What happens

The script runs Phase 0 (setup, mode detection, PII scan), creates a new run,
and presents Gate-0 to the user. Then it exits.

The user must respond to the gate via `/plan-sdd-reply` (the `sdd-planner-reply` skill)
to continue execution through subsequent phases.

## Examples

```
/plan-sdd Build a CLI todo app with SQLite backend
/plan-sdd E-commerce API with Stripe integration
```
