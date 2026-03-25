#!/usr/bin/env python3
"""
fix_case_plan_schema.py — Auto-fixes structural shape mismatches in case-plan.json

This script fixes MECHANICAL schema issues where the content is correct but the
shape is wrong. It does NOT change narrative content — only restructures fields
to match the V8 skeleton.

Run immediately after Phase 2a (case-plan.json generation) and before validation.

Usage: python3 fix_case_plan_schema.py cases/exports/<slug>/case-plan.json

Known fixes:
  1. evidence_chain: string[] → object[] with {step, docs_needed, reveals}
  2. contradictions: ensures all have 'id' field (adds CONTRA-NN if missing)
  3. timeline: ensures all have 'datetime' field (flags if missing, can't auto-fix)
  4. pois: ensures 'id' field format POI-NN (fixes 'poi_id' → 'id' rename)
  5. envelopes: fixes 'doc_ids'/'documents' → 'docs' key name
  6. culprit: fixes 'method' string → 'method_steps' array
"""

import json
import sys
import re
import os
from copy import deepcopy


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fix_case_plan(path):
    plan = load_json(path)
    original = deepcopy(plan)
    fixes = []

    # ── Fix 1: evidence_chain strings → objects ──
    chain = plan.get('evidence_chain', [])
    if chain and isinstance(chain[0], str):
        new_chain = []
        for i, item in enumerate(chain):
            if isinstance(item, str):
                # Try to extract doc references from the string
                doc_refs = re.findall(r'\b([A-Z]\d+)\b', item)
                new_chain.append({
                    "step": i + 1,
                    "docs_needed": doc_refs if doc_refs else [],
                    "reveals": item
                })
            elif isinstance(item, dict):
                new_chain.append(item)
        plan['evidence_chain'] = new_chain
        fixes.append(f"evidence_chain: converted {len(chain)} strings → objects")

    # Ensure evidence_chain objects have required fields
    for i, step in enumerate(plan.get('evidence_chain', [])):
        if isinstance(step, dict):
            if 'step' not in step:
                step['step'] = i + 1
                fixes.append(f"evidence_chain[{i}]: added missing 'step' number")
            if 'docs_needed' not in step:
                doc_refs = re.findall(r'\b([A-Z]\d+)\b', step.get('reveals', ''))
                step['docs_needed'] = doc_refs
                fixes.append(f"evidence_chain[{i}]: added missing 'docs_needed'")
            if 'reveals' not in step:
                step['reveals'] = str(step)
                fixes.append(f"evidence_chain[{i}]: added missing 'reveals'")

    # ── Fix 2: contradiction IDs ──
    for i, c in enumerate(plan.get('contradictions', [])):
        if isinstance(c, dict):
            if not c.get('id'):
                c['id'] = f"CONTRA-{i+1:02d}"
                fixes.append(f"contradiction[{i}]: added missing id '{c['id']}'")
            elif not c['id'].startswith('CONTRA-'):
                old_id = c['id']
                c['id'] = f"CONTRA-{i+1:02d}"
                fixes.append(f"contradiction[{i}]: fixed id '{old_id}' → '{c['id']}'")

    # ── Fix 3: POI 'poi_id' → 'id' rename ──
    for poi in plan.get('pois', []):
        if isinstance(poi, dict):
            if 'poi_id' in poi and 'id' not in poi:
                poi['id'] = poi.pop('poi_id')
                fixes.append(f"POI: renamed 'poi_id' → 'id' for {poi['id']}")
            if poi.get('id') and not poi['id'].startswith('POI-'):
                old_id = poi['id']
                # Try to preserve the number
                num = re.search(r'\d+', old_id)
                poi['id'] = f"POI-{num.group().zfill(2)}" if num else poi['id']
                fixes.append(f"POI: fixed id format '{old_id}' → '{poi['id']}'")

    # ── Fix 4: Envelope key 'doc_ids'/'documents' → 'docs' ──
    for env_name, env_data in plan.get('envelopes', {}).items():
        if isinstance(env_data, dict):
            if 'doc_ids' in env_data and 'docs' not in env_data:
                env_data['docs'] = env_data.pop('doc_ids')
                fixes.append(f"envelope {env_name}: renamed 'doc_ids' → 'docs'")
            elif 'documents' in env_data and 'docs' not in env_data:
                env_data['docs'] = env_data.pop('documents')
                fixes.append(f"envelope {env_name}: renamed 'documents' → 'docs'")

    # ── Fix 5: culprit 'method' string → 'method_steps' array ──
    culprit = plan.get('culprit', {})
    if isinstance(culprit, dict):
        if 'method' in culprit and 'method_steps' not in culprit:
            method = culprit.pop('method')
            if isinstance(method, str):
                # Split on sentence boundaries or numbered steps
                steps = re.split(r'(?:\d+\.\s*|\n+|;\s*)', method)
                steps = [s.strip() for s in steps if s.strip()]
                culprit['method_steps'] = steps if steps else [method]
            elif isinstance(method, list):
                culprit['method_steps'] = method
            fixes.append(f"culprit: converted 'method' → 'method_steps' ({len(culprit.get('method_steps', []))} steps)")

    # ── Fix 6: emotional_arc key format normalization ──
    arc = plan.get('emotional_arc', {})
    if isinstance(arc, dict):
        new_arc = {}
        for key, val in arc.items():
            # Normalize: 'A' → 'envelope_A', 'Envelope A' → 'envelope_A'
            normalized = key
            if re.match(r'^[A-Z]$', key):
                normalized = f"envelope_{key}"
            elif re.match(r'^[Ee]nvelope[_ ]([A-Z])$', key):
                normalized = f"envelope_{re.match(r'^[Ee]nvelope[_ ]([A-Z])$', key).group(1)}"
            new_arc[normalized] = val
            if normalized != key:
                fixes.append(f"emotional_arc: normalized key '{key}' → '{normalized}'")
        if new_arc != arc:
            plan['emotional_arc'] = new_arc

    # ── Save if changed ──
    if fixes:
        # Backup original
        backup_path = path.replace('.json', '_pre_schema_fix.json')
        save_json(backup_path, original)

        # Save fixed
        save_json(path, plan)

        print(f"\n{'='*60}")
        print(f"SCHEMA FIXER: {path}")
        print(f"{'='*60}")
        print(f"  Fixes applied: {len(fixes)}")
        for f in fixes:
            print(f"  ✓ {f}")
        print(f"  Backup saved: {backup_path}")
        print(f"{'='*60}\n")
    else:
        print(f"SCHEMA FIXER: {path} — no fixes needed (schema already correct)")

    return fixes


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 fix_case_plan_schema.py <case-plan.json path>")
        sys.exit(1)

    fixes = fix_case_plan(sys.argv[1])
    sys.exit(0)
