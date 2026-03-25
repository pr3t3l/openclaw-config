# V9 Pipeline Audit Report — Declassified Cases

**Auditor:** Claude (Opus 4.6)
**Date:** 2026-03-19
**Scope:** Full workspace audit — every agent, skill, script, and config reviewed in pipeline sequence
**Goal:** Align entire pipeline with V9 decisions (all-AI rendering, no templates, POI-only images, unlimited doc types)

---

## EXECUTIVE SUMMARY

The workspace is stuck between V8 and V9. The V9 rendering engine (`ai_render.py`) exists and works, but virtually everything upstream still references the V8 template-based system. The pipeline will produce cases, but with three critical failures:

1. **No document gets its emotional beat or detective annotations during rendering** — the experience_design.json lookup in ai_render.py is completely broken
2. **Custom document types will fail validation** — validate_narrative.py rejects any type_key not in template_registry.json, killing V9's extensibility
3. **AGENTS.md Phase 8 describes a pipeline that no longer exists** — references inject_and_render.js, template_vars, Layout Planner sub-agent

Additionally, 6 dead V8 files, 30+ stale references across skills/scripts, and missing quality metadata in doc_type_catalog.json mean the agent will constantly fight contradictory instructions.

**Bottom line: 14 critical issues, 15 warnings, 7 notes. Estimated fix effort: 1 focused session.**

---

## V9 TECHNICAL LESSONS (hard-won, never forget)

These were discovered through production failures and must be respected in every future modification:

### TL-01: Python `requests` DIES in WSL for long API calls
Any Anthropic API call >30 seconds fails silently via Python `requests` in WSL. The ONLY reliable method is **streaming curl via subprocess**:
```python
subprocess.run([
    'curl', '-s', '-S', '-N', '--max-time', '300',
    'https://api.anthropic.com/v1/messages',
    '-H', f'x-api-key: {api_key}',
    '-H', 'anthropic-version: 2023-06-01',
    '-H', 'content-type: application/json',
    '--data-binary', f'@{tmp_path}'  # NOT --data, must be --data-binary
], capture_output=True, text=True, timeout=310)
```
**Critical details:**
- `stream: True` in the payload — required for streaming SSE response
- `--data-binary @tempfile` — NOT `--data` (binary preserves encoding)
- `ensure_ascii=True` in `json.dumps()` — prevents UTF-8 issues in the tempfile
- Parse SSE events from stdout line by line (`data: {...}`)
- API key from `~/.openclaw/.env` (ANTHROPIC_API_KEY) or `~/.config/litellm/litellm.env`

**NEVER replace this with `requests`, `httpx`, `aiohttp`, or any Python HTTP library.** They all fail in WSL for calls >30s.

### TL-02: POI portrait sizing — 100px JPEG q70 is the sweet spot
Portraits are embedded as base64 in the Claude API prompt. Size matters enormously for cost:

| Size | Format | File size | Base64 tokens | Cost per image |
|------|--------|-----------|---------------|----------------|
| 200px PNG | PNG | ~80KB | ~20,000 | ~$0.06 |
| 100px JPEG q70 | JPEG | ~5KB | ~1,300 | ~$0.004 |

**That's a 15x cost reduction per portrait.** At 5 POIs per case, that's $0.30 → $0.02 for portraits alone.
`ai_render.py` must resize to 100px max width and convert to JPEG quality 70 before base64 encoding.

### TL-03: cost_tracker.py None-handling
`manifest.json` fields can be `None` from previous pipeline runs. Every numeric access must use:
```python
(totals.get('field') or 0)  # NOT totals['field'] or totals.get('field', 0)
```
The `or 0` pattern handles both missing keys AND explicit `None` values. `get('field', 0)` does NOT handle `None` — it only handles missing keys.

---

## V9 DECISIONS (recap for context)

