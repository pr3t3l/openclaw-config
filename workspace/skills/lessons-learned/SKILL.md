---
name: lessons-learned
description: Reviews failure records after each case and updates lessons_learned.json. Runs after case completion or after pipeline failures requiring human intervention. Reads structured failure records, not full chat logs.
---

# Lessons Learned

You review what went wrong (and right) during case production and update the knowledge base so future cases avoid the same mistakes.

## When you run

1. **After every case completion** — automatic review of all failure records
2. **After any pipeline failure that required human intervention** — immediate review of that failure

## Step 0 — Read (SILENTLY)

Read these inputs **silently**.
- **NEVER echo, quote, paste, or summarize file contents verbatim** in your output.
- Your output must contain **only** the updated `cases/config/lessons_learned.json` content.

1. `cases/exports/<CASE_SLUG>/qa/failures/` — ALL failure record JSON files from this case
2. `cases/exports/<CASE_SLUG>/manifest.json` — cost_tracking section (which phases were expensive)
3. `cases/exports/<CASE_SLUG>/playthrough_report.json` — any suggestions from playthrough QA
4. `cases/config/lessons_learned.json` — current knowledge base (to avoid duplicates)

**IMPORTANT**: You read ONLY structured failure records and reports. You do NOT read the full Robotin chat log — that would be too expensive.

## What you produce

Update `cases/config/lessons_learned.json` with new entries.

### For each failure record, extract:

```json
{
  "id": "LL-XXX",
  "date": "<today>",
  "case_slug": "<slug>",
  "phase": "<which agent/phase failed>",
  "category": "<root cause category>",
  "problem": "<what went wrong, specific>",
  "root_cause": "<why it went wrong>",
  "fix_applied": "<what was done to fix it>",
  "applies_to": ["<which skills/scripts should be aware>"]
}
```

### Categories to use:
- `clue_catalog_quality` — vague/stub entries in clue_catalog
- `schema_mismatch` — JSON structure doesn't match what validator expects
- `placeholder_passthrough` — placeholders in final output
- `content_quality` — thin/empty content that passes word count but fails experience
- `incomplete_image_coverage` — missing image briefs
- `hardcoded_template_data` — static filler in templates
- `model_rate_limit` — API rate limits causing failures
- `missing_tools` — system tools not installed
- `state_management` — pipeline state stuck or inconsistent
- `document_type_mismatch` — wrong document type selected for the story
- `retry_waste` — identical retry without addressing root cause

### Update anti_patterns

If a pattern repeats across 2+ cases, add it to the `anti_patterns` array. Write it as a clear "Never do X" rule.

### Update model_notes

If a model-specific issue was discovered (rate limits, quality issues, cost surprises), add to `model_notes`.

### Cost analysis

If any phase spent >2x the average for that phase type, flag it:
```json
{
  "id": "LL-XXX",
  "category": "cost_anomaly",
  "problem": "Production Engine Envelope B cost $3.50 (3 retries) vs typical $0.80",
  "root_cause": "Schema mismatch caused 2 unnecessary retries",
  "fix_applied": "SKILL.md now includes exact JSON example"
}
```

## Self-Check

- [ ] Every failure record has been reviewed and cataloged
- [ ] No duplicate lessons (check existing IDs and descriptions)
- [ ] anti_patterns are actionable ("Never do X" format)
- [ ] model_notes include any new rate limit or cost observations
- [ ] lessons_learned.json is valid JSON after update
