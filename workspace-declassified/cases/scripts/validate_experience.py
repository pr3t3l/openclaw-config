#!/usr/bin/env python3
"""
validate_experience.py — Validates experience_design.json for Declassified Cases V8.
Run after Experience Designer, before Production Engine.

Usage: python3 cases/scripts/validate_experience.py cases/exports/<slug>/
"""

import json
import sys
import os

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate(case_dir):
    errors = []
    warnings = []

    # --- Load required files ---
    try:
        experience = load_json(os.path.join(case_dir, 'experience_design.json'))
    except FileNotFoundError:
        print("FAIL: experience_design.json not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"FAIL: experience_design.json is invalid JSON: {e}")
        sys.exit(1)

    try:
        case_plan = load_json(os.path.join(case_dir, 'case-plan.json'))
    except FileNotFoundError:
        print("FAIL: case-plan.json not found (required for cross-validation)")
        sys.exit(1)

    try:
        clue_catalog = load_json(os.path.join(case_dir, 'clue_catalog.json'))
    except FileNotFoundError:
        print("FAIL: clue_catalog.json not found (required for cross-validation)")
        sys.exit(1)

    # Build doc_id set from clue_catalog
    catalog_doc_ids = set()
    for doc in clue_catalog.get('documents', []):
        catalog_doc_ids.add(doc.get('doc_id', ''))

    # --- 1. Top-level fields ---
    if 'experiential_style' not in experience:
        errors.append("Missing 'experiential_style'")
    elif experience['experiential_style'] not in ('physical_local', 'digital_corporate'):
        errors.append(f"Invalid experiential_style: '{experience['experiential_style']}'. Must be 'physical_local' or 'digital_corporate'.")

    if 'detective_persona' not in experience:
        errors.append("Missing 'detective_persona'")
    else:
        persona = experience['detective_persona']
        if not persona.get('name'):
            errors.append("detective_persona.name is empty")
        if not persona.get('annotation_voice') or len(persona.get('annotation_voice', '')) < 10:
            errors.append("detective_persona.annotation_voice must be ≥10 chars describing the detective's writing style")

    # --- 2. Document Experience Map ---
    doc_map = experience.get('document_experience_map', {})

    # Check every clue_catalog doc has an entry
    for doc_id in catalog_doc_ids:
        if doc_id not in doc_map:
            errors.append(f"Document {doc_id} exists in clue_catalog but has no entry in document_experience_map")

    # Check each entry quality
    emotional_beats_seen = []
    annotation_contents_seen = []

    for doc_id, entry in doc_map.items():
        prefix = f"[{doc_id}]"

        # doc_id must exist in catalog
        if doc_id not in catalog_doc_ids:
            warnings.append(f"{prefix} exists in experience_map but not in clue_catalog (orphan entry)")

        # emotional_beat
        beat = entry.get('emotional_beat', '')
        if not beat or len(beat) < 20:
            errors.append(f"{prefix} emotional_beat missing or <20 chars: '{beat}'")
        else:
            # Check for generic beats (substitution test)
            generic_beats = [
                "the player feels suspense",
                "the player feels curious",
                "creates tension",
                "important clue",
                "reveals information",
                "the player learns something"
            ]
            for gb in generic_beats:
                if gb in beat.lower():
                    errors.append(f"{prefix} emotional_beat is too generic (contains '{gb}'). Must be specific to THIS document.")
            emotional_beats_seen.append(beat)

        # detective_annotations
        annotations = entry.get('detective_annotations', [])
        if not annotations:
            errors.append(f"{prefix} has no detective_annotations (minimum 1 required)")

        # Find this doc's player_purpose from clue_catalog
        doc_purpose = None
        for doc in clue_catalog.get('documents', []):
            if doc.get('doc_id') == doc_id:
                doc_purpose = doc.get('player_purpose')
                break

        if doc_purpose in ('clue_delivery', 'revelation') and len(annotations) < 2:
            errors.append(f"{prefix} is a '{doc_purpose}' document — needs ≥2 detective_annotations (has {len(annotations)})")

        for i, ann in enumerate(annotations):
            ann_prefix = f"{prefix} annotation[{i}]"

            valid_types = {'sticky_note', 'margin_comment', 'highlight', 'circled_text', 'arrow_connection', 'question_mark'}
            if ann.get('type') not in valid_types:
                errors.append(f"{ann_prefix} invalid type: '{ann.get('type')}'. Valid: {valid_types}")

            content = ann.get('content', '')
            if not content or len(content) < 5:
                errors.append(f"{ann_prefix} content missing or too short")
            elif content.lower() in ('check this', 'important', 'suspicious', 'important clue', 'look into this'):
                errors.append(f"{ann_prefix} content is too generic: '{content}'. Must reference specific case facts.")
            annotation_contents_seen.append(content)

            if not ann.get('position'):
                warnings.append(f"{ann_prefix} missing position hint")

        # immersion_elements
        elements = entry.get('immersion_elements', [])
        if not elements:
            errors.append(f"{prefix} has no immersion_elements (minimum 1 required)")

    # Check for duplicate annotation content
    from collections import Counter
    content_counts = Counter(annotation_contents_seen)
    for content, count in content_counts.items():
        if count >= 2:
            errors.append(f"Annotation content appears {count} times (must be unique): '{content[:60]}...'")

    # Check for duplicate emotional beats
    beat_counts = Counter(emotional_beats_seen)
    for beat, count in beat_counts.items():
        if count >= 2:
            errors.append(f"Emotional beat appears {count} times (must be unique per doc): '{beat[:60]}...'")

    # --- 3. Clue Proximity Check ---
    proximity = experience.get('clue_proximity_check', [])
    contradictions = case_plan.get('contradictions', [])

    if len(proximity) < len(contradictions):
        errors.append(f"clue_proximity_check has {len(proximity)} entries but case-plan has {len(contradictions)} contradictions — must cover ALL")

    proximity_warnings_count = 0
    for p in proximity:
        if p.get('status') == 'proximity_warning':
            proximity_warnings_count += 1
            warnings.append(f"Contradiction {p.get('contradiction_id')}: distance {p.get('distance_docs')} docs (>8) — may be hard for players to connect")
        elif p.get('status') == 'too_easy_warning':
            warnings.append(f"Contradiction {p.get('contradiction_id')}: distance {p.get('distance_docs')} docs (<2) — may be too obvious")

    # --- 4. Pacing Analysis ---
    pacing = experience.get('pacing_analysis', {})
    tier = case_plan.get('tier', 'NORMAL')

    expected_envelopes = {'SHORT': ['A', 'B', 'R'], 'NORMAL': ['A', 'B', 'C', 'R'], 'PREMIUM': ['A', 'B', 'C', 'D', 'R']}
    expected = expected_envelopes.get(tier, ['A', 'B', 'C', 'R'])

    for env in expected:
        if env not in pacing:
            errors.append(f"pacing_analysis missing envelope {env}")
        else:
            p = pacing[env]
            if not p.get('document_count'):
                errors.append(f"pacing_analysis.{env}.document_count is missing or zero")
            if not p.get('emotional_intensity'):
                errors.append(f"pacing_analysis.{env}.emotional_intensity is missing")

    # Check balance
    if pacing:
        counts = {env: pacing[env].get('document_count', 0) for env in pacing if env != 'R'}
        if counts:
            max_count = max(counts.values())
            min_count = min(counts.values()) if min(counts.values()) > 0 else 1
            if max_count >= 2 * min_count:
                warnings.append(f"Envelope balance warning: max {max_count} docs vs min {min_count} docs — consider rebalancing")

    # Check C envelope pivot thickness
    if 'C' in pacing and pacing['C'].get('document_count', 0) < 2:
        warnings.append("Envelope C has fewer than 2 documents — pivot may feel too thin")

    # --- 5. Trojan Horse Verification ---
    trojans = experience.get('trojan_horse_verification', [])
    if not trojans:
        warnings.append("No trojan_horse_verification entries — these are important for information relevance")

    for t in trojans:
        if t.get('doc_id') not in catalog_doc_ids:
            errors.append(f"Trojan horse doc_id '{t.get('doc_id')}' not found in clue_catalog")
        if not t.get('appears_as') or len(t.get('appears_as', '')) < 10:
            errors.append(f"Trojan horse '{t.get('doc_id')}' appears_as is too short")
        if not t.get('actually_proves') or len(t.get('actually_proves', '')) < 10:
            errors.append(f"Trojan horse '{t.get('doc_id')}' actually_proves is too short")

    # --- Write report to qa/ ---
    report_dir = os.path.join(case_dir, 'qa')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, 'validate_experience_report.md')

    lines = ["# Experience Design Validation Report", ""]
    lines.append(f"**Result: {'FAIL' if errors else 'PASS'}**")
    lines.append(f"- Errors: {len(errors)}")
    lines.append(f"- Warnings: {len(warnings)}")
    lines.append(f"- Documents in experience map: {len(doc_map)}/{len(catalog_doc_ids)}")
    lines.append("")

    if errors:
        lines.append("## Errors (must fix)")
        for e in errors:
            lines.append(f"- ❌ {e}")
        lines.append("")
    if warnings:
        lines.append("## Warnings (should fix)")
        for w in warnings:
            lines.append(f"- ⚠️ {w}")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Report: {report_path}")

    # --- Console output ---
    print(f"\n{'='*60}")
    print(f"EXPERIENCE DESIGN VALIDATION: {case_dir}")
    print(f"{'='*60}")
    print(f"Documents in catalog: {len(catalog_doc_ids)}")
    print(f"Documents in experience map: {len(doc_map)}")
    print(f"Contradictions checked: {len(proximity)}/{len(contradictions)}")
    print(f"Envelopes in pacing: {len(pacing)}/{len(expected)}")
    print(f"Trojan horses verified: {len(trojans)}")
    print(f"{'='*60}")

    if errors:
        print(f"\nFAIL — {len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")
    if warnings:
        print(f"\nWARNINGS — {len(warnings)}:")
        for w in warnings:
            print(f"  ⚠ {w}")
    if not errors:
        print(f"\nPASS — experience_design.json is valid")
        if warnings:
            print(f"  ({len(warnings)} non-blocking warnings)")

    print(f"\n{'='*60}")
    return len(errors) == 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 validate_experience.py <case_export_dir>")
        sys.exit(1)

    case_dir = sys.argv[1].rstrip('/')
    success = validate(case_dir)
    sys.exit(0 if success else 1)
