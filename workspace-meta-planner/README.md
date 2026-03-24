# Meta-Workflow Planner

A system that takes a raw idea and produces a complete, buildable development plan for any future workflow.

Designed iteratively by Claude Opus 4.6, GPT-5.4, Gemini 3.1 Pro, and MiniMax M2.7. See `workflow_builder_master_plan_v3_operational.md` for the full design document.

## Quick Start

### Initialize a new plan

```bash
bash scripts/start_plan.sh <slug> "<idea text>"
```

This creates `runs/<slug>/manifest.json` with all artifacts in "missing" status.

### Resume a paused plan

```bash
bash scripts/resume_plan.sh <slug>
```

Shows the current state of all artifacts and gates, and suggests the next step. Does not execute anything.

### Validate an artifact

```bash
python3 scripts/validate_schema.py <slug> <artifact_name>
```

Validates a produced artifact against its JSON Schema in `schemas/`.

## Pipeline

The planner runs in 3 phases with human gates between each:

- **Fase A (Clarify):** Intake Analyst → Gap Finder → Scope Framer → Gate #1
- **Fase B (Design):** Data Flow Mapper → Contract Designer → Architecture Planner → Gate #2
- **Fase C (Buildability):** Implementation Planner → Cost Estimator → Lessons Validator → Gate #3

## Structure

```
workspace-meta-planner/
├── planner_config.json    # General configuration
├── models.json            # Model routing (change here, not in scripts)
├── skills/                # SKILL.md per agent (populated in Build Phase 1+)
├── schemas/               # JSON Schema per artifact
├── scripts/               # Execution scripts
├── runs/                  # One subdirectory per plan execution
└── README.md
```

## Shared Resources

```
~/.openclaw/shared/
├── scripts/spawn_core.py  # Pinned copy of the spawn pattern
├── scripts/VERSION        # Version tracking
└── lessons_learned.md     # Master lessons learned reference
```