| Decision | Old (V8) | New (V9) |
|----------|----------|----------|
| Rendering | 19 HTML templates + Handlebars + inject_and_render.js | ai_render.py → Claude Sonnet API → HTML → Chromium PDF |
| Image gen | 15-17 images per case (all types) | POI portraits ONLY (4-6 per case); all other visuals created in HTML/CSS by Claude |
| Doc types | Fixed 19 types in template_registry.json | Unlimited types via doc_type_catalog.json + design_hint |
| API calls | LiteLLM proxy (broken in WSL) | Direct Anthropic API via streaming curl (TL-01) |
| Type authority | template_registry.json (type_id 1-19) | doc_type_catalog.json (type_key strings) |
| Portrait size | 200px PNG (~$0.06/image) | 100px JPEG q70 (~$0.004/image) (TL-02) |

---

## CRITICAL ISSUES (14) — Must fix before next case

### C-01: ai_render.py experience_design lookup is completely broken
**File:** `cases/scripts/ai_render.py` lines 424-428
**Problem:** Looks for `experience.get('emotional_arc', experience.get('beats', []))` and iterates looking for doc_ids inside beat arrays. The actual structure is `experience['document_experience_map'][doc_id]` with fields `emotional_beat`, `detective_annotations`, `immersion_elements`.
**Impact:** ZERO documents receive emotional beats or detective annotation context during rendering. This is the single biggest quality gap — the entire Experience Designer phase produces output that is never consumed.
**Fix:** Replace experience_notes lookup with:
```python
doc_exp = experience.get('document_experience_map', {}).get(doc_id, {})
exp_notes = ''
if doc_exp:
    parts = []
    beat = doc_exp.get('emotional_beat', '')
    if beat:
        parts.append(f'EMOTIONAL BEAT: {beat}')
    annotations = doc_exp.get('detective_annotations', [])
    if annotations:
        parts.append('DETECTIVE ANNOTATIONS:')
        for ann in annotations:
            parts.append(f'  [{ann.get("type")}] {ann.get("content")} (position: {ann.get("position")}, style: {ann.get("style_hint")})')
    immersion = doc_exp.get('immersion_elements', [])
    if immersion:
        parts.append(f'IMMERSION ELEMENTS: {", ".join(immersion)}')
    exp_notes = '\n'.join(parts)
```

### C-02: AGENTS.md Phase 8 describes dead V8 pipeline
**File:** `AGENTS.md` lines 308-320
**Problem:** References Layout Planner sub-agent, Document Assembler, inject_and_render.js, template_vars JSON, CSS overlay annotations. None of this exists in V9.
**Impact:** If the agent follows AGENTS.md literally, Phase 8 will fail completely.
**Fix:** Rewrite Phase 8 to use `ai_render.py`:
```
### Phase 8: AI Render
1. Run: `exec python3 cases/scripts/ai_render.py cases/exports/<slug>/`
2. This renders ALL documents: reads _content.md + doc_type_catalog + experience_design → Claude API → HTML → PDF
3. Verify: each doc has .html and .pdf in layout_specs/, PDFs > 1KB
4. Merge per envelope: ai_render.py handles this automatically
5. Continue to Phase 9
```

### C-03: Narrative Architect constrains type_keys to template_registry.json
**File:** `skills/narrative-architect/SKILL.md` lines 20, 521, 559
**Problem:** Says `type_key MUST exist in template_registry.json` and self-check says `Every type_key exists in template_registry.json`. This locks the Narrative Architect to the 19 V8 types and blocks V9's unlimited types via design_hint.
**Impact:** Custom document types (e.g., `app_notification`, `bank_statement`, `parking_ticket`) will be rejected by the Narrative Architect's self-check, preventing V9 extensibility.
**Fix:** Replace all 3 references with `doc_type_catalog.json`. Add: "If type_key is not in doc_type_catalog, add a `design_hint` field (≥30 chars) describing the visual feel. Claude will render any type."

### C-04: validate_narrative.py rejects custom type_keys
**File:** `cases/scripts/validate_narrative.py` line 293
**Problem:** `fail(f"Document {did}: type_key '{type_key}' not found in template_registry")` — hard FAIL for any type_key not in the 19 registered types.
**Impact:** Even if the Narrative Architect produces a custom type with design_hint, the validator blocks the pipeline.
**Fix:** Change to: if type_key not in template_registry AND doc has no design_hint → WARN. If has design_hint → PASS.

