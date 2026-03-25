#!/usr/bin/env python3
"""
benchmark_scoring.py — Automated 6-pillar benchmark scoring for Declassified Cases V8.
Can be run standalone or imported by quality-auditor.

Usage: python3 cases/scripts/benchmark_scoring.py cases/exports/<slug>/

Scoring based on the 4-case benchmark analysis:
  Linda Oward: 88% (gold standard)
  Steve Jacobs: 83%
  Carmen García: 82%
  Caso Nismen: 62%
  
Target: ≥75% (45/60) to pass threshold
"""

import json
import sys
import os
from collections import Counter


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def score_case(case_dir):
    """Score a case against the 6 quality pillars. Returns dict with scores and analysis."""

    # Load all required files
    try:
        case_plan = load_json(os.path.join(case_dir, 'case-plan.json'))
        clue_catalog = load_json(os.path.join(case_dir, 'clue_catalog.json'))
    except FileNotFoundError as e:
        return {"error": f"Missing required file: {e}"}

    # Optional files (score what we can)
    experience = None
    art_briefs = None
    try:
        experience = load_json(os.path.join(case_dir, 'experience_design.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        art_briefs = load_json(os.path.join(case_dir, 'art_briefs.json'))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    docs = clue_catalog.get('documents', [])
    pois = case_plan.get('pois', [])
    contradictions = case_plan.get('contradictions', [])
    timeline = case_plan.get('timeline', [])
    tier = case_plan.get('tier', 'NORMAL')
    living_pois = [p for p in pois if p.get('status') == 'alive']

    scores = {}
    notes = {}

    # ========================================================
    # PILLAR 1: User Experience (Emotional Arc) — weight 2x
    # ========================================================
    ux_score = 5  # baseline

    # Check for emotional_arc
    if case_plan.get('emotional_arc'):
        arc = case_plan['emotional_arc']
        specific_count = sum(1 for v in arc.values() if len(str(v)) > 30)
        if specific_count >= 3:
            ux_score += 1  # case-specific emotional arc planned

    # Check interview quality indicators
    interview_docs = [d for d in docs if str(d.get('type_id')) == '11']
    if len(interview_docs) >= len(living_pois):
        ux_score += 1  # 1 interview per living POI

    # Check interview briefs have phases, the_lie, the_slip
    interviews_with_briefs = 0
    for d in interview_docs:
        brief = d.get('production_brief_interview', {})
        if brief and brief.get('phases') and brief.get('the_lie') and brief.get('the_slip'):
            interviews_with_briefs += 1
    if interviews_with_briefs == len(interview_docs) and len(interview_docs) > 0:
        ux_score += 1  # all interviews have full briefs

    # Check for visceral moment (911 call, intercepted call, etc.)
    visceral_types = {6, 18}  # 911 transcript, calls/SMS
    has_visceral = any(d.get('type_id') in visceral_types for d in docs)
    if has_visceral:
        ux_score += 0.5

    # Check experience design emotional beats
    if experience:
        doc_map = experience.get('document_experience_map', {})
        beats_with_specifics = sum(1 for entry in doc_map.values()
                                   if len(entry.get('emotional_beat', '')) > 30)
        if beats_with_specifics >= len(docs) * 0.7:
            ux_score += 1  # >70% of docs have specific emotional beats

    # Check for conflicting emotions (POIs with both surface_motive and hiding)
    complex_pois = sum(1 for p in living_pois if p.get('surface_motive') and p.get('hiding'))
    if complex_pois >= 2:
        ux_score += 0.5

    ux_score = min(10, ux_score)
    scores['user_experience'] = {'raw': round(ux_score, 1), 'weight': 2, 'weighted': round(ux_score * 2, 1)}
    notes['user_experience'] = f"{len(interview_docs)} interviews, {interviews_with_briefs} with full briefs, visceral={has_visceral}"

    # ========================================================
    # PILLAR 2: Information Relevance — weight 1x
    # ========================================================
    ir_score = 5

    # Every doc has reveals and player_inference
    docs_with_reveals = sum(1 for d in docs if len(d.get('reveals', '')) > 30)
    docs_with_inference = sum(1 for d in docs if len(d.get('player_inference', '')) > 20)
    if docs_with_reveals == len(docs):
        ir_score += 1
    if docs_with_inference == len(docs):
        ir_score += 1

    # Trojan horse docs planned
    trojans = case_plan.get('trojan_horse_docs', [])
    if len(trojans) >= 2:
        ir_score += 1.5
    elif len(trojans) >= 1:
        ir_score += 0.5

    # Document justification quality
    docs_with_justification = sum(1 for d in docs if len(d.get('document_justification', '')) > 30)
    if docs_with_justification >= len(docs) * 0.8:
        ir_score += 1

    # Check for alibi-verification evidence (receipts, logs, records)
    alibi_types = {7, 8, 18}  # evidence_mosaic, entry_exit_log, calls_sms_log
    alibi_docs = sum(1 for d in docs if d.get('type_id') in alibi_types)
    if alibi_docs >= 2:
        ir_score += 0.5

    ir_score = min(10, ir_score)
    scores['information_relevance'] = {'raw': round(ir_score, 1), 'weight': 1, 'weighted': round(ir_score, 1)}
    notes['information_relevance'] = f"{docs_with_reveals}/{len(docs)} docs with reveals, {len(trojans)} trojans, {alibi_docs} alibi-verification docs"

    # ========================================================
    # PILLAR 3: Clue Structure & Cognitive Load — weight 1x
    # ========================================================
    cs_score = 5

    # Contradiction count meets tier minimums
    tier_mins = {'SHORT': 3, 'NORMAL': 5, 'PREMIUM': 8}
    if len(contradictions) >= tier_mins.get(tier, 5):
        cs_score += 1

    # At least 1 contradiction resolves in C or later
    late_resolvers = 0
    for c in contradictions:
        resolved_doc = c.get('resolved_in', '')
        for d in docs:
            if d.get('doc_id') == resolved_doc and d.get('envelope', '') in ('C', 'D', 'R'):
                late_resolvers += 1
                break
    if late_resolvers >= 1:
        cs_score += 1

    # Evidence chain length
    chain = case_plan.get('evidence_chain', [])
    if 6 <= len(chain) <= 12:
        cs_score += 1

    # Timeline events
    if len(timeline) >= 8:
        cs_score += 0.5

    # Clue proximity check from experience_design
    if experience:
        proximity = experience.get('clue_proximity_check', [])
        warnings = sum(1 for p in proximity if p.get('status') in ('proximity_warning', 'too_easy_warning'))
        if len(proximity) > 0 and warnings == 0:
            cs_score += 1
        elif warnings <= 1:
            cs_score += 0.5

    # Envelope balance
    envelope_counts = Counter(d.get('envelope') for d in docs if d.get('envelope') != 'R')
    if envelope_counts:
        max_c = max(envelope_counts.values())
        min_c = min(envelope_counts.values())
        if max_c <= 2 * min_c:
            cs_score += 0.5

    cs_score = min(10, cs_score)
    scores['clue_structure'] = {'raw': round(cs_score, 1), 'weight': 1, 'weighted': round(cs_score, 1)}
    notes['clue_structure'] = f"{len(contradictions)} contradictions, {late_resolvers} resolve in C+, chain={len(chain)}"

    # ========================================================
    # PILLAR 4: Visual Support — weight 1x
    # ========================================================
    vs_score = 3  # lower baseline since this depends on images existing

    if art_briefs:
        briefs = art_briefs.get('briefs', [])
        brief_types = Counter(b.get('type') for b in briefs)

        # Image coverage
        if len(briefs) >= 10:
            vs_score += 2
        elif len(briefs) >= 5:
            vs_score += 1

        # Variety of image types
        if len(brief_types) >= 4:
            vs_score += 1.5
        elif len(brief_types) >= 2:
            vs_score += 0.5

        # Canonical POI portraits
        poi_mugshots = sum(1 for b in briefs if b.get('type') == 'mugshot')
        if poi_mugshots >= len(pois) - 1:  # -1 for victim who may not have mugshot
            vs_score += 1

        # Scene images
        scene_images = sum(1 for b in briefs if b.get('type') in ('scene', 'building'))
        if scene_images >= 2:
            vs_score += 0.5

        # Usage map present
        briefs_with_usage = sum(1 for b in briefs if b.get('usage_map'))
        if briefs_with_usage >= len(briefs) * 0.5:
            vs_score += 1
    else:
        notes_extra = "art_briefs.json not found — visual score heavily penalized"

    vs_score = min(10, vs_score)
    scores['visual_support'] = {'raw': round(vs_score, 1), 'weight': 1, 'weighted': round(vs_score, 1)}
    notes['visual_support'] = f"{len(art_briefs.get('briefs', [])) if art_briefs else 0} image briefs planned"

    # ========================================================
    # PILLAR 5: Dynamic Clue Variety — weight 0.5x
    # ========================================================
    dv_score = 5

    type_keys = set(d.get('type_key') for d in docs)
    tier_type_mins = {'SHORT': 6, 'NORMAL': 10, 'PREMIUM': 14}

    if len(type_keys) >= tier_type_mins.get(tier, 10):
        dv_score += 2
    elif len(type_keys) >= tier_type_mins.get(tier, 10) * 0.8:
        dv_score += 1

    # Social media docs
    social_docs = sum(1 for d in docs if d.get('type_key') == 'social_posts')
    if social_docs >= 3:
        dv_score += 1
    elif social_docs >= 1:
        dv_score += 0.5

    # Spatial tool
    spatial = case_plan.get('spatial_tool')
    if spatial and spatial.get('doc_id'):
        dv_score += 1

    # Total doc count meets tier
    tier_doc_mins = {'SHORT': 8, 'NORMAL': 15, 'PREMIUM': 25}
    if len(docs) >= tier_doc_mins.get(tier, 15):
        dv_score += 1

    dv_score = min(10, dv_score)
    scores['dynamic_variety'] = {'raw': round(dv_score, 1), 'weight': 0.5, 'weighted': round(dv_score * 0.5, 1)}
    notes['dynamic_variety'] = f"{len(type_keys)} unique types, {len(docs)} total docs, {social_docs} social media"

    # ========================================================
    # PILLAR 6: Document as Experience — weight 0.5x
    # ========================================================
    de_score = 4  # lower baseline

    if experience:
        doc_map = experience.get('document_experience_map', {})

        # Detective annotations coverage
        docs_with_annotations = sum(1 for entry in doc_map.values()
                                     if len(entry.get('detective_annotations', [])) >= 1)
        coverage = docs_with_annotations / max(len(docs), 1)
        if coverage >= 0.5:
            de_score += 2
        elif coverage >= 0.3:
            de_score += 1

        # Immersion elements variety
        all_elements = []
        for entry in doc_map.values():
            all_elements.extend(entry.get('immersion_elements', []))
        unique_elements = len(set(all_elements))
        if unique_elements >= 8:
            de_score += 1.5
        elif unique_elements >= 4:
            de_score += 0.5

        # Experiential style declared and consistent
        if experience.get('experiential_style'):
            de_score += 1

        # Detective persona defined
        if experience.get('detective_persona', {}).get('name'):
            de_score += 0.5

    de_score = min(10, de_score)
    scores['document_experience'] = {'raw': round(de_score, 1), 'weight': 0.5, 'weighted': round(de_score * 0.5, 1)}
    notes['document_experience'] = f"experience_design={'present' if experience else 'missing'}"

    # ========================================================
    # TOTAL
    # ========================================================
    total_weighted = sum(s['weighted'] for s in scores.values())
    max_possible = 20 + 10 + 10 + 10 + 5 + 5  # = 60 weighted max (using the weights)
    # Actually: 2*10 + 1*10 + 1*10 + 1*10 + 0.5*10 + 0.5*10 = 55
    max_weighted = 55
    score_60 = round((total_weighted / max_weighted) * 60, 1)
    percentage = round((total_weighted / max_weighted) * 100)

    above_threshold = score_60 >= 45  # 75%

    # Identify weakest pillars
    pillar_percentages = {}
    for name, s in scores.items():
        pillar_percentages[name] = round(s['raw'] / 10 * 100)
    weakest = sorted(pillar_percentages.items(), key=lambda x: x[1])[:2]
    weakest_names = [w[0] for w in weakest]

    result = {
        "pillar_scores": scores,
        "pillar_notes": notes,
        "total_weighted": round(total_weighted, 1),
        "score_out_of_60": score_60,
        "percentage": f"{percentage}%",
        "above_threshold": above_threshold,
        "weakest_pillars": weakest_names,
        "comparison": {
            "linda_oward": "88% (53/60)",
            "steve_jacobs": "83% (50/60)",
            "carmen_garcia": "82% (49/60)",
            "caso_nismen": "62% (37/60)",
            "this_case": f"{percentage}% ({score_60}/60)"
        }
    }

    return result


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 benchmark_scoring.py <case_export_dir>")
        sys.exit(1)

    case_dir = sys.argv[1].rstrip('/')
    result = score_case(case_dir)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"BENCHMARK SCORING: {case_dir}")
    print(f"{'='*60}")

    for name, s in result['pillar_scores'].items():
        bar = '█' * int(s['raw']) + '░' * (10 - int(s['raw']))
        print(f"  {name:25s} {bar} {s['raw']:4.1f}/10  (×{s['weight']} = {s['weighted']:4.1f})")

    print(f"\n  {'TOTAL':25s}              {result['total_weighted']:5.1f}/{55}")
    print(f"  {'SCORE (60-pt scale)':25s}              {result['score_out_of_60']:5.1f}/60")
    print(f"  {'PERCENTAGE':25s}              {result['percentage']}")
    print(f"  {'THRESHOLD (75%)':25s}              {'✓ PASS' if result['above_threshold'] else '✗ BELOW THRESHOLD'}")

    print(f"\n  Weakest pillars: {', '.join(result['weakest_pillars'])}")

    print(f"\n  Comparison:")
    for k, v in result['comparison'].items():
        marker = ' ◄' if k == 'this_case' else ''
        print(f"    {k:20s} {v}{marker}")

    print(f"{'='*60}\n")

    # Write result
    output_path = os.path.join(case_dir, 'benchmark_score.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Score written to: {output_path}")

    sys.exit(0 if result['above_threshold'] else 1)


if __name__ == '__main__':
    main()
