# Pipeline Version History

## Previous case: el-asesinato-en-la-casa-inteligente (2026-03-11)
- Tier: NORMAL
- Issues: clue_catalog stubs, placeholder passthrough, only 4 mugshots, hardcoded template data, thin forensics/lab reports, empty missing person
- Cost: estimated >$5 due to 3+ retry cycles on Envelope B and C
- Lessons extracted to cases/config/lessons_learned.json


## Pipeline v8.0 — CLEAN DEPLOY (2026-03-13)
- **All V6/V7 artifacts cleaned.** No old changelogs, fix scripts, or stale memory files remain.
- **V8 focuses on EXPERIENCE quality** — the gap between a puzzle and a product
- New agent: Experience Designer (emotional beats, detective annotations, pacing, trojan horse verification)
- New validations: validate_experience.py, benchmark_scoring.py
- New template: floor_plan.html (type_id 19), detective_annotations.html (overlay)
- Pipeline: 10 phases (Init → Narrative → Art → Experience → Production → Playthrough QA → Images → Layout/Render → Package → Distribute)
- Benchmark target: ≥75% (45/60) on 6-pillar scoring
- KEY RULES:
  * 1 canonical portrait per POI, reuse everywhere (never regenerate)
  * Every art brief needs usage_map: {doc_id, template_slot}
  * Tier constraints injected verbatim into Narrative Architect spawn prompt
  * Sub-agent status MUST be checked: completed/failed/timed_out
  * interviews = 1 per living POI (MULTIPLIER, not single doc)
  * social_media_docs: min 3 for NORMAL, min 4 for PREMIUM
  * spatial_tool: REQUIRED for NORMAL and PREMIUM
- Full backup at: ~/.openclaw/workspace_pre_v8_backup_*


## V8.1 Hotfix (2026-03-14)
- **BUG FIX:** validate_narrative.py crashed with KeyError('min_pois') because V8 tier_definitions uses nested objects (pois.min) but validator expected flat keys (min_pois). Fixed with tier_val() helper that handles both schemas.
- **BUG FIX:** Narrative Architect truncation — clue_catalog.json was written as empty {"documents": []} because the sub-agent tried to output 800+ lines of JSON through chat, causing truncation. Fixed by splitting Phase 2 into TWO sub-agent spawns: 2a generates case-plan.json, 2b generates clue_catalog.json separately.
- **NEW RULE:** Sub-agents MUST write large files using the write tool directly to disk. NEVER paste large JSON through chat.
- **NEW RULE:** Orchestrator MUST verify file existence + minimum size after every sub-agent that writes files.
- **NEW RULE:** Orchestrator MUST backup case-plan.json and clue_catalog.json before any operation that might overwrite them.
- **NEW SECTION in AGENTS.md:** "Sub-Agent Output Rules" — explicit truncation prevention.
- **NEW SECTION in AGENTS.md:** "TRUNCATION failure" classification in Retry Protocol.
- Lessons: LL-015 (validator schema mismatch), LL-016 (sub-agent output truncation)


## V8.2 Hotfix (2026-03-14)
- **NEW SCRIPT:** fix_case_plan_schema.py — auto-fixes 6 known schema shape mismatches:
  1. evidence_chain strings → objects with step/docs_needed/reveals
  2. contradiction IDs: adds CONTRA-NN if missing
  3. POI field rename: poi_id → id
  4. Envelope key: doc_ids/documents → docs
  5. Culprit: method string → method_steps array
  6. emotional_arc key normalization
- **FIX:** validate_narrative.py now has type guards on ALL loops — never crashes on wrong types, reports clear FAIL messages instead
- **PIPELINE CHANGE:** Schema fixer runs automatically after Phase 2a, before validation
- Root cause: models follow skeleton structure ~85% of the time. The remaining 15% produces correct CONTENT in wrong SHAPE. Auto-fixing shape is cheaper than re-running the agent.