### C-05: content-distribution SKILL.md references inject_and_render.js
**File:** `skills/content-distribution/SKILL.md` line 28
**Problem:** Still says `Run: node cases/render/inject_and_render.js` for rendering.
**Impact:** Distribution agent tries to use dead V8 rendering pipeline.
**Fix:** Replace rendering section with reference to ai_render.py output (HTMLs and PDFs already in layout_specs/).

### C-06: Art Director references template_registry for image decisions
**File:** `skills/art-director/SKILL.md` lines 22, 30, 65, 173
**Problem:** Uses `needs_image: true` from template_registry.json to decide which docs need images. In V9, POI portraits are the ONLY pre-generated images. All other visuals are HTML/CSS.
**Impact:** Art Director plans 15-17 images when only 4-6 POI portraits are needed, wasting Gemini/DALL-E budget.
**Fix:** Rewrite image planning: Art Director produces POI portrait briefs ONLY. Scene descriptions remain (used by Production Engine for narrative writing). Remove non-POI image briefs. Update self-check.

### C-07: doc_type_catalog.json missing quality metadata
**File:** `cases/config/doc_type_catalog.json`
**Problem:** No `min_narrative_words`, no `needs_image`, no `type_id` mapping. Multiple downstream consumers (validate_content.py, validate_art.py, production-engine, experience-designer) need this data and currently fall back to template_registry.json.
**Impact:** Quality floors aren't enforced for custom types. Art Director has no image planning data.
**Fix:** Add to each type in doc_type_catalog: `min_narrative_words`, `quality_notes`. Remove `needs_image` (V9: only POIs get pre-gen images). Remove `type_id` (V9 uses type_key strings).

### C-08: validate_content.py reads quality floors from template_registry
**File:** `cases/scripts/validate_content.py` lines 92, 106
**Problem:** Falls back to template_registry for min_narrative_words. Custom types get no quality floor check.
**Fix:** Read from doc_type_catalog.json. Fallback: if type not found, use 100 words minimum.

### C-09: validate_art.py validates against template_registry
**File:** `cases/scripts/validate_art.py` lines 68, 104
**Problem:** Checks which docs need images based on template_registry `needs_image`. In V9, only POI portraits are pre-generated.
**Fix:** Rewrite: validate that every POI has exactly one canonical portrait brief. Warn (not fail) if non-POI briefs are present (legacy tolerance).

### C-10: validate_document.py is dead code that could confuse agent
**File:** `cases/scripts/validate_document.py`
**Problem:** Expects template_vars JSON (V8 format). AGENTS.md doesn't reference it, but TOOLS.md does. validate_content.py is the actual V9 validator.
**Impact:** Agent might call the wrong validator.
**Fix:** Delete or rename to `validate_document_v8_DEPRECATED.py`.

### C-11: TOOLS.md lists dead V8 tools as current
**File:** `TOOLS.md`
**Problem:** Lists inject_and_render.js, doc_type_mapping.js, validate_document.py, HTML templates as current tools. References `cases/templates/html/` which doesn't even exist in workspace.
**Impact:** Agent follows stale tool documentation.
**Fix:** Rewrite Render pipeline section for V9.

### C-12: Production Engine and Experience Designer reference template_registry
**Files:** `skills/production-engine/SKILL.md` line 25, `skills/experience-designer/SKILL.md` lines 25, 110
**Problem:** Both read template_registry for quality floors and reading time estimates.
**Fix:** Change references to doc_type_catalog.json. For reading time, use actual _content.md word counts or estimates from doc_type_catalog.

### C-13: ai_render.py POI image sizing wastes 15x tokens per portrait
**File:** `cases/scripts/ai_render.py` lines 53-55, 107-132
**Problem:** `POI_IMAGE_MAX_WIDTH = 200` and encodes as PNG. A 200px PNG = ~80KB = ~20K tokens = ~$0.06 per image. At 5 POIs × 4 docs using portraits = 20 embeddings = $1.20 just in portrait tokens.
**Impact:** Portrait token cost alone can exceed the target $2/case rendering budget.
**Fix:** Change to 100px max width, JPEG quality 70:
```python
POI_IMAGE_MAX_WIDTH = 100

def resize_image_to_base64(image_path, max_width=600):
    # ... existing resize logic ...
    # Force JPEG output for portraits (much smaller than PNG)
    buf = BytesIO()
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(buf, format='JPEG', quality=70)
    data = base64.b64encode(buf.getvalue()).decode()
    return f'data:image/jpeg;base64,{data}'
```
**Cost impact:** $0.06 → $0.004 per portrait embedding. 15x reduction. See TL-02.

