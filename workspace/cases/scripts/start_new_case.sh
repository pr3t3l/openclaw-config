#!/usr/bin/env bash
# start_new_case.sh — Initialize a new Declassified Cases folder structure (v6)
# Usage: bash cases/scripts/start_new_case.sh <slug> <TIER>

set -euo pipefail

SLUG="${1:?Usage: start_new_case.sh <slug> <TIER>}"
TIER="${2:?Usage: start_new_case.sh <slug> <TIER>}"
WORKSPACE="$(cd "$(dirname "$0")/../.." && pwd)"
CASE_DIR="${WORKSPACE}/cases/exports/${SLUG}"
CONFIG_DIR="${WORKSPACE}/cases/config"
TIER_FILE="${CONFIG_DIR}/tier_definitions.json"

# ── Pre-flight checks ──────────────────────────────────────────────────
echo "=== Pre-flight checks ==="

# Validate tier
if [[ "$TIER" != "SHORT" && "$TIER" != "NORMAL" && "$TIER" != "PREMIUM" ]]; then
  echo "ERROR: Tier must be SHORT, NORMAL, or PREMIUM. Got: $TIER"
  exit 1
fi

# Check required config files
for f in tier_definitions.json doc_type_catalog.json model_routing.json; do
  if [[ ! -f "${CONFIG_DIR}/${f}" ]]; then
    echo "ERROR: Missing config file: ${CONFIG_DIR}/${f}"
    exit 1
  fi
done

# Check required tools
for tool in node python3 zip; do
  if ! command -v $tool &> /dev/null; then
    echo "ERROR: Required tool not found: $tool"
    exit 1
  fi
done

# Check chromium
if ! command -v chromium-browser &> /dev/null && ! command -v chromium &> /dev/null && ! command -v google-chrome &> /dev/null; then
  echo "WARN: No chromium/chrome found. PDF rendering may fail in Phase 8."
fi

# Check handlebars
if ! node -e "require('handlebars')" 2>/dev/null; then
  echo "WARN: handlebars not installed. Will install during render."
fi

# Check if case already exists
if [[ -d "$CASE_DIR" ]]; then
  echo "ERROR: Case directory already exists: $CASE_DIR"
  echo "Delete it first or use a different slug."
  exit 1
fi

echo "  All checks passed ✓"
echo ""

# ── Create directory structure ──────────────────────────────────────────
echo "=== Initializing case: $SLUG (tier: $TIER) ==="

mkdir -p "${CASE_DIR}"

case "$TIER" in
  SHORT)   ENVELOPES=("A" "B" "R") ;;
  NORMAL)  ENVELOPES=("A" "B" "C" "R") ;;
  PREMIUM) ENVELOPES=("A" "B" "C" "D" "R") ;;
esac

for ENV in "${ENVELOPES[@]}"; do
  mkdir -p "${CASE_DIR}/envelope_${ENV}"
  mkdir -p "${CASE_DIR}/visuals/envelope_${ENV}/final"
done

mkdir -p "${CASE_DIR}/visuals/canonical"
mkdir -p "${CASE_DIR}/visuals/scenes"
mkdir -p "${CASE_DIR}/visuals/evidence"
mkdir -p "${CASE_DIR}/visuals/cctv"
mkdir -p "${CASE_DIR}/visuals/devices"
mkdir -p "${CASE_DIR}/qa"
mkdir -p "${CASE_DIR}/qa/failures"
mkdir -p "${CASE_DIR}/final"
mkdir -p "${CASE_DIR}/layout_specs"

if [[ "$TIER" == "PREMIUM" ]]; then
  mkdir -p "${CASE_DIR}/audio"
  mkdir -p "${CASE_DIR}/audio_scripts"
fi

# ── Create manifest.json ────────────────────────────────────────────────
CREATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

PIPELINE_ENVELOPES="{"
for ENV in "${ENVELOPES[@]}"; do
  PIPELINE_ENVELOPES+="\"${ENV}\": \"pending\","
done
PIPELINE_ENVELOPES="${PIPELINE_ENVELOPES%,}}"

if [[ "$TIER" == "PREMIUM" ]]; then
  TTS_SCRIPT="\"pending\""
  TTS_GEN="\"pending\""
else
  TTS_SCRIPT="\"not_applicable\""
  TTS_GEN="\"not_applicable\""
fi

cat > "${CASE_DIR}/manifest.json" << MANIFEST
{
  "case_id": "",
  "slug": "${SLUG}",
  "tier": "${TIER}",
  "status": "initialized",
  "created_at": "${CREATED_AT}",
  "updated_at": "${CREATED_AT}",
  "pois": [],
  "documents": {},
  "images": {},
  "audio": {},
  "pipeline_state": {
    "narrative_architect": "pending",
    "narrative_qa": "pending",
    "art_director": "pending",
 "experience_designer": "pending",
    "experience_designer": "pending",
    "production_envelopes": ${PIPELINE_ENVELOPES},
    "playthrough_qa": "pending",
    "image_generation": "pending",
    "tts_scripting": ${TTS_SCRIPT},
    "tts_generation": ${TTS_GEN},
    "layout_planning": "pending",
    "render": "pending",
    "distribution": "pending"
  },
  "cost_tracking": {
    "phases": {},
    "images": {},
    "totals": {
      "input_tokens": 0,
      "output_tokens": 0,
      "wasted_tokens_retries": 0,
      "images_generated": 0,
      "estimated_total_usd": 0
    }
  }
}
MANIFEST

echo ""
echo "=== Case initialized ==="
echo "  Path: ${CASE_DIR}"
echo "  Tier: ${TIER}"
echo "  Envelopes: ${ENVELOPES[*]}"
echo ""
echo "Next: Create case_config.json, then run Narrative Architect."
