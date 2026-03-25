# HEARTBEAT.md — Declassified Agent

## When to activate
On each heartbeat, check manifest.json pipeline status:
- If `status` is "in_progress" → ACTIVE mode: check subagent status, continue pipeline
- If `status` is "distributed" or "initialized" or no active case → IDLE mode: do nothing

## Active mode actions
1. Read manifest.json → find current pipeline phase
2. Check if any subagent is pending/running
3. If subagent completed → run next validation → advance pipeline
4. If subagent running > 5 min → check status, report if stuck
5. If at a human gate → do nothing (wait for human)

## Pipeline start trigger
When user says "start a new case" or similar:
1. Run start_new_case.sh
2. Enable heartbeat: update manifest status to "in_progress"

## Pipeline end trigger
After Phase 10 (distribution) completes:
1. Update manifest status to "distributed"
2. Heartbeat checks will see "distributed" and go idle automatically
