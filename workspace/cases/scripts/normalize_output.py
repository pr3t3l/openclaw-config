#!/usr/bin/env python3
"""
normalize_output.py — Normalizes Narrative Architect output to V8 schema.

Models produce good CONTENT but in creative FIELD NAMES. This script
translates the model's output into the exact schema the validators expect,
without losing any content.

Usage:
  python3 normalize_output.py cases/exports/<slug>/

Runs on BOTH case-plan.json and clue_catalog.json.
Creates backups before modifying. Reports all changes.
"""

import json
import sys
import re
import os
from copy import deepcopy
from pathlib import Path


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def backup(path):
    backup_path = str(path).replace('.json', f'_pre_normalize.json')
    if os.path.exists(path):
        import shutil
        shutil.copy2(path, backup_path)
    return backup_path


# ================================================================
# FIELD NAME MAPPINGS — known model alternatives → expected V8 name
# ================================================================

# case-plan.json: contradiction fields
CONTRA_FIELD_MAP = {
    'description': 'what',
    'discrepancy': 'what',
    'contradiction': 'what',
    'detail': 'what',
    'resolution': 'player_inference',
    'meaning': 'player_inference',
    'inference': 'player_inference',
    'implication': 'player_inference',
    'what_it_means': 'player_inference',
    'what_player_notices': 'what',
}

# case-plan.json: POI status normalization
STATUS_MAP = {
    'living': 'alive',
    'live': 'alive',
    'suspect': 'alive',
    'active': 'alive',
    'dead': 'deceased',
    'victim': 'deceased',
    'killed': 'deceased',
    'missing': 'unknown',
}

# case-plan.json: envelope key names
ENVELOPE_DOCS_KEY_MAP = {
    'doc_ids': 'docs',
    'documents': 'docs',
    'document_ids': 'docs',
    'doc_list': 'docs',
}

# case-plan.json: culprit method
CULPRIT_METHOD_MAP = {
    'method': 'method_steps',
    'steps': 'method_steps',
    'how': 'method_steps',
    'procedure': 'method_steps',
}

# case-plan.json: timeline field names
TIMELINE_FIELD_MAP = {
    'time': 'datetime',
    'timestamp': 'datetime',
    'date': 'datetime',
    'when': 'datetime',
    'date_time': 'datetime',
    'description': 'event',
    'what_happened': 'event',
    'docs': 'source_docs',
    'sources': 'source_docs',
    'evidence': 'source_docs',
    'references': 'source_docs',
    'critical': 'is_critical_period',
    'is_critical': 'is_critical_period',
    'important': 'is_critical_period',
}

# clue_catalog: production_brief_writing field names
BRIEF_FIELD_MAP = {
    'narrative_goal': 'summary',
    'description': 'summary',
    'brief': 'summary',
    'writing_goal': 'summary',
    'overview': 'summary',
    'purpose': 'summary',
    'key_line': 'key_mandatory_line',
    'mandatory_line': 'key_mandatory_line',
    'critical_line': 'key_mandatory_line',
    'key_info': 'key_information_to_include',
    'information': 'key_information_to_include',
    'details': 'key_information_to_include',
    'include': 'key_information_to_include',
}


