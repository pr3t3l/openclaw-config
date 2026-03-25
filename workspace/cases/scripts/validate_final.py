#!/usr/bin/env python3
"""
validate_final.py — Validates final rendered output (v6)
Usage: python3 validate_final.py <case_dir>
Exit code: 0 = PASS, 1 = FAIL

v6: derives file expectations from clue_catalog (no expected_X.json).
"""

import json
import re
import sys
from pathlib import Path


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_final.py <case_dir>")
        sys.exit(2)

    case_dir = Path(sys.argv[1])
    issues = []
    def fail(msg): issues.append(("FAIL", msg))
    def warn(msg): issues.append(("WARN", msg))
    def info(msg): issues.append(("INFO", msg))

    manifest = load_json(case_dir / 'manifest.json')
    catalog = load_json(case_dir / 'clue_catalog.json') if (case_dir / 'clue_catalog.json').exists() else {}
    tier = manifest.get('tier', '')

    envelopes_map = {'SHORT': ['A','B','R'], 'NORMAL': ['A','B','C','R'], 'PREMIUM': ['A','B','C','D','R']}
    envelopes = envelopes_map.get(tier, ['A','B','R'])

    # Build expected docs from clue_catalog
    docs_by_envelope = {}
    for doc in catalog.get('documents', []):
        env = doc.get('envelope', '')
        if env not in docs_by_envelope:
            docs_by_envelope[env] = []
        docs_by_envelope[env].append(doc)

    total_pdfs = 0
    total_htmls = 0

    # ── 1. Check document files ─────────────────────────────────────────
    for env in envelopes:
        env_dir = case_dir / f'envelope_{env}'
        if not env_dir.exists():
            fail(f"Missing envelope directory: envelope_{env}")
            continue

        env_docs = docs_by_envelope.get(env, [])
        for doc in env_docs:
            doc_id = doc.get('doc_id', '')
            if not doc_id:
                continue

            # JSON data file
            json_path = env_dir / f'{doc_id}.json'
            if not json_path.exists():
                fail(f"Missing: {json_path.name}")

            # Content MD
            md_path = env_dir / f'{doc_id}_content.md'
            if not md_path.exists():
                fail(f"Missing: {md_path.name}")

            # Rendered HTML
            html_path = env_dir / f'{doc_id}.html'
            if html_path.exists():
                total_htmls += 1
                size = html_path.stat().st_size
                if size < 500:
                    fail(f"HTML {html_path.name} too small ({size} bytes)")
                html_text = html_path.read_text(encoding='utf-8', errors='replace')
                unresolved = re.findall(r'\{\{[^}]+\}\}', html_text)
                if unresolved:
                    fail(f"HTML {html_path.name} has unresolved placeholders: {unresolved[:3]}")
                # Check for broken image links
                img_srcs = re.findall(r'src=["\']([^"\']+)["\']', html_text)
                for src in img_srcs:
                    if src.startswith('file://'):
                        img_file = Path(src.replace('file://', ''))
                        if not img_file.exists():
                            fail(f"Broken image in {html_path.name}: {src}")
            else:
                fail(f"Missing HTML: {html_path.name}")

            # PDF
            pdf_path = env_dir / f'{doc_id}.pdf'
            if pdf_path.exists():
                total_pdfs += 1
                if pdf_path.stat().st_size < 1000:
                    fail(f"PDF {pdf_path.name} too small ({pdf_path.stat().st_size} bytes)")
            else:
                fail(f"Missing PDF: {pdf_path.name}")

    info(f"Found {total_pdfs} PDFs, {total_htmls} HTMLs")

    # ── 2. Check images ─────────────────────────────────────────────────
    config_dir = case_dir.parent.parent / 'config'
    doc_type_catalog = load_json(config_dir / 'doc_type_catalog.json') if (config_dir / 'doc_type_catalog.json').exists() else {'types': {}}

    total_images = 0
    missing_images = 0

    briefs_path = case_dir / 'art_briefs.json'
    if briefs_path.exists():
        briefs = load_json(briefs_path)
        for b in briefs.get('briefs', []):
            filename = b.get('filename', '')
            env = b.get('envelope', 'A')
            img_path = case_dir / 'visuals' / f'envelope_{env}' / 'final' / filename
            if img_path.exists():
                total_images += 1
                if img_path.stat().st_size < 10000:
                    warn(f"Image {filename} very small ({img_path.stat().st_size} bytes)")
            else:
                fail(f"Missing image: {filename}")
                missing_images += 1

    info(f"Found {total_images} images, {missing_images} missing")

    # ── 3. Merged envelope PDFs ─────────────────────────────────────────
    final_dir = case_dir / 'final'
    if final_dir.exists():
        for env in envelopes:
            merged = final_dir / f'Envelope_{env}.pdf'
            if merged.exists():
                if merged.stat().st_size < 5000:
                    warn(f"Merged {merged.name} very small ({merged.stat().st_size} bytes)")
            else:
                warn(f"Missing merged PDF: Envelope_{env}.pdf")
    else:
        warn("final/ directory not found")

    # ── 4. Audio (PREMIUM) ──────────────────────────────────────────────
    if tier == 'PREMIUM':
        audio_dir = case_dir / 'audio'
        audio_docs = [d for d in catalog.get('documents', [])
                      if str(d.get('type_id')) in ('6', '11')]
        for doc in audio_docs:
            audio_file = audio_dir / f"{doc['doc_id']}.mp3"
            if audio_file.exists():
                if audio_file.stat().st_size < 50000:
                    warn(f"Audio {audio_file.name} very small")
            else:
                fail(f"Missing audio: {doc['doc_id']}.mp3")

    # ── Write report ────────────────────────────────────────────────────
    report_dir = case_dir / 'qa'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / 'validate_final_report.md'

    lines = ["# Final Validation Report (v6)", ""]
    fails = sum(1 for i in issues if i[0] == "FAIL")
    warns = sum(1 for i in issues if i[0] == "WARN")
    lines.append(f"**Result: {'FAIL' if fails > 0 else 'PASS'}**")
    lines.append(f"- FAIL: {fails}")
    lines.append(f"- WARN: {warns}")
    lines.append("")
    for level, msg in issues:
        icons = {"FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️"}
        lines.append(f"- {icons.get(level, '•')} {msg}")
    report_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Report: {report_path}")
    print(f"\n{'PASS' if fails == 0 else 'FAIL'} — {fails} fails, {warns} warnings")
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    main()
