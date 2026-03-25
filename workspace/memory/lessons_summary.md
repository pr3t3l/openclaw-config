# Declassified Pipeline — Lessons Learned

Source: workspace-declassified/cases/config/lessons_learned.json
Last synced: 2026-03-23

---

## Anti-Patterns (NEVER do these)

- Never use `some_type` as type_key — always use exact key from template_registry.json
- Never use `Reveals something about DOC-XX` — always write the actual revelation
- Never use `Player infers something` — always write the actual player inference
- Never use `Write this doc.` as a production brief summary
- Never use `Info` as key_information_to_include
- Never use `Internal QC anchor for DOC-XX` as key_mandatory_line
- Never count template/form field words toward content quality minimums
- Never include HTML tags (`<p>`, `<div>`) in _content.md files — use plain Markdown only
- Never retry with identical parameters — always include failure diagnosis in retry prompt
- Never include a document type that doesn't serve the story
- Never hardcode case-specific data in HTML templates — all content comes from JSON vars
- Normalize all interview subject lines to established POI IDs
- Verify timeline source_docs and contradiction doc IDs match the evidence exactly

---

## Model Notes

- gemini31pro-thinking hits rate limits after ~15 spawns in 2 hours
- gpt52-thinking is a reliable fallback for playthrough QA and narrative architect
- nano-banana-2-gemini needs exponential backoff (2s, 5s, 10s) for RESOURCE_EXHAUSTED errors
- Sub-agents via sessions_spawn start with fresh context — token tracking per sub-agent is reliable
- Robotin main session context compounds with each spawn — keep orchestration messages concise

---

## Key Lessons by Phase

### Narrative Architect
- **LL-001**: Clue catalog entries must be as detailed as case-plan assignments. Stubs (generic reveals, inferences) will pass through to production undetected without validation.
- **LL-013**: Cross-references (contradictions, timeline, evidence_chain) must be re-linked after any document type conversion.
- **LL-015**: Same as LL-013 but specifically for doc type conversions mid-pipeline.
- **LL-016**: Trojan horse docs in early envelopes must have ambiguous reveals. The pivot doc (Envelope C) delivers the explicit detail.
- **LL-017**: Interview slips must be concrete and verifiable (specific device states, UI labels, physical details), not vague "knows too much" tells.

### Production Engine
- **LL-002**: SKILL.md must include exact JSON examples per document type. Without them, agents guess wrong.
- **LL-003**: Placeholder patterns (`{{CONTENT_FROM_MD_FILE}}`, `Internal QC anchor`) must be scanned and rejected.
- **LL-005**: Word count validation must count narrative words only, excluding form labels, headers, and template structure.
- **LL-012**: All interview subject lines must use established POI IDs consistently across envelopes.

### Art Director
- **LL-004**: Must produce briefs for ALL document types with needs_image=true, not just mugshots.
- **LL-008**: One canonical portrait per POI, reused across all documents. No separate generation per doc.
- **LL-009**: Victim image = normal portrait (headshot/candid), not mugshot, unless story requires it.
- **LL-010**: Art brief envelope must be one of {A,B,C,R}. for_doc must reference a real doc_id.
- **LL-011**: Art planning must include usage_notes mapping image → doc_id + template slot.
- **LL-018**: template_registry must mark all visual doc types as needs_image=true. Art Director self-checks coverage.

### Render / Layout
- **LL-006**: Templates must be 100% data-driven (Handlebars). No hardcoded sample content.
- **LL-019**: Render output goes to envelope_X/<doc_id>.html|pdf, not to layout_specs/.

### Infrastructure
- **LL-007**: Pre-flight check for required tools (zip, node, python3, chromium) before starting a case.

### Cost Tracking
- **LL-014**: Token/cost usage must be recorded after each sub-agent run. Totals must be non-zero for completed cases.
