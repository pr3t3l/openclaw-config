# SDD Planner — SKILL.md

## Trigger
User sends `/plan-sdd` followed by a project description.

## Commands

### /plan-sdd [description]
Start a new SDD planning run from an idea.

**Execute:**
```bash
cd /home/robotin/.openclaw/workspace-meta-planner
python3 scripts/run_sdd_planner.py start [description] --doc-type WORKFLOW_SPEC
```

Ask the user: "Is this a MODULE (app/service) or WORKFLOW (pipeline/automation)?"
- If MODULE → add `--doc-type MODULE_SPEC`
- If WORKFLOW → add `--doc-type WORKFLOW_SPEC`

### /plan-sdd-status [run_id]
Check status of SDD planner runs.

**Execute:**
```bash
cd /home/robotin/.openclaw/workspace-meta-planner
python3 scripts/run_sdd_planner.py status [run_id]
```

### /plan-sdd-resume [run_id]
Resume an interrupted SDD planner run.

**Execute:**
```bash
cd /home/robotin/.openclaw/workspace-meta-planner
python3 scripts/run_sdd_planner.py resume [run_id]
```

### /plan-sdd-test
Test LiteLLM connectivity for the SDD planner.

**Execute:**
```bash
cd /home/robotin/.openclaw/workspace-meta-planner
python3 scripts/run_sdd_planner.py test-call
```

## Important
- This is SEPARATE from the old planner pipeline (start_plan.sh).
- `/plan-sdd` = new SDD Python planner in `planner/`
- Old commands (`start plan`, `run strategy`) = old shell pipeline
- Do NOT mix them. They use different run directories.

## Run Directory
SDD runs go to: `workspace-meta-planner/planner_runs/{RUN-ID}/`
Old runs go to: `workspace-meta-planner/runs/{slug}/`

## Output
Report the command output to the user via Telegram.
For status, format nicely with emojis.