### C-14: cost_tracker.py crashes on None values in manifest.json
**File:** `cases/scripts/cost_tracker.py`
**Problem:** Previous pipeline runs can leave `None` values in manifest.json cost_tracking fields (e.g., `"estimated_cost_usd": null`). Standard `dict.get('field', 0)` does NOT handle explicit `None` — it returns `None` because the key exists. Arithmetic on `None` crashes.
**Impact:** cost_tracker crashes mid-pipeline, blocking render progress.
**Fix:** Every numeric access must use `(totals.get('field') or 0)` pattern. The `or 0` handles both missing keys AND explicit None. See TL-03.

### C-15: ai_render.py sends ALL images, not just POI portraits
The resolve_images_for_doc function was updated today to filter POI-only, but the update_tiers.py script may not have applied cleanly. Claude Code needs to verify the function only returns images where 'poi_' in fn.lower().
### C-16: ai_render.py Tier 1 prompt is still too expensive for interviews
B1 (interrogation_transcript) cost $2.19 — same as visual docs. The two-tier system was added but needs verification. Tier 1 docs should use a ~500 char system prompt, NOT the full design system JSON.
---

## WARNINGS (15) — Should fix before next case

### W-01: 6 dead V8 files still in workspace
- `cases/scripts/build_layout_specs.py` (894 lines)
- `cases/scripts/hybrid_render.py`
- `cases/render/inject_and_render.js`
- `cases/render/mini-handlebars.js`
- `cases/render/doc_type_mapping.js`
- `cases/render/html_to_pdf.js`

**Fix:** Delete all 6. They're V8 artifacts that add confusion.

### W-02: MEMORY.md says V8.4, references build_layout_specs as "operational"
**Fix:** Update to V9. Remove build_layout_specs reference.

### W-03: IDENTITY.md says V8.4
**Fix:** Update to V9.

