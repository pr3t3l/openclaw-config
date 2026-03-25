# TOOLS.md - Local Notes

## Declassified Cases — Pipeline Tools (V9)

### Model routing
**DO NOT hardcode model names.** Read `cases/config/model_routing.json` for all model selection.
- Reasoning levels: thinking, medium, none
- Each skill maps to a level via agent_reasoning_map
- Primary + fallback per level for rate limit resilience

### Case scripts
- `cases/scripts/start_new_case.sh <slug> <tier>` — initializes case folder
- `cases/scripts/validate_narrative.py <case_dir>` — validates case plan + clue_catalog quality
- `cases/scripts/validate_content.py <case_dir> [envelope]` — validates narrative content quality (word counts, placeholders)
- `cases/scripts/validate_art.py <case_dir>` — validates art briefs (POI portraits only in V9)
- `cases/scripts/validate_placeholders.py <case_dir>` — scans entire case for ANY placeholder
- `cases/scripts/validate_final.py <case_dir>` — validates rendered output completeness
- `cases/scripts/ai_render.py <case_dir>` — V9 all-AI document renderer (Claude API → HTML → PDF)
- `cases/scripts/cost_tracker.py <case_dir>` — unified cost tracking

### Render pipeline (V9)
- `cases/scripts/ai_render.py <case_dir>` — reads _content.md + doc_type_catalog + experience_design → Claude API → HTML → Chromium PDF
- `cases/render/render_pdf_system_chromium.js` — Chromium PDF backend (used by ai_render.py)
- `cases/render/merge_pdfs.js` — merge per-envelope PDFs

### File structure
- Config: `cases/config/` (tier_definitions, doc_type_catalog, design_system, model_routing, lessons_learned)
- Exports: `cases/exports/<slug>/` (one folder per case)
- Assets: `cases/assets/` (body-diagrams, reusable assets)

### Token tracking
- After each sub-agent spawn, read session usage and write to manifest.json cost_tracking
- Use cost_tracker.py for programmatic tracking
- Pricing reference: model_routing.json pricing_per_1M_tokens

### Environment
- WSL/Ubuntu via Tailscale
- Direct Anthropic API via streaming curl (NOT Python requests — see TL-01)
- Chromium headless for PDF rendering
- Node.js for render scripts
- Python 3 for validation scripts
- ElevenLabs API for TTS (PREMIUM only)
- Google Drive via gog skill for uploads
