---
name: content-distribution
description: Renders final PDFs, merges per envelope, packages ZIP, and uploads to Drive. The final step in the Declassified Cases pipeline.
---

# Content Distribution

You render and package the final Declassified Cases product for distribution.

## Step 0 — Read (SILENTLY)

Read these inputs **silently**.
- **NEVER echo, quote, paste, or summarize file contents verbatim** in your output.
- Report only the distribution summary + links.

1. `cases/exports/<CASE_SLUG>/manifest.json` — case state, all docs
2. `cases/exports/<CASE_SLUG>/clue_catalog.json` — document inventory per envelope
3. `cases/config/model_routing.json` — not for model selection, just for cost tracking reference

## Process

### 1. Verify Rendered Output

ai_render.py should have already rendered all documents in Phase 8:

1. Check that `layout_specs/<doc_id>.html` and `layout_specs/<doc_id>.pdf` exist for each document
2. Verify each PDF is > 1KB
3. If any are missing, re-run: `python3 cases/scripts/ai_render.py cases/exports/<slug>/`

### 2. Merge PDFs per envelope

For each envelope, merge all individual PDFs into one:
- Run: `node cases/render/merge_pdfs.js <sorted_pdf_list> <output_path>`
- Result: `final/Envelope_A.pdf`, `final/Envelope_B.pdf`, etc.
- PDFs must be in sequence_number order within each envelope

### 3. Package

Create `final/` directory with:
- Envelope PDFs (Envelope_A.pdf, Envelope_B.pdf, ... Envelope_R.pdf)
- Audio files (if PREMIUM): copy from `audio/` to `final/audio/`

### 4. Create ZIP

Use Python zipfile (more reliable than zip CLI):
```python
import zipfile, os
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(final_dir):
        for f in files:
            filepath = os.path.join(root, f)
            arcname = os.path.relpath(filepath, final_dir)
            zf.write(filepath, arcname)
```

### 5. Upload to Drive

- Upload ZIP to Google Drive folder "Declassified Cases Exports"
- Send Drive link to Telegram
- Update manifest.json: `status = "distributed"`, `distribution = "completed"`

### 6. Validate final output

Run: `exec python3 cases/scripts/validate_final.py cases/exports/<CASE_SLUG>/`

## After packaging

Report to orchestrator with human-readable summary:
```
CASE DELIVERED: [title]
- Envelopes: A (X pages), B (Y pages), C (Z pages), R (W pages)
- Images: N generated
- Audio: N files (PREMIUM only)
- ZIP size: X.X MB
- Drive link: [URL]
- Total estimated cost: $X.XX
```

## Cost Tracking

After completion, compile the full cost_tracking section for manifest.json from all phase entries.
