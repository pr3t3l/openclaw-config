#!/usr/bin/env python3
"""
validate_narrative.py — Validates Narrative Architect output (V8)
Usage: python3 validate_narrative.py <case_dir>
Exit code: 0 = PASS, 1 = FAIL

Deterministic checks only (no LLM). Catches structural issues before
the LLM QA evaluates narrative quality.

V8 changes:
- Compatible with V8 tier_definitions (nested: pois.min, total_docs.min, etc.)
- Backward-compatible with V6 flat schema (min_pois, min_docs, etc.)
- Validates V8 experience fields (experiential_style, emotional_arc, trojan_horse_docs, social_media_plan, spatial_tool)
- Report header updated to V8
"""

import json
import re
import sys
from pathlib import Path

KNOWN_PLACEHOLDER_PATTERNS = [
    r'^reveals?\s+something',
    r'^player\s+infers?\s+something',
    r'^write\s+this\s+doc',
    r'^info$',
    r'^internal\s+qc\s+anchor',
    r'^document\s+\d+$',
    r'^some_type$',
    r'^tbd$',
    r'^\[fill\]$',
    r'^\[todo\]$',
]

VALID_PLAYER_PURPOSES = [
    'case_introduction', 'context_setting', 'clue_delivery',
    'red_herring', 'tension_builder', 'revelation', 'resolution'
]

VALID_EXPERIENTIAL_STYLES = ['physical_local', 'digital_corporate']


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_placeholder(text):
    """Check if text matches known placeholder patterns."""
    if not text:
        return True
    t = text.strip().lower()
    for pattern in KNOWN_PLACEHOLDER_PATTERNS:
        if re.match(pattern, t):
            return True
    return False