def normalize_case_plan(plan):
    """Normalize case-plan.json to V8 schema. Returns (plan, fixes)."""
    fixes = []

    # ── POI status normalization ──
    for poi in plan.get('pois', []):
        if not isinstance(poi, dict):
            continue
        status = poi.get('status', '').lower()
        if status in STATUS_MAP:
            old = poi['status']
            poi['status'] = STATUS_MAP[status]
            fixes.append(f"POI {poi.get('id','?')}: status '{old}' → '{poi['status']}'")

        # Rename poi_id → id
        if 'poi_id' in poi and 'id' not in poi:
            poi['id'] = poi.pop('poi_id')
            fixes.append(f"POI: renamed 'poi_id' → 'id' for {poi['id']}")

        # Ensure id format
        if poi.get('id') and not poi['id'].startswith('POI-'):
            old_id = poi['id']
            num = re.search(r'\d+', old_id)
            if num:
                poi['id'] = f"POI-{num.group().zfill(2)}"
                fixes.append(f"POI: id '{old_id}' → '{poi['id']}'")

        # Fill missing fields with safe defaults (so validator warns, not crashes)
        if 'description' not in poi:
            poi['description'] = poi.get('role', '') + ' - ' + poi.get('name', '')
            if len(poi['description']) < 20:
                poi['description'] = f"{poi.get('name', 'Unknown')} — {poi.get('role', 'Unknown role')} connected to the case"
            fixes.append(f"POI {poi.get('id','?')}: generated description from role/name")

        if 'voice_profile' not in poi and poi.get('status') == 'alive':
            poi['voice_profile'] = {
                'speech_pattern': 'TO BE DEFINED',
                'under_pressure': 'TO BE DEFINED',
                'verbal_tics': 'TO BE DEFINED'
            }
            fixes.append(f"POI {poi.get('id','?')}: added placeholder voice_profile (needs agent fill)")

        if poi.get('status') == 'alive' and not poi.get('interview_doc'):
            # Try to find it from clue_catalog if loaded later, for now mark it
            fixes.append(f"POI {poi.get('id','?')}: interview_doc is null (will attempt auto-assign)")

    # ── Auto-assign interview_doc from case-plan envelopes ──
    # Map POI names to doc_ids by matching interview titles
    living_pois = [p for p in plan.get('pois', []) if isinstance(p, dict) and p.get('status') == 'alive']

    # ── Contradiction field renames ──
    for c in plan.get('contradictions', []):
        if not isinstance(c, dict):
            continue
        for old_key, new_key in CONTRA_FIELD_MAP.items():
            if old_key in c and new_key not in c:
                c[new_key] = c.pop(old_key)
                fixes.append(f"Contradiction {c.get('id','?')}: '{old_key}' → '{new_key}'")
            elif old_key in c and new_key in c and not c[new_key]:
                # If the expected key exists but is empty, and the alt key has content
                c[new_key] = c.pop(old_key)
                fixes.append(f"Contradiction {c.get('id','?')}: filled empty '{new_key}' from '{old_key}'")

        # Ensure id format
        if c.get('id') and not c['id'].startswith('CONTRA-'):
            old_id = c['id']
            num = re.search(r'\d+', old_id)
            if num:
                c['id'] = f"CONTRA-{num.group().zfill(2)}"
                fixes.append(f"Contradiction: id '{old_id}' → '{c['id']}'")

    # ── Timeline field renames ──
    for evt in plan.get('timeline', []):
        if not isinstance(evt, dict):
            continue
        for old_key, new_key in TIMELINE_FIELD_MAP.items():
            if old_key in evt and new_key not in evt:
                evt[new_key] = evt.pop(old_key)
                fixes.append(f"Timeline: '{old_key}' → '{new_key}'")
        # Ensure is_critical_period exists
        if 'is_critical_period' not in evt:
            evt['is_critical_period'] = False

    # ── Evidence chain: strings → objects ──
    chain = plan.get('evidence_chain', [])
    if chain and len(chain) > 0 and isinstance(chain[0], str):
        new_chain = []
        for i, item in enumerate(chain):
            if isinstance(item, str):
                doc_refs = re.findall(r'\b([A-Z]\d+)\b', item)
                new_chain.append({
                    'step': i + 1,
                    'docs_needed': doc_refs if doc_refs else [],
                    'reveals': item
                })
            elif isinstance(item, dict):
                new_chain.append(item)
        plan['evidence_chain'] = new_chain
        fixes.append(f"evidence_chain: converted {len(chain)} strings → objects")
    else:
        # Ensure chain objects have required fields
        for i, step in enumerate(chain):
            if isinstance(step, dict):
                if 'step' not in step:
                    step['step'] = i + 1
                if 'docs_needed' not in step:
                    doc_refs = re.findall(r'\b([A-Z]\d+)\b', step.get('reveals', ''))
                    step['docs_needed'] = doc_refs
                if 'reveals' not in step:
                    step['reveals'] = str(step)

    # ── Envelope key renames ──
    for env_name, env_data in plan.get('envelopes', {}).items():
        if isinstance(env_data, dict):
            for old_key, new_key in ENVELOPE_DOCS_KEY_MAP.items():
                if old_key in env_data and new_key not in env_data:
                    env_data[new_key] = env_data.pop(old_key)
                    fixes.append(f"Envelope {env_name}: '{old_key}' → '{new_key}'")

    # ── Culprit method rename ──
    culprit = plan.get('culprit', {})
    if isinstance(culprit, dict):
        for old_key, new_key in CULPRIT_METHOD_MAP.items():
            if old_key in culprit and new_key not in culprit:
                val = culprit.pop(old_key)
                if isinstance(val, str):
                    steps = re.split(r'(?:\d+\.\s*|\n+|;\s*)', val)
                    culprit[new_key] = [s.strip() for s in steps if s.strip()]
                elif isinstance(val, list):
                    culprit[new_key] = val
                fixes.append(f"Culprit: '{old_key}' → '{new_key}'")

    # ── Emotional arc key normalization ──
    arc = plan.get('emotional_arc', {})
    if isinstance(arc, dict):
        new_arc = {}
        for key, val in arc.items():
            normalized = key
            if re.match(r'^[A-Z]$', key):
                normalized = f"envelope_{key}"
            elif re.match(r'^[Ee]nvelope[_ ]([A-Z])$', key):
                m = re.match(r'^[Ee]nvelope[_ ]([A-Z])$', key)
                normalized = f"envelope_{m.group(1)}"
            new_arc[normalized] = val
            if normalized != key:
                fixes.append(f"emotional_arc: '{key}' → '{normalized}'")
        if new_arc != arc:
            plan['emotional_arc'] = new_arc

    return plan, fixes