### W-04: model_routing.json disconnected from ai_render.py
**Problem:** model_routing uses LiteLLM model names (`litellm/gemini31pro-thinking`). ai_render.py hardcodes `claude-sonnet-4-6` via direct Anthropic API. The agent_reasoning_map for `layout-planner` and `document-assembler` references agents that don't exist in V9.
**Fix:** Add `document-renderer` entry to agent_reasoning_map. Remove `layout-planner` and `document-assembler`. Consider making ai_render.py read model from model_routing or accept --model flag (it already does, but default is `claude-sonnet46` which doesn't match).

### W-05: ai_render.py DEFAULT_MODEL is 'claude-sonnet46' (wrong format)
**File:** `cases/scripts/ai_render.py` line 53
**Problem:** DEFAULT_MODEL = 'claude-sonnet46' but call_litellm hardcodes 'claude-sonnet-4-6'. The --model flag uses DEFAULT_MODEL but call_litellm ignores it.
**Fix:** Make call_litellm use the model parameter. Set DEFAULT_MODEL = 'claude-sonnet-4-6'.

### W-06: ai_render.py still loads template_registry (graceful fail)
**Problem:** Doesn't crash if missing, but loads it unnecessarily.
**Fix:** Remove template_registry loading. Only load doc_type_catalog.json and design_system.json.

### W-07: start_new_case.sh checks for template_registry.json
**File:** `cases/scripts/start_new_case.sh` line 24
**Fix:** Replace with doc_type_catalog.json in the pre-flight check.

### W-08: validate_final.py reads template_registry
**File:** `cases/scripts/validate_final.py` line 107
**Fix:** Switch to doc_type_catalog.json for any type lookups.

### W-09: design_system.json dumped in full on every Tier 2 render call
**Problem:** ~2K tokens of design_system JSON in every system prompt. 20 docs = 40K extra input tokens = ~$0.12 wasted.
**Fix:** Condense design_system into a shorter prompt section. Only include relevant portions per doc type.

### W-10: No rendering instructions for detective annotations in ai_render.py
**Problem:** Even after C-01 fix, the annotations are passed as text context but the system prompt never instructs Claude to RENDER them as visual overlays (sticky notes, margin comments, highlights). The document-designer SKILL.md mentions it but ai_render.py's system prompt doesn't.
**Fix:** Add annotation rendering instructions to build_system_prompt() for Tier 2.

### W-11: Art Director canonical portrait path inconsistency
**Problem:** SKILL.md says `visuals/canonical/poi_XX_name.png` but briefs use `visuals/envelope_<X>/final/` for filename field, with separate `library_path: "canonical/..."` only for reuse.
**Fix:** Standardize: all POI portraits save to `visuals/canonical/`, art_briefs filename reflects this.

### W-12: Narrative Architect type_id still used alongside type_key
**Problem:** clue_catalog skeleton requires both `type_id` (numeric) and `type_key` (string). In V9 with unlimited types, type_id is meaningless for custom types.
**Fix:** Make type_id optional in skeleton. Validators should use type_key as primary identifier.

### W-13: Resolution envelope doc count validation
**Problem:** Narrative Architect self-check says "one doc per POI in R" but this means R envelope can have 4-8 docs (one per POI). For player experience, this might be excessive. Consider: 1 prosecutor summary + 1 clearance memo per non-culprit, combined (as in Linda Oward benchmark case).
**Fix:** Add flexibility note: R envelope should provide closure for each POI but can combine non-culprits into fewer docs.

### W-14: No SKILL.md for the V9 rendering phase
**Problem:** document-designer SKILL.md only handles visual types (social_posts, evidence_mosaic, etc.). There's no skill that describes the full V9 rendering pipeline. ai_render.py IS the pipeline, but the orchestrator has no skill to reference.
**Fix:** Either expand document-designer into a comprehensive V9 rendering skill, or create a new `ai-renderer/SKILL.md` that documents the full process.

### W-15: design_system.json handwritten font is Comic Sans MS — visual quality killer
**File:** `cases/config/design_system.json` → `typography.handwritten`
**Problem:** Comic Sans MS is the current handwriting font. For printed case files where detective annotations, sticky notes, and margin comments are a *core quality differentiator*, Comic Sans destroys immersion. This directly impacts your quality dimensions 1 (UX) and 6 (Document as Experience).
**Impact:** Every detective annotation, every sticky note, every handwritten margin comment looks like a joke instead of a real detective's notes.
**Fix:** Change to Google Fonts "Caveat" (or "Patrick Hand" as fallback). ai_render.py's generated HTML can import it at zero cost:
```css
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;700');
```
Update design_system.json:
```json
"handwritten": "'Caveat', 'Patrick Hand', cursive"
```
Claude's system prompt should reference this font for all annotation/handwritten elements.


### W-16: render_all.sh is dead — delete it
Listed in render/ but not in the delete table.
### W-17: content_patch_last_livestream.py is case-specific dead code
Should be deleted — it's a one-time patch for Case 1.
N-08 should be renamed to N-09: The report already has N-07 as "No Spanish language support" but the original had N-07 as "Comic Sans" and N-08 as "No Spanish." The numbering shifted when Comic Sans was promoted to W-15. Minor but Claude Code might get confused.

---

## NOTES (7) — Nice to have

### N-01: lessons_learned.json references inject_and_render.js (entry about output paths)
Lower priority — won't break pipeline. Update at next lessons_learned refresh.

### N-02: Nano Banana SKILL.md references gemini-3.1-flash-image-preview
Verify this model is still available. Gemini API changes frequently.

### N-03: Cost tracking inconsistency
manifest.json shows "document-designer" as agent for render costs. V9 should use "ai-renderer".

### N-04: validate_placeholders.py checks for Handlebars {{ }} markers
Still useful as a safety net (catches if any V8 artifacts leak through), but the specific check for `{CONTENT_FROM_MD_FILE}` is V8-specific.

### N-05: Quality benchmark scoring could be weighted toward UX
Your quality framework puts User Experience as "most important." Current benchmark weights UX at 2x (20/55 = 36% of score). Consider 2.5x or 3x to match stated priority.

### N-06: Clue proximity rule exists in tier_definitions but only enforced for NORMAL
Experience Designer checks proximity for all tiers, but only NORMAL tier_definitions mentions `clue_proximity_rule`.

### N-07: No Spanish language support path
All skills say "ALL OUTPUTS MUST BE IN US ENGLISH." For a Spanish-speaking market, a language parameter would be needed. Low priority but worth noting.

---

## FILES TO DELETE (V9 cleanup)

| File | Reason |
|------|--------|
| `cases/scripts/build_layout_specs.py` | V8 Layout Planner — replaced by ai_render.py |
| `cases/scripts/hybrid_render.py` | V8.5 hybrid renderer — replaced by ai_render.py |
| `cases/render/inject_and_render.js` | V8 template injector — dead |
| `cases/render/mini-handlebars.js` | V8 Handlebars engine — dead |
| `cases/render/doc_type_mapping.js` | V8 type→template map — dead |
| `cases/render/html_to_pdf.js` | V8 PDF renderer — replaced by render_pdf_system_chromium.js |
| `cases/scripts/validate_document.py` | V8 template_vars validator — replaced by validate_content.py |

Keep `cases/render/render_pdf_system_chromium.js` (used by ai_render.py) and `cases/render/merge_pdfs.js` (used for envelope merging).

---

## PRIORITIZED FIX ORDER (15 steps)

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | **C-01:** Fix ai_render.py experience_design lookup | 10 min | Unlocks emotional beats + annotations in rendering |
| 2 | **C-13:** Fix POI image sizing (100px JPEG q70) | 10 min | 15x cost reduction per portrait ($0.06→$0.004) |
| 3 | **C-14:** Fix cost_tracker.py None-handling | 5 min | Stops mid-pipeline crashes |
| 4 | **C-02:** Rewrite AGENTS.md Phase 8 for V9 | 15 min | Pipeline can execute Phase 8 correctly |
| 5 | **C-03 + C-04:** Update Narrative Architect + validate_narrative.py for unlimited types | 20 min | Unlocks V9 extensibility |
| 6 | **C-07:** Add quality metadata to doc_type_catalog.json | 15 min | Quality floors enforced for all types |
| 7 | **C-08 + C-09 + W-08:** Update all validators to use doc_type_catalog | 20 min | Validators aligned with V9 |
| 8 | **C-06:** Update Art Director for POI-only images | 15 min | Stops wasting image budget |
| 9 | **C-05 + C-11 + C-12:** Update content-distribution, TOOLS.md, Production Engine, Experience Designer | 15 min | All downstream skills aligned |
| 10 | **W-01:** Delete 7 dead files | 2 min | Removes confusion |
| 11 | **W-02 + W-03:** Update MEMORY.md, IDENTITY.md to V9 | 2 min | Agent self-awareness |
| 12 | **W-04 + W-05:** Fix model_routing alignment with ai_render.py | 10 min | Model selection consistent |
| 13 | **W-10:** Add annotation rendering instructions to ai_render.py prompts | 15 min | Detective annotations actually appear in PDFs |
| 14 | **W-15:** Replace Comic Sans with Caveat in design_system.json | 5 min | Annotation quality jump for zero cost |
| 15 | **W-07:** Update start_new_case.sh | 2 min | Init script aligned |

**Total estimated effort: ~2.5 hours of focused work.**

---

## V9 DATA FLOW (corrected)

```
case_config.json
    ↓
[Narrative Architect] → case-plan.json + clue_catalog.json
    ↓                    (type_keys from doc_type_catalog.json, custom types via design_hint)
[Art Director] → art_briefs.json (POI portraits ONLY) + scene_descriptions.json
    ↓
[Experience Designer] → experience_design.json
    ↓                    (document_experience_map with emotional_beat + detective_annotations)
[Production Engine] → envelope_X/XX_content.md (per document)
    ↓                  (reads experience_design for emotional beats, scene_descriptions for visual context)
[Quality Auditor: playthrough] → playthrough_report.json
    ↓
[Image Generator] → visuals/canonical/poi_XX_name.png (POI portraits only, 100px JPEG q70)
    ↓
[ai_render.py] → layout_specs/XX.html + XX.pdf (per document)
    ↓              reads: _content.md + doc_type_catalog + design_system + experience_design + POI images (base64, ~1.3K tokens each)
    ↓              Claude Sonnet generates full HTML with: content + visual design + annotations + immersion elements + Caveat font for handwriting
    ↓              Chromium renders HTML → PDF
    ↓              API calls via streaming curl (TL-01) — NEVER Python requests
    ↓              Merges PDFs per envelope → final/Envelope_X.pdf
    ↓
[Content Distribution] → ZIP → Google Drive → Telegram
```

### Key V9 contracts:

| Producer | File | Consumer | Critical fields |
|----------|------|----------|-----------------|
| Narrative Architect | clue_catalog.json | All downstream | doc_id, type_key, design_hint (custom types), production_brief_writing |
| Narrative Architect | case-plan.json | All downstream | pois, timeline, contradictions, emotional_arc, experiential_style |
| Art Director | art_briefs.json | ai_render.py | briefs[].usage_map (POI portraits → doc_id mapping) |
| Art Director | scene_descriptions.json | Production Engine | Visual context for narrative writing |
| Experience Designer | experience_design.json | Production Engine + ai_render.py | document_experience_map[doc_id].emotional_beat, .detective_annotations, .immersion_elements |
| Production Engine | envelope_X/XX_content.md | ai_render.py | Full narrative content as markdown |
| doc_type_catalog.json | (config) | Narrative Architect + ai_render.py | types[type_key].feel, .layout, .typography, .special_elements |
| design_system.json | (config) | ai_render.py | Page setup, typography, colors, stamps, effects |

---

## YOUR QUALITY FRAMEWORK → PIPELINE MAPPING

You defined 6 dimensions of excellent output. Here's where each is enforced:

| Your Dimension | Pipeline Enforcement Point |
|----------------|--------------------------|
| **1. User Experience (most important)** — aha moments, suspense, immersion, conflicting emotions, catharsis | Experience Designer (emotional_beat per doc), Production Engine (writes toward beat), Quality Auditor playthrough (Pillar 1, 2x weight), **ai_render.py annotations (CURRENTLY BROKEN — C-01)** |
| **2. Relevant information** | Narrative Architect (document_justification per doc), Quality Auditor narrative_quality (document selection check), tier_definitions anti-patterns |
| **3. Structured clue presentation** | Experience Designer (clue_proximity_check), tier_definitions (clue_proximity_rule for NORMAL), Narrative Architect (evidence_chain steps), envelope themes |
| **4. Visual support** | Art Director (POI portraits), ai_render.py (doc_type_catalog visual designs, immersion_elements), design_system.json (stamps, textures, effects), **W-10: annotation rendering needs fix** |
| **5. Dynamic clue variety** | Narrative Architect (min_unique_template_types), tier_definitions (multiplier_types), V9 unlimited types via design_hint |
| **6. Documents as experience** | Experience Designer (detective_annotations, immersion_elements), Production Engine (emotional beat targeting), **ai_render.py must render annotations visually (W-10)** |

**Critical gap:** Dimensions 1, 4, and 6 all depend on ai_render.py correctly consuming experience_design.json. Fix C-01 and W-10 unlocks all three.

---

## NEXT STEPS

After applying fixes in priority order:

1. **Test run:** Generate a SHORT case to validate the full V9 pipeline end-to-end
2. **Score it:** Use the 6-pillar benchmark. Target ≥75% (45/60).
3. **Compare:** Print a doc from Case 2 (broken annotations) vs the test case (fixed) — the visual quality difference should be dramatic
4. **Iterate:** The test case will surface any remaining issues in the actual API interaction (token limits, streaming, prompt quality)
