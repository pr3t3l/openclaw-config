#!/usr/bin/env python3
"""
validate_art.py — Validates Art Director output (V8.4)
Usage: python3 validate_art.py <case_dir>
Exit code: 0 = PASS, 1 = FAIL

V8.4:
- Detects duplicate POI portraits (LL-008)
- Handles reusable briefs
- Validates canonical rule expectations
- Checks envelope values, usage_map presence, and image coverage
"""

import json
import sys
from pathlib import Path


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_report(case_dir: Path, issues):
    report_dir = case_dir / 'qa'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / 'validate_art_report.md'

    fails = sum(1 for level, _ in issues if level == 'FAIL')
    warns = sum(1 for level, _ in issues if level == 'WARN')

    lines = [
        '# Art Validation Report (V8.4)',
        '',
        f"**Result: {'FAIL' if fails else 'PASS'}**",
        f"- FAIL: {fails}",
        f"- WARN: {warns}",
        ''
    ]

    for level, msg in issues:
        icon = '❌' if level == 'FAIL' else '⚠️'
        lines.append(f"- {icon} {msg}")

    report_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Report: {report_path}")


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 validate_art.py <case_dir>')
        sys.exit(2)

    case_dir = Path(sys.argv[1])
    config_dir = case_dir.parent.parent / 'config'

    issues = []

    def fail(msg):
        issues.append(('FAIL', msg))

    def warn(msg):
        issues.append(('WARN', msg))

    briefs_path = case_dir / 'art_briefs.json'
    scenes_path = case_dir / 'scene_descriptions.json'
    catalog_path = case_dir / 'clue_catalog.json'
    registry_path = config_dir / 'template_registry.json'
    manifest_path = case_dir / 'manifest.json'
    plan_path = case_dir / 'case-plan.json'
    tier_path = config_dir / 'tier_definitions.json'

    for p, name in [
        (briefs_path, 'art_briefs.json'),
        (scenes_path, 'scene_descriptions.json'),
        (catalog_path, 'clue_catalog.json'),
        (manifest_path, 'manifest.json'),
    ]:
        if not p.exists():
            fail(f"Missing file: {name}")

    if any(level == 'FAIL' for level, _ in issues):
        write_report(case_dir, issues)
        sys.exit(1)

    briefs_data = load_json(briefs_path)
    scenes = load_json(scenes_path)
    catalog = load_json(catalog_path)
    registry = load_json(registry_path) if registry_path.exists() else {}
    manifest = load_json(manifest_path)
    plan = load_json(plan_path) if plan_path.exists() else {}
    tiers = load_json(tier_path) if tier_path.exists() else {}

    templates = registry.get('templates', {})
    tier = plan.get('tier', manifest.get('tier', 'NORMAL'))
    tier_def = tiers.get(tier, {})
    valid_envelopes = set(tier_def.get('envelopes', ['A', 'B', 'C', 'D', 'R']))

    catalog_doc_ids = {
        d.get('doc_id') for d in catalog.get('documents', [])
        if isinstance(d, dict) and d.get('doc_id')
    }

    # V9: Only POI portraits are pre-generated images. All other visuals are HTML/CSS by Claude.
    # We validate that every POI has exactly one canonical portrait brief.
    docs_needing_images = []  # Legacy — kept for compatibility but not used for validation

    pois = plan.get('pois', [])
    poi_map = {p['id']: p for p in pois if isinstance(p, dict) and 'id' in p}
    deceased_pois = {p['id'] for p in pois if isinstance(p, dict) and p.get('status') == 'deceased'}

    brief_list = briefs_data.get('briefs', [])
    if not isinstance(brief_list, list):
        fail('art_briefs.json must contain a top-level briefs array')
        write_report(case_dir, issues)
        sys.exit(1)

    brief_for_docs = set()
    brief_poi_portraits = set()

    # LL-008: Detect duplicate POI portraits (non-reusable portrait generation)
    poi_gen_briefs = {}
    for b in brief_list:
        if not isinstance(b, dict):
            continue
        poi_id = b.get('for_poi')
        is_reusable = b.get('reusable_from_library', False)
        if poi_id and b.get('type') == 'mugshot' and not is_reusable:
            poi_gen_briefs.setdefault(poi_id, []).append(b.get('image_id', '?'))

    for poi_id, gen_list in poi_gen_briefs.items():
        if len(gen_list) > 1:
            fail(
                f"LL-008: POI {poi_id} has {len(gen_list)} non-reusable portraits: {gen_list}. "
                "Must be exactly 1 canonical + reusable copies."
            )

    # Validate each brief
    for b in brief_list:
        if not isinstance(b, dict):
            fail('art_briefs.briefs contains a non-object entry')
            continue

        bid = b.get('image_id', '?')
        is_reusable = b.get('reusable_from_library', False)

        if not b.get('for_doc'):
            fail(f"Brief {bid} missing for_doc")
        else:
            brief_for_docs.add(b['for_doc'])
            if b['for_doc'] not in catalog_doc_ids:
                warn(f"Brief {bid}: for_doc '{b['for_doc']}' not in clue_catalog")

        if not b.get('filename'):
            fail(f"Brief {bid} missing filename")

        env = b.get('envelope', '')
        if env and env not in valid_envelopes:
            fail(f"Brief {bid}: envelope '{env}' invalid for tier {tier}. Valid: {sorted(valid_envelopes)}")

        if not is_reusable:
            prompt = b.get('dall_e_prompt', '') or ''
            if len(prompt) < 50:
                fail(f"Brief {bid} dall_e_prompt too short (<50 chars)")
            elif 'photorealistic' not in prompt.lower():
                warn(f"Brief {bid} missing 'photorealistic' in prompt")
        else:
            if not b.get('library_path'):
                fail(f"Brief {bid} is reusable but missing library_path")

        btype = b.get('type', '')
        if btype == 'mugshot' and b.get('for_poi'):
            brief_poi_portraits.add(b['for_poi'])

        # Victim portrait style warning (LL-009)
        if btype == 'mugshot' and b.get('for_poi') in deceased_pois and not is_reusable:
            prompt_lower = (b.get('dall_e_prompt') or '').lower()
            if 'booking' in prompt_lower or 'mugshot' in prompt_lower:
                warn(f"Brief {bid}: victim {b.get('for_poi')} uses mugshot style — should be normal portrait (LL-009)")

        if not b.get('usage_map'):
            warn(f"Brief {bid} missing usage_map")

    # Ensure coverage for docs that need images
    for doc_info in docs_needing_images:
        did = doc_info.get('doc_id')
        if not did:
            continue
        found = any(isinstance(b, dict) and b.get('for_doc') == did for b in brief_list)
        if not found:
            # fallback: usage_map references
            found_usage = any(
                any(isinstance(u, dict) and u.get('doc_id') == did for u in (b.get('usage_map') or []))
                for b in brief_list if isinstance(b, dict)
            )
            if not found_usage:
                fail(f"Doc {did} needs {doc_info.get('image_type')} image but has no brief")

    # Every POI has at least one portrait brief (canonical or reusable)
    for pid in poi_map:
        if pid not in brief_poi_portraits:
            fail(f"POI {pid} has no portrait brief")

    # Validate scene_descriptions
    scene_list = scenes.get('scenes', [])
    if not isinstance(scene_list, list):
        fail('scene_descriptions.json must contain a top-level scenes array')
        scene_list = []

    if len(scene_list) < 2:
        warn(f"Only {len(scene_list)} scene descriptions (recommend >=2)")

    for s in scene_list:
        if not isinstance(s, dict):
            fail('Scene description list contains a non-object entry')
            continue
        if not s.get('for_doc'):
            fail('Scene description missing for_doc')
        if not s.get('visual_description') or len(s.get('visual_description', '')) < 30:
            warn(f"Scene for {s.get('for_doc', '?')} visual_description too short")

    # Check reusable asset references (must exist under cases/assets/reusable)
    reusable_dir = case_dir.parent.parent / 'assets' / 'reusable'
    for b in brief_list:
        if not isinstance(b, dict):
            continue
        if b.get('reusable_from_library') and b.get('library_path'):
            lib_path = reusable_dir / b['library_path'] if not Path(b['library_path']).is_absolute() else Path(b['library_path'])
            if not lib_path.exists():
                fail(f"Brief {b.get('image_id', '?')}: reusable asset not found: {b['library_path']}")

    # Print summary
    unique_gen = sum(1 for b in brief_list if isinstance(b, dict) and not b.get('reusable_from_library', False))
    reuse = sum(1 for b in brief_list if isinstance(b, dict) and b.get('reusable_from_library', False))
    print(f"\nBriefs: {len(brief_list)} total ({unique_gen} generate, {reuse} reuse)")
    print(f"Scenes: {len(scene_list)} | POIs: {len(brief_poi_portraits)}/{len(poi_map)}")

    write_report(case_dir, issues)
    fails = sum(1 for level, _ in issues if level == 'FAIL')
    warns = sum(1 for level, _ in issues if level == 'WARN')
    print(f"\n{'PASS' if fails == 0 else 'FAIL'} — {fails} fails, {warns} warnings")
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    main()
