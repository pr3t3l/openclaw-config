# MEMORY.md — Declassified Cases Agent

## Completed Cases
- **The Last Livestream** (2026-03-16) — NORMAL tier, 86% benchmark, 18 docs
  - Drive: https://drive.google.com/file/d/1_hYi09sNGVWmEPMaa8UENOwzJV5i16Qm/view

## Pipeline State
- Version: V9
- ai_render.py: all-AI rendering via Claude Sonnet API → HTML → Chromium PDF
- POI portraits ONLY for pre-generated images (100px JPEG q70); all other visuals created by Claude in HTML/CSS
- doc_type_catalog.json is the type authority (unlimited types via design_hint)
- API calls via streaming curl (NEVER Python requests in WSL — TL-01)
- 19 lessons in lessons_learned.json — read before every pipeline run