def normalize_clue_catalog(catalog, plan=None):
    """Normalize clue_catalog.json to V8 schema. Returns (catalog, fixes)."""
    fixes = []
    poi_map = {}
    if plan:
        poi_map = {p['id']: p for p in plan.get('pois', []) if isinstance(p, dict) and 'id' in p}

    for doc in catalog.get('documents', []):
        if not isinstance(doc, dict):
            continue
        did = doc.get('doc_id', '?')

        # ── Rename id → doc_id ──
        if 'id' in doc and 'doc_id' not in doc:
            doc['doc_id'] = doc.pop('id')
            did = doc['doc_id']
            fixes.append(f"{did}: renamed 'id' → 'doc_id'")

        # ── Rename sequence → sequence_number ──
        if 'sequence' in doc and 'sequence_number' not in doc:
            doc['sequence_number'] = doc.pop('sequence')
            fixes.append(f"{did}: renamed 'sequence' → 'sequence_number'")

        # ── Normalize production_brief_writing ──
        brief = doc.get('production_brief_writing', {})
        if isinstance(brief, dict):
            for old_key, new_key in BRIEF_FIELD_MAP.items():
                if old_key in brief and new_key not in brief:
                    brief[new_key] = brief.pop(old_key)
                    fixes.append(f"{did}: brief '{old_key}' → '{new_key}'")
                elif old_key in brief and new_key in brief and not brief[new_key]:
                    brief[new_key] = brief.pop(old_key)
                    fixes.append(f"{did}: filled empty brief '{new_key}' from '{old_key}'")

            # Ensure summary exists
            if 'summary' not in brief or not brief['summary']:
                # Try to derive from other fields
                candidates = ['narrative_goal', 'writing_goal', 'description',
                              'overview', 'purpose', 'brief', 'tone']
                for c in candidates:
                    if c in brief and brief[c]:
                        brief['summary'] = brief[c]
                        fixes.append(f"{did}: derived 'summary' from '{c}'")
                        break
                # If still empty, try to use reveals + tone
                if not brief.get('summary') and doc.get('reveals'):
                    tone = brief.get('tone', '')
                    brief['summary'] = f"{doc['reveals']} Tone: {tone}" if tone else doc['reveals']
                    fixes.append(f"{did}: derived 'summary' from reveals+tone")

            # Ensure key_information_to_include exists
            if 'key_information_to_include' not in brief:
                brief['key_information_to_include'] = []

        # ── Normalize production_brief_interview ──
        tid = str(doc.get('type_id', ''))
        if tid == '11':
            ib = doc.get('production_brief_interview', {})
            if isinstance(ib, dict) and ib:
                # Check if it uses the phase_1/phase_2/... format
                phase_keys = sorted([k for k in ib.keys() if re.match(r'phase_\d', k)])

                if phase_keys and 'phases' not in ib:
                    # Convert phase_N_label → phases array
                    phases = []
                    for pk in phase_keys:
                        phase_num = int(re.search(r'\d+', pk).group())
                        label = pk.replace(f'phase_{phase_num}_', '').replace('_', ' ').title()
                        phases.append({
                            'phase': phase_num,
                            'label': label,
                            'tactic': ib[pk],
                            'goal': ib[pk],
                            'exchanges': 4
                        })
                    ib['phases'] = phases
                    # Clean up old keys
                    for pk in phase_keys:
                        del ib[pk]
                    fixes.append(f"{did}: converted {len(phase_keys)} phase_N keys → phases array")

                # Auto-assign subject_poi_id from document title/pois_referenced
                if not ib.get('subject_poi_id'):
                    # Try from pois_referenced
                    refs = doc.get('pois_referenced', [])
                    living_refs = [r for r in refs if r in poi_map and poi_map[r].get('status') == 'alive']
                    if len(living_refs) == 1:
                        ib['subject_poi_id'] = living_refs[0]
                        fixes.append(f"{did}: auto-assigned subject_poi_id={living_refs[0]} from pois_referenced")
                    elif len(living_refs) > 1:
                        # Match by name in title
                        title = doc.get('in_world_title', '').lower()
                        for ref in living_refs:
                            poi_name = poi_map[ref].get('name', '').lower()
                            if poi_name and poi_name.split()[-1].lower() in title:
                                ib['subject_poi_id'] = ref
                                fixes.append(f"{did}: auto-assigned subject_poi_id={ref} from title match")
                                break

                # Ensure min_exchanges
                if not ib.get('min_exchanges'):
                    ib['min_exchanges'] = 18
                    fixes.append(f"{did}: set default min_exchanges=18")

                # Extract the_lie and the_slip from phase descriptions
                if not ib.get('the_lie'):
                    for phase in ib.get('phases', []):
                        if isinstance(phase, dict):
                            label = phase.get('label', '').lower()
                            if 'lie' in label or 'claim' in label:
                                ib['the_lie'] = phase.get('tactic', phase.get('goal', ''))
                                fixes.append(f"{did}: extracted the_lie from phase '{phase.get('label')}'")
                                break
                    # Fallback: check old-style keys
                    for key in ['phase_3_the_lie', 'the_lie_description', 'lie']:
                        if key in ib:
                            ib['the_lie'] = ib.pop(key)
                            fixes.append(f"{did}: the_lie from '{key}'")
                            break

                if not ib.get('the_slip') or not isinstance(ib.get('the_slip'), dict):
                    slip_content = None
                    for phase in ib.get('phases', []):
                        if isinstance(phase, dict):
                            label = phase.get('label', '').lower()
                            if 'slip' in label or 'reveal' in label:
                                slip_content = phase.get('tactic', phase.get('goal', ''))
                                break
                    # Check old-style keys
                    for key in ['phase_4_the_slip', 'the_slip_description', 'slip']:
                        if key in ib:
                            slip_content = ib.pop(key)
                            break

                    if slip_content:
                        ib['the_slip'] = {
                            'what': slip_content,
                            'how': 'Revealed naturally during interview pressure'
                        }
                        fixes.append(f"{did}: constructed the_slip from phase/key content")

                # Also try to link interview_doc back to case-plan POI
                if plan and ib.get('subject_poi_id'):
                    for poi in plan.get('pois', []):
                        if isinstance(poi, dict) and poi.get('id') == ib['subject_poi_id']:
                            if not poi.get('interview_doc'):
                                poi['interview_doc'] = did
                                fixes.append(f"POI {poi['id']}: assigned interview_doc={did}")

        # ── Ensure image_requirements is a list ──
        ir = doc.get('image_requirements')
        if isinstance(ir, str):
            doc['image_requirements'] = [{'type': 'general', 'brief': ir}]
            fixes.append(f"{did}: image_requirements string → list")
        elif ir is None:
            doc['image_requirements'] = []

        # ── Ensure specialized briefs default to null ──
        for key in ['production_brief_interview', 'production_brief_911', 'production_brief_newspaper']:
            if key not in doc:
                doc[key] = None

    return catalog, fixes


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 normalize_output.py cases/exports/<slug>/")
        sys.exit(1)

    case_dir = Path(sys.argv[1])
    plan_path = case_dir / 'case-plan.json'
    catalog_path = case_dir / 'clue_catalog.json'

    all_fixes = []
    plan = None

    # ── Normalize case-plan.json ──
    if plan_path.exists():
        bp = backup(plan_path)
        plan = load_json(plan_path)
        plan, fixes = normalize_case_plan(plan)
        save_json(plan_path, plan)
        all_fixes.extend([f"[case-plan] {f}" for f in fixes])
        if fixes:
            print(f"case-plan.json: {len(fixes)} fixes applied (backup: {bp})")
    else:
        print(f"WARNING: {plan_path} not found")

    # ── Normalize clue_catalog.json ──
    if catalog_path.exists():
        bp = backup(catalog_path)
        catalog = load_json(catalog_path)
        catalog, fixes = normalize_clue_catalog(catalog, plan)
        save_json(catalog_path, catalog)
        all_fixes.extend([f"[clue_catalog] {f}" for f in fixes])
        if fixes:
            print(f"clue_catalog.json: {len(fixes)} fixes applied (backup: {bp})")

        # If we assigned interview_docs back to POIs, re-save case-plan
        if plan and any('interview_doc' in f for f in fixes):
            save_json(plan_path, plan)
            print("case-plan.json: re-saved with interview_doc assignments")
    else:
        print(f"WARNING: {catalog_path} not found")

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"NORMALIZE OUTPUT: {case_dir}")
    print(f"{'='*60}")
    if all_fixes:
        print(f"Total fixes: {len(all_fixes)}")
        for f in all_fixes:
            print(f"  ✓ {f}")
    else:
        print("No fixes needed — output already matches V8 schema")
    print(f"{'='*60}\n")

    return all_fixes


if __name__ == '__main__':
    main()
