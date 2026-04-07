---
name: sdd_planner
description: Alias for /plan-sdd — start a new SDD planning run from a project idea
command: /sdd_planner
command-dispatch: tool
command-tool: exec
command-arg-mode: raw
---

# /sdd_planner — Start SDD Planner (alias)

This is an alias for `/plan-sdd`.

Execute the following command with the raw arguments passed by the user:

```bash
python3 /home/robotin/.openclaw/workspace-meta-planner/scripts/run_sdd_planner.py start "<args>"
```

Where `<args>` is the raw text the user provided after `/sdd_planner`.
