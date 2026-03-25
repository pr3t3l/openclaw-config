#!/usr/bin/env python3
"""
merge_clue_catalogs.py — Merges per-envelope clue_catalog files into final clue_catalog.json

Phase 2b generates clue_catalog entries envelope-by-envelope to prevent timeouts:
  clue_catalog_A.json, clue_catalog_B.json, clue_catalog_C.json, clue_catalog_R.json

This script merges them into the final clue_catalog.json and validates basic integrity.

Usage: python3 merge_clue_catalogs.py <case_dir>
Exit code: 0 = success, 1 = error
"""

import json
import sys
import os
from pathlib import Path


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 merge_clue_catalogs.py <case_dir>")
        sys.exit(2)

    case_dir = Path(sys.argv[1])

    # Read case-plan for slug and expected doc_ids
    plan_path = case_dir / 'case-plan.json'
    if not plan_path.exists():
        print(f"ERROR: case-plan.json not found at {plan_path}")
        sys.exit(1)

    plan = load_json(plan_path)
    slug = plan.get('slug', case_dir.name)

    # Collect expected doc_ids from case-plan envelopes
    expected_docs = set()
    envelope_order = []
    for env_letter, env_data in sorted(plan.get('envelopes', {}).items()):
        docs = env_data.get('docs', [])
        expected_docs.update(docs)
        envelope_order.append(env_letter)

    print(f"Merge clue catalogs for: {slug}")
    print(f"Expected envelopes: {envelope_order}")
    print(f"Expected total docs: {len(expected_docs)}")
    print()

    # Find and load per-envelope files
    all_documents = []
    found_envelopes = []
    missing_envelopes = []

    for letter in envelope_order:
        part_path = case_dir / f'clue_catalog_{letter}.json'
        if not part_path.exists():
            print(f"  MISSING: clue_catalog_{letter}.json")
            missing_envelopes.append(letter)
            continue

        try:
            part = load_json(part_path)
        except json.JSONDecodeError as e:
            print(f"  INVALID JSON: clue_catalog_{letter}.json — {e}")
            missing_envelopes.append(letter)
            continue

        docs = part.get('documents', [])
        if not docs:
            print(f"  EMPTY: clue_catalog_{letter}.json has no documents")
            missing_envelopes.append(letter)
            continue

        doc_ids = [d.get('doc_id', '?') for d in docs]
        print(f"  OK: clue_catalog_{letter}.json — {len(docs)} docs: {', '.join(doc_ids)}")
        all_documents.extend(docs)
        found_envelopes.append(letter)

    print()

    if missing_envelopes:
        print(f"ERROR: Missing envelope files: {missing_envelopes}")
        print("Fix the missing envelopes before merging.")
        sys.exit(1)

    # Validate no duplicate doc_ids
    doc_ids = [d.get('doc_id', '?') for d in all_documents]
    duplicates = [did for did in doc_ids if doc_ids.count(did) > 1]
    if duplicates:
        print(f"ERROR: Duplicate doc_ids found: {set(duplicates)}")
        sys.exit(1)

    # Check all expected docs are present
    found_ids = set(doc_ids)
    missing_ids = expected_docs - found_ids
    extra_ids = found_ids - expected_docs

    if missing_ids:
        print(f"WARNING: Missing doc_ids (in case-plan but not in catalog): {sorted(missing_ids)}")
    if extra_ids:
        print(f"WARNING: Extra doc_ids (in catalog but not in case-plan): {sorted(extra_ids)}")

    # Sort documents by envelope then sequence_number
    def sort_key(doc):
        env = doc.get('envelope', 'Z')
        seq = doc.get('sequence_number', 99)
        return (env, seq)

    all_documents.sort(key=sort_key)

    # Write final clue_catalog.json
    final = {
        "slug": slug,
        "documents": all_documents
    }

    output_path = case_dir / 'clue_catalog.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    size_kb = output_path.stat().st_size / 1024
    print(f"MERGED: clue_catalog.json — {len(all_documents)} docs, {size_kb:.1f}KB")

    # Envelope summary
    env_counts = {}
    for doc in all_documents:
        env = doc.get('envelope', '?')
        env_counts[env] = env_counts.get(env, 0) + 1

    summary = ' '.join(f"{k}={v}" for k, v in sorted(env_counts.items()))
    print(f"Distribution: {summary}")

    # Clean up per-envelope temp files
    cleaned = 0
    for letter in envelope_order:
        part_path = case_dir / f'clue_catalog_{letter}.json'
        if part_path.exists():
            part_path.unlink()
            cleaned += 1

    print(f"Cleaned up {cleaned} temp files.")
    print("Done.")


if __name__ == '__main__':
    main()