def tier_val(t, v8_key, v6_key, sub_key='min', default=None):
    """Read a tier value with V8 nested schema, falling back to V6 flat key."""
    # V8: t['pois']['min'] — accessed as tier_val(t, 'pois', 'min_pois', 'min')
    # V6: t['min_pois']
    v8_obj = t.get(v8_key)
    if isinstance(v8_obj, dict):
        return v8_obj.get(sub_key, default)
    # Flat fallback
    return t.get(v6_key, default)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_narrative.py <case_dir>")
        sys.exit(2)

    case_dir = Path(sys.argv[1])
    config_dir = case_dir.parent.parent / 'config'

    issues = []
    def fail(msg): issues.append(("FAIL", msg))
    def warn(msg): issues.append(("WARN", msg))

    # ── Load files ──────────────────────────────────────────────────────
    plan_path = case_dir / 'case-plan.json'
    catalog_path = case_dir / 'clue_catalog.json'
    manifest_path = case_dir / 'manifest.json'
    tier_path = config_dir / 'tier_definitions.json'
    registry_path = config_dir / 'template_registry.json'
    catalog_types_path = config_dir / 'doc_type_catalog.json'

    for p, name in [(plan_path, 'case-plan.json'), (catalog_path, 'clue_catalog.json'),
                     (manifest_path, 'manifest.json'), (tier_path, 'tier_definitions.json')]:
        if not p.exists():
            fail(f"Missing file: {name} at {p}")

    if any(i[0] == "FAIL" for i in issues):
        write_report(case_dir, issues)
        sys.exit(1)

    plan = load_json(plan_path)
    catalog = load_json(catalog_path)
    manifest = load_json(manifest_path)
    tiers = load_json(tier_path)
    registry = load_json(registry_path) if registry_path.exists() else {'templates': {}}
    doc_type_catalog = load_json(catalog_types_path) if catalog_types_path.exists() else {'types': {}}

    tier = plan.get('tier', manifest.get('tier', ''))
    if tier not in tiers:
        fail(f"Unknown tier: {tier}")
        write_report(case_dir, issues)
        sys.exit(1)

    t = tiers[tier]
    # V9: valid types come from doc_type_catalog (primary) + template_registry (legacy)
    valid_type_keys = set(doc_type_catalog.get('types', {}).keys())
    valid_type_keys |= {v['type_key'] for v in registry.get('templates', {}).values()}

    # ── 1. Culprit ──────────────────────────────────────────────────────
    culprit = plan.get('culprit', {})
    if not culprit:
        fail("No culprit defined in case-plan.json")
    else:
        if not culprit.get('poi_id'):
            fail("Culprit missing poi_id")
        if not culprit.get('motive') or len(culprit.get('motive', '')) < 50:
            fail("Culprit motive missing or too short (<50 chars). Must be specific.")
        if not culprit.get('motive_specificity_test'):
            fail("Culprit missing motive_specificity_test")
        if not culprit.get('method_steps') or len(culprit.get('method_steps', [])) < 3:
            fail("Culprit needs at least 3 method_steps")
        if not culprit.get('the_almost'):
            fail("Culprit missing 'the_almost' (pivot clue)")

        poi_ids = [p['id'] for p in plan.get('pois', [])]
        if culprit.get('poi_id') and culprit['poi_id'] not in poi_ids:
            fail(f"Culprit poi_id '{culprit['poi_id']}' not found in POI list")

    # ── 2. POIs ─────────────────────────────────────────────────────────
    pois = plan.get('pois', [])
    min_pois = tier_val(t, 'pois', 'min_pois', 'min')
    max_pois = tier_val(t, 'pois', 'max_pois', 'max', default=99)

    if min_pois is None:
        fail("Tier definition missing POI minimum (expected pois.min or min_pois)")
    else:
        if len(pois) < min_pois:
            fail(f"POI count {len(pois)} < tier minimum {min_pois}")

    if len(pois) > max_pois:
        warn(f"POI count {len(pois)} > tier maximum {max_pois}")

    poi_map = {p['id']: p for p in pois}
    living_pois = [p for p in pois if p.get('status') in ('alive', 'unknown')]

    for poi in pois:
        if not poi.get('id') or not poi['id'].startswith('POI-'):
            fail(f"POI missing valid id (format: POI-XX): {poi.get('name', '?')}")
        if not poi.get('name') or len(poi.get('name', '')) < 3:
            fail(f"POI {poi.get('id', '?')} missing name")
        if not poi.get('role'):
            fail(f"POI {poi.get('id', '?')} missing role")
        if not poi.get('description') or len(poi.get('description', '')) < 20:
            warn(f"POI {poi.get('id', '?')} description too short (<20 chars)")
        if not poi.get('voice_profile'):
            warn(f"POI {poi.get('id', '?')} missing voice_profile")
        elif not all(k in poi['voice_profile'] for k in ('speech_pattern', 'under_pressure', 'verbal_tics')):
            warn(f"POI {poi.get('id', '?')} voice_profile incomplete (need speech_pattern, under_pressure, verbal_tics)")

    for poi in living_pois:
        if not poi.get('interview_doc'):
            fail(f"Living POI {poi['id']} ({poi.get('name', '?')}) has no interview_doc assigned")

    # ── 3. Timeline ─────────────────────────────────────────────────────
    timeline = plan.get('timeline', [])
    if len(timeline) < 8:
        fail(f"Timeline has only {len(timeline)} events (minimum 8)")

    for i, evt in enumerate(timeline):
        if not isinstance(evt, dict):
            fail(f"Timeline event {i} is {type(evt).__name__} — must be object with datetime/event/source_docs")
            continue
        if not evt.get('source_docs'):
            fail(f"Timeline event {i} has no source_docs: {evt.get('event', '?')[:50]}")
        if not evt.get('datetime'):
            fail(f"Timeline event {i} has no datetime")

    critical = [e for e in timeline if isinstance(e, dict) and e.get('is_critical_period')]
    if len(critical) < 3:
        warn(f"Only {len(critical)} events marked as critical period (recommend ≥5)")

    # ── 4. Contradictions ───────────────────────────────────────────────
    contras = plan.get('contradictions', [])
    min_contras = tier_val(t, 'contradictions', 'min_contradictions', 'min')

    if min_contras is None:
        fail("Tier definition missing contradiction minimum")
    else:
        if len(contras) < min_contras:
            fail(f"Contradiction count {len(contras)} < tier minimum {min_contras}")

    docs_in_catalog = {d['doc_id'] for d in catalog.get('documents', [])}
    doc_envelope_map = {d['doc_id']: d.get('envelope', '') for d in catalog.get('documents', [])}

    for i, c in enumerate(contras):
        if not isinstance(c, dict):
            fail(f"Contradiction {i+1} is {type(c).__name__} — must be object with id/what/introduced_in/resolved_in/player_inference")
            continue
        if not c.get('id') or not c['id'].startswith('CONTRA-'):
            fail(f"Contradiction missing valid id: {c}")
        if not c.get('what') or len(c.get('what', '')) < 20:
            fail(f"Contradiction {c.get('id', '?')} 'what' too vague (<20 chars)")
        if not c.get('introduced_in'):
            fail(f"Contradiction {c.get('id', '?')} missing introduced_in")
        if not c.get('resolved_in'):
            fail(f"Contradiction {c.get('id', '?')} missing resolved_in")
        if not c.get('player_inference'):
            fail(f"Contradiction {c.get('id', '?')} missing player_inference")
        if c.get('introduced_in') and c['introduced_in'] not in docs_in_catalog:
            warn(f"Contradiction {c['id']}: introduced_in '{c['introduced_in']}' not in clue_catalog")
        if c.get('resolved_in') and c['resolved_in'] not in docs_in_catalog:
            warn(f"Contradiction {c['id']}: resolved_in '{c['resolved_in']}' not in clue_catalog")

    late_envelopes = {'C', 'D', 'R'}
    late_resolved = any(
        doc_envelope_map.get(c.get('resolved_in', ''), '') in late_envelopes
        for c in contras
    )
    if not late_resolved and tier != 'SHORT':
        fail("No contradiction resolves in envelope C or later (progression lock missing)")

    # ── 5. Evidence Chain ───────────────────────────────────────────────
    chain = plan.get('evidence_chain', [])
    if len(chain) < 6:
        fail(f"Evidence chain has only {len(chain)} steps (minimum 6)")

    for i, step in enumerate(chain):
        if isinstance(step, str):
            fail(f"Evidence chain step {i+1} is a plain string — must be object with step/docs_needed/reveals. Run fix_case_plan_schema.py to auto-fix.")
            break  # No point checking further if format is wrong
        elif isinstance(step, dict):
            if not step.get('docs_needed'):
                fail(f"Evidence chain step {step.get('step', i+1)} has no docs_needed")
            if not step.get('reveals'):
                fail(f"Evidence chain step {step.get('step', i+1)} has no reveals")
        else:
            fail(f"Evidence chain step {i+1} is unexpected type {type(step).__name__} — must be object")

    # ── 6. Envelopes ────────────────────────────────────────────────────
    envelopes = plan.get('envelopes', {})
    required_envs = t['envelopes']
    for env in required_envs:
        if env not in envelopes:
            fail(f"Missing envelope {env} (required for tier {tier})")
        elif not envelopes[env].get('docs'):
            fail(f"Envelope {env} has no docs assigned")

    if 'R' not in envelopes:
        fail("Resolution envelope (R) missing — must always be separate")

    total_docs = sum(len(e.get('docs', [])) for e in envelopes.values())
    min_docs = tier_val(t, 'total_docs', 'min_docs', 'min')
    max_docs = tier_val(t, 'total_docs', 'max_docs', 'max', default=999)

    if min_docs is None:
        fail("Tier definition missing document minimum")
    else:
        if total_docs < min_docs:
            fail(f"Total document count {total_docs} < tier minimum {min_docs}")
    if total_docs > max_docs:
        warn(f"Total document count {total_docs} > tier maximum {max_docs}")

    # ── 7. Clue Catalog Quality (THE CRITICAL CHECK) ────────────────────
    docs = catalog.get('documents', [])
    if min_docs is not None and len(docs) < min_docs:
        fail(f"Clue catalog has {len(docs)} docs, tier requires minimum {min_docs}")

    sequence_by_envelope = {}

    for doc in docs:
        did = doc.get('doc_id', '?')
        tid = doc.get('type_id')
        tid_str = str(tid) if tid is not None else None
        type_key = doc.get('type_key', '')
        envelope = doc.get('envelope', '')

        # Basic fields
        if not doc.get('doc_id'):
            fail("Document missing doc_id")
            continue
        if not doc.get('envelope'):
            fail(f"Document {did} missing envelope")
        if not doc.get('type_id'):
            fail(f"Document {did} missing type_id")

        # type_key must be in catalog or have design_hint for custom types
        if not type_key:
            fail(f"Document {did}: missing type_key")
        elif type_key not in valid_type_keys:
            design_hint = doc.get('design_hint', '')
            if design_hint and len(design_hint) >= 30:
                pass  # Custom type with valid design_hint — OK for V9
            elif design_hint:
                warn(f"Document {did}: custom type_key '{type_key}' design_hint too short ({len(design_hint)} chars, need >=30)")
            else:
                warn(f"Document {did}: type_key '{type_key}' not in doc_type_catalog and no design_hint provided")

        # type_id must match type_key in registry
        if tid_str and tid_str in registry.get('templates', {}):
            expected_key = registry['templates'][tid_str].get('type_key', '')
            if type_key and type_key != expected_key:
                fail(f"Document {did}: type_key '{type_key}' doesn't match type_id {tid} (expected '{expected_key}')")

        # in_world_title must be real
        title = doc.get('in_world_title', '')
        if not title or len(title) < 5:
            fail(f"Document {did} missing in_world_title")
        if is_placeholder(title):
            fail(f"Document {did}: in_world_title is a placeholder: '{title}'")

        # reveals must be specific
        reveals = doc.get('reveals', '')
        if not reveals or len(reveals) < 30:
            fail(f"Document {did}: 'reveals' too short (<30 chars): '{reveals[:50]}'")
        if is_placeholder(reveals):
            fail(f"Document {did}: 'reveals' is a placeholder: '{reveals[:50]}'")

        # player_inference must be specific
        pi = doc.get('player_inference', '')
        if not pi or len(pi) < 20:
            fail(f"Document {did}: 'player_inference' too short (<20 chars)")
        if is_placeholder(pi):
            fail(f"Document {did}: 'player_inference' is a placeholder: '{pi[:50]}'")

        # sequence_number
        seq = doc.get('sequence_number')
        if seq is None:
            fail(f"Document {did} missing sequence_number")
        else:
            env_key = envelope
            if env_key not in sequence_by_envelope:
                sequence_by_envelope[env_key] = {}
            if seq in sequence_by_envelope[env_key]:
                fail(f"Document {did}: duplicate sequence_number {seq} in envelope {env_key} (conflicts with {sequence_by_envelope[env_key][seq]})")
            else:
                sequence_by_envelope[env_key][seq] = did

        # player_purpose
        purpose = doc.get('player_purpose', '')
        if not purpose or purpose not in VALID_PLAYER_PURPOSES:
            fail(f"Document {did}: player_purpose '{purpose}' invalid. Must be one of: {VALID_PLAYER_PURPOSES}")

        # document_justification
        justification = doc.get('document_justification', '')
        if not justification or len(justification) < 20:
            warn(f"Document {did}: missing or short document_justification (<20 chars)")

        # production_brief_writing
        brief = doc.get('production_brief_writing')
        if not brief:
            fail(f"Document {did} missing production_brief_writing")
        else:
            kml = brief.get('key_mandatory_line', '')
            if not kml or len(kml) < 20:
                fail(f"Document {did}: key_mandatory_line missing or too short (<20 chars)")
            if is_placeholder(kml):
                fail(f"Document {did}: key_mandatory_line is a placeholder: '{kml[:60]}'")

            summary = brief.get('summary', '')
            if is_placeholder(summary):
                fail(f"Document {did}: production_brief summary is a placeholder: '{summary[:50]}'")

            info_list = brief.get('key_information_to_include', [])
            if info_list and len(info_list) == 1 and is_placeholder(str(info_list[0])):
                fail(f"Document {did}: key_information_to_include has placeholder entries")

        # Interview briefs (type 11)
        if str(tid) == '11':
            ib = doc.get('production_brief_interview')
            if not ib:
                fail(f"Interview {did} missing production_brief_interview")
            else:
                if not ib.get('subject_poi_id'):
                    fail(f"Interview {did} missing subject_poi_id")
                elif ib['subject_poi_id'] not in poi_map:
                    fail(f"Interview {did} subject_poi_id '{ib['subject_poi_id']}' not in POI list")
                if not ib.get('phases') or len(ib.get('phases', [])) < 3:
                    fail(f"Interview {did} has <3 phases")
                if not ib.get('min_exchanges') or ib.get('min_exchanges', 0) < 14:
                    fail(f"Interview {did} min_exchanges <14")
                if not ib.get('the_lie'):
                    fail(f"Interview {did} missing 'the_lie'")
                if not ib.get('the_slip') or not ib['the_slip'].get('what'):
                    fail(f"Interview {did} missing 'the_slip' details")

        # 911 briefs (type 6)
        if str(tid) == '6':
            nb = doc.get('production_brief_911')
            if not nb:
                fail(f"911 transcript {did} missing production_brief_911")
            else:
                if not nb.get('caller_emotional_arc') or len(nb.get('caller_emotional_arc', [])) < 3:
                    fail(f"911 {did} caller_emotional_arc needs ≥3 phases")
                if not nb.get('min_exchanges') or nb.get('min_exchanges', 0) < 10:
                    fail(f"911 {did} min_exchanges <10")
                if not nb.get('key_revelation_moment'):
                    fail(f"911 {did} missing key_revelation_moment")

        # Newspaper briefs (type 4, 12)
        if str(tid) in ('4', '12'):
            np_brief = doc.get('production_brief_newspaper')
            if not np_brief:
                warn(f"Newspaper {did} missing production_brief_newspaper")
            else:
                if not np_brief.get('angle'):
                    warn(f"Newspaper {did} missing angle")
                if not np_brief.get('quotes') or len(np_brief.get('quotes', [])) < 2:
                    warn(f"Newspaper {did} needs ≥2 quotes")
                if not np_brief.get('planted_clue'):
                    warn(f"Newspaper {did} missing planted_clue")

    # ── 8. Mandatory docs check ─────────────────────────────────────────
    mandatory = t.get('mandatory_docs', [])
    for m in mandatory:
        seq = m.get('sequence')
        purpose = m.get('purpose')
        if seq:
            found = False
            for doc in docs:
                if doc.get('envelope') == 'A' and doc.get('sequence_number') == seq:
                    found = True
                    if m.get('type_id') and str(doc.get('type_id')) != str(m['type_id']):
                        fail(f"Mandatory doc at sequence {seq} must be type_id {m['type_id']} but is {doc.get('type_id')}")
                    if purpose and doc.get('player_purpose') != purpose:
                        warn(f"Mandatory doc at sequence {seq} should have player_purpose='{purpose}' but has '{doc.get('player_purpose')}'")
                    break
            if not found:
                fail(f"Mandatory doc at sequence {seq} (purpose: {purpose}) not found in Envelope A")

    # ── 9. Resolution envelope check ────────────────────────────────────
    resolution_docs = [d for d in docs if d.get('envelope') == 'R']
    living_poi_ids = {p['id'] for p in living_pois}
    resolution_poi_ids = set()
    for doc in resolution_docs:
        if doc.get('player_purpose') == 'resolution':
            refs = doc.get('pois_referenced', [])
            resolution_poi_ids.update(refs)

    for poi in pois:
        pid = poi['id']
        if pid not in resolution_poi_ids:
            warn(f"POI {pid} ({poi.get('name', '?')}) has no resolution document in Envelope R")

    # ── 10. V8 Experience Layer Checks ──────────────────────────────────
    # experiential_style
    exp_style = plan.get('experiential_style')
    if not exp_style:
        warn("V8: missing experiential_style in case-plan (should be 'physical_local' or 'digital_corporate')")
    elif exp_style not in VALID_EXPERIENTIAL_STYLES:
        warn(f"V8: experiential_style '{exp_style}' invalid. Must be one of: {VALID_EXPERIENTIAL_STYLES}")

    # emotional_arc
    emotional_arc = plan.get('emotional_arc')
    if not emotional_arc:
        warn("V8: missing emotional_arc in case-plan")
    else:
        required_envs_arc = t.get('envelopes', [])
        for env in required_envs_arc:
            env_key = f"envelope_{env}"
            if env_key not in emotional_arc:
                warn(f"V8: emotional_arc missing entry for {env_key}")
            else:
                arc_text = emotional_arc[env_key]
                if not arc_text or len(str(arc_text)) < 20:
                    warn(f"V8: emotional_arc.{env_key} too short (<20 chars)")

    # trojan_horse_docs
    trojans = plan.get('trojan_horse_docs', [])
    trojan_min = {'SHORT': 1, 'NORMAL': 2, 'PREMIUM': 3}.get(tier, 2)
    if len(trojans) < trojan_min:
        warn(f"V8: trojan_horse_docs has {len(trojans)} entries, recommended ≥{trojan_min} for {tier}")
    for th in trojans:
        if th.get('doc_id') and th['doc_id'] not in docs_in_catalog:
            warn(f"V8: trojan_horse doc_id '{th['doc_id']}' not in clue_catalog")
        if not th.get('appears_as') or len(th.get('appears_as', '')) < 10:
            warn(f"V8: trojan_horse '{th.get('doc_id', '?')}' appears_as too short")
        if not th.get('actually_proves') or len(th.get('actually_proves', '')) < 10:
            warn(f"V8: trojan_horse '{th.get('doc_id', '?')}' actually_proves too short")

    # social_media_plan
    social_plan = plan.get('social_media_plan', [])
    social_min = tier_val(t, 'social_media_docs', 'social_media_docs', 'min', default=0)
    if social_min and len(social_plan) < social_min:
        warn(f"V8: social_media_plan has {len(social_plan)} entries, tier requires ≥{social_min}")

    # spatial_tool
    spatial_required = t.get('spatial_tool_required', False)
    spatial_tool = plan.get('spatial_tool')
    if spatial_required and not spatial_tool:
        warn(f"V8: spatial_tool is REQUIRED for {tier} but missing in case-plan")
    elif spatial_tool:
        if spatial_tool.get('doc_id') and spatial_tool['doc_id'] not in docs_in_catalog:
            warn(f"V8: spatial_tool doc_id '{spatial_tool['doc_id']}' not in clue_catalog")

    # Interview count vs living POIs
    interview_docs = [d for d in docs if str(d.get('type_id')) == '11']
    if len(interview_docs) < len(living_pois):
        warn(f"V8: {len(interview_docs)} interview docs but {len(living_pois)} living POIs — should be 1 interview per living POI")

    # ── Write report ────────────────────────────────────────────────────
    write_report(case_dir, issues)
    fails = sum(1 for i in issues if i[0] == "FAIL")
    warns = sum(1 for i in issues if i[0] == "WARN")
    print(f"\n{'PASS' if fails == 0 else 'FAIL'} — {fails} fails, {warns} warnings")
    sys.exit(0 if fails == 0 else 1)


def write_report(case_dir, issues):
    report_dir = case_dir / 'qa'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / 'validate_narrative_report.md'

    lines = ["# Narrative Validation Report (V8)", ""]
    fails = sum(1 for i in issues if i[0] == "FAIL")
    warns = sum(1 for i in issues if i[0] == "WARN")

    lines.append(f"**Result: {'FAIL' if fails > 0 else 'PASS'}**")
    lines.append(f"- FAIL: {fails}")
    lines.append(f"- WARN: {warns}")
    lines.append("")

    if fails > 0:
        lines.append("## Failures (must fix)")
        for level, msg in issues:
            if level == "FAIL":
                lines.append(f"- ❌ {msg}")
        lines.append("")

    if warns > 0:
        lines.append("## Warnings (should fix)")
        for level, msg in issues:
            if level == "WARN":
                lines.append(f"- ⚠️ {msg}")

    report_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Report: {report_path}")


if __name__ == '__main__':
    main()
