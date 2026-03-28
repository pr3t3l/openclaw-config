## When to activate
On each heartbeat, check for active runs:
- Look in runs/ for any directory with a manifest.json where ALL gates are NOT approved AND at least one artifact has status "fresh"
- If found → ACTIVE mode: check run status, continue pipeline, report progress
- If no active runs found → IDLE mode: respond only with HEARTBEAT_OK, do nothing else

## Active mode actions
1. Read the active run's manifest.json → find current phase
2. Check if a session/subprocess is running for this run
3. If a phase completed → report result to human via Telegram
4. If at a human gate → remind human once, then wait (do NOT auto-approve)
5. If a subprocess is stuck > 10 min → report as potentially stuck
6. If contracts/architecture generation failed → report the error and wait for instructions

## Flow start trigger
When user says "start plan", "run strategy", "correr planner" or similar:
1. Run start_plan.sh or start_plan_from_file.sh
2. The run directory + manifest.json are created automatically
3. Heartbeat will detect the new active run on next cycle

## Flow end trigger
After Gate #3 is approved AND report is generated:
1. All gates show approved in manifest.json
2. Heartbeat checks will see no active runs and go idle automatically

## During idle
- Do NOT process old runs
- Do NOT re-analyze completed plans
- Do NOT generate reports unprompted
- Just respond HEARTBEAT_OK
