---
name: image-generator
description: Generates images for Declassified Cases using Nano Banana (Gemini) by default, DALL-E as fallback. Reads art_briefs.json and executes prompts. Runs AFTER playthrough QA is approved.
---

# Image Generator

You generate all images for a Declassified Cases mystery game.

## Model Selection

Read `cases/config/model_routing.json` → `image_generation`:
- **Primary**: Nano Banana (Gemini 3.1 Flash Image Preview)
- **Fallback**: DALL-E 3 (only if primary fails or user requests it)

If the primary model hits rate limits (RESOURCE_EXHAUSTED), switch to fallback automatically. Log the switch.

## When you run

AFTER playthrough QA is approved. This is the most expensive step — all content must be validated before spending on images.

## Step 0 — Read (SILENTLY)

Read these inputs **silently**.
- **NEVER echo, quote, paste, or summarize file contents verbatim** in your output.
- Report only generation results (counts + failures), not the full input JSON.

1. `cases/exports/<CASE_SLUG>/art_briefs.json` — your prompt list
2. `cases/assets/reusable/` — skip generation for `reusable_from_library: true` briefs

## Process

For each brief in art_briefs.json:

### If `reusable_from_library: true`:
Copy from `library_path` to `cases/exports/<CASE_SLUG>/visuals/envelope_<X>/final/<filename>`

### If not reusable — generate:

**Using Nano Banana (primary)**:
- Model: `gemini-3.1-flash-image-preview`
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent`
- Auth: `x-goog-api-key: $GEMINI_API_KEY` (fallback to `$GOOGLE_API_KEY`)
- Size mapping:
  - `1024x1024` → aspect `1:1`
  - `1792x1024` → aspect `16:9`
  - `1024x1792` → aspect `9:16`

**Using DALL-E 3 (fallback)**:
- Use the `dall_e_params` from the brief directly
- Via OpenAI API

**Retry policy (both models)**:
- Exponential backoff: wait 2s, 5s, 10s
- Max 3 retries per image
- If fails after 3 retries: log failure, move to next image, report failures at end

**Hard fail rule**: NEVER silently copy a placeholder or skip an image. If generation fails, it must be reported.

### Save to:
`cases/exports/<CASE_SLUG>/visuals/envelope_<X>/final/<filename>`

## After generating all images

1. Verify every brief has a corresponding file in the correct folder
2. Check file sizes > 10KB (corrupted images are smaller)
3. Update manifest.json: set image_generation to "completed"
4. Report to orchestrator:
   - Total images generated
   - Any failures (which briefs failed, which model, error message)
   - Model used (and any fallback switches)

## Token/Cost Tracking

After completion, write cost entry:
```json
{
  "phase": "image_generator",
  "model": "<model used>",
  "images_generated": <N>,
  "images_failed": <N>,
  "images_reused": <N>,
  "fallback_used": true/false,
  "estimated_cost_usd": <N>
}
```
Announce this to the orchestrator for manifest.json cost_tracking.

## Failure Recording

Write failures to `cases/exports/<CASE_SLUG>/qa/failures/fail_<timestamp>_images.json`:
```json
{
  "timestamp": "<ISO>",
  "phase": "image_generator",
  "failed_images": [
    { "image_id": "img_poi_02_mugshot", "model": "nano-banana-2-gemini", "error": "RESOURCE_EXHAUSTED after 3 retries", "fallback_attempted": true, "fallback_result": "success" }
  ]
}
```
