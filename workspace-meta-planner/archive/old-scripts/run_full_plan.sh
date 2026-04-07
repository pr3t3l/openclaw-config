#!/bin/bash
# Usage: bash run_full_plan.sh <slug> "<idea>" [regular|deep]
# Runs the ENTIRE planner pipeline: init → A → Gate #1 → B → Gate #2 → C → Gate #3 → Report

set -euo pipefail

SLUG="$1"
IDEA="$2"
LEVEL="${3:-regular}"

WORKSPACE="/home/robotin/.openclaw/workspace-meta-planner"
SCRIPTS="$WORKSPACE/scripts"

echo "============================================"
echo "  META-WORKFLOW PLANNER — Full Run"
echo "  Slug: $SLUG"
echo "  Analysis: $LEVEL"
echo "============================================"

# Init
bash "$SCRIPTS/start_plan.sh" "$SLUG" "$IDEA" "$LEVEL"

# Helper: read analysis_level from manifest
get_level() {
  python3 -c "
import json
with open('$WORKSPACE/runs/$SLUG/manifest.json') as f:
    print(json.load(f).get('analysis_level', 'regular'))
"
}

# Helper: run phase agent respecting level
run_with_level() {
  local AGENT="$1"
  local LVL=$(get_level)
  if [ "$LVL" = "deep" ]; then
    python3 "$SCRIPTS/spawn_debate.py" "$SLUG" --phase "$AGENT"
  else
    python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" "$AGENT"
  fi
}

# === FASE A ===
echo ""
echo "=== FASE A: CLARIFY ==="

# A1: Iterative Intake (up to 5 rounds)
for round in 1 2 3 4 5; do
  python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" intake_analyst
  STATUS=$(python3 -c "import json; print(json.load(open('$WORKSPACE/runs/$SLUG/00_intake_summary.json'))['status'])")
  if [ "$STATUS" = "READY" ]; then
    echo "  Intake READY after round $round"
    break
  fi
  echo "  Round $round: NEEDS_CLARIFICATION"
  echo "  Answer the questions in intake_pending_questions.json"
  echo "  Save answers to intake_answers.json"
  read -p "  (Press Enter after answering, or 'quit' to stop): " RESP
  if [ "$RESP" = "quit" ]; then exit 0; fi
done

# A2: Gap Finder
run_with_level gap_finder

# A3: Scope Framer
run_with_level scope_framer

# GATE #1
python3 "$SCRIPTS/human_gate.py" "$SLUG" 1
GATE1_RESULT=$?
if [ $GATE1_RESULT -eq 2 ]; then
  echo "  Gate #1: adjustments requested. Re-running Fase A..."
  python3 "$SCRIPTS/spawn_planner_agent.py" "$SLUG" intake_analyst
  run_with_level gap_finder
  run_with_level scope_framer
  python3 "$SCRIPTS/human_gate.py" "$SLUG" 1
  GATE1_RESULT=$?
fi
if [ $GATE1_RESULT -eq 1 ]; then echo "  Gate #1 rejected. Stopping."; exit 0; fi

# === FASE B ===
echo ""
echo "=== FASE B: DESIGN ==="
bash "$SCRIPTS/run_phase_b.sh" "$SLUG"

# GATE #2
python3 "$SCRIPTS/human_gate.py" "$SLUG" 2
GATE2_RESULT=$?
if [ $GATE2_RESULT -eq 2 ]; then
  echo "  Gate #2: adjustments requested. Re-running Fase B..."
  bash "$SCRIPTS/run_phase_b.sh" "$SLUG"
  python3 "$SCRIPTS/human_gate.py" "$SLUG" 2
  GATE2_RESULT=$?
fi
if [ $GATE2_RESULT -eq 1 ]; then echo "  Gate #2 rejected. Stopping."; exit 0; fi

# === FASE C ===
echo ""
echo "=== FASE C: BUILDABILITY ==="
bash "$SCRIPTS/run_phase_c.sh" "$SLUG"

# GATE #3
python3 "$SCRIPTS/human_gate.py" "$SLUG" 3
GATE3_RESULT=$?
if [ $GATE3_RESULT -eq 2 ]; then
  echo "  Gate #3: adjustments requested. Re-running Fase C..."
  bash "$SCRIPTS/run_phase_c.sh" "$SLUG"
  python3 "$SCRIPTS/human_gate.py" "$SLUG" 3
  GATE3_RESULT=$?
fi
if [ $GATE3_RESULT -eq 1 ]; then echo "  Gate #3 rejected. Stopping."; exit 0; fi

# === REPORT ===
echo ""
echo "=== GENERATING REPORT ==="
python3 "$SCRIPTS/build_fact_pack.py" "$SLUG"
python3 "$SCRIPTS/generate_report.py" "$SLUG"

echo ""
echo "============================================"
echo "  PLAN COMPLETE"
echo "  Report: runs/$SLUG/${SLUG}_report.html"
echo "============================================"
