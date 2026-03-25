#!/usr/bin/env python3
"""
validate_content.py — Validates Production Engine _content.md files against clue_catalog briefs.

This runs AFTER Production Engine (Phase 5) and BEFORE Layout Planner.
It validates narrative content directly — no template_vars needed.

Usage: python3 validate_content.py <case_dir> [<envelope>]
  - With envelope: validates only that envelope's documents
  - Without envelope: validates all envelopes

Exit code: 0 = PASS, 1 = FAIL
"""

import json
import re
import sys
from pathlib import Path

KNOWN_PLACEHOLDER_PATTERNS = [
    r'\{\{', r'\{CONTENT_FROM_MD_FILE\}', r'<TBD>', r'\[FILL\]', r'\[TODO\]',
    r'\[Text here\]', r'Question \d+', r'Response \d+', r'\[INSERT',
]

HTML_TAG_PATTERN = re.compile(r'<(?:p|div|span|br|table|tr|td|th)\b[^>]*>', re.IGNORECASE)


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def count_narrative_words(text, doc_type_key):
    """Count narrative words, excluding form labels, headers, metadata."""
    lines = text.strip().split('\n')
    narrative_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Skip markdown headers that are just labels
        if stripped.startswith('#') and len(stripped.split()) <= 4:
            continue
        # Skip form-style labels (KEY: value where KEY is all caps or title case)
        if re.match(r'^[A-Z][A-Z\s/]+:', stripped) and len(stripped.split(':')[0].split()) <= 4:
            continue
        # Skip metadata lines
        if re.match(r'^\*\*[A-Za-z\s]+:\*\*', stripped):
            continue
        # Skip speaker tags in interviews (but count their dialogue)
        if doc_type_key == 'interrogation_transcript':
            # **Det. Torres:** dialogue text → count "dialogue text"
            match = re.match(r'^\*\*[^*]+:\*\*\s*(.*)', stripped)
            if match:
                narrative_lines.append(match.group(1))
                continue
        # Skip timestamp markers
        if re.match(r'^\[\d{2}:\d{2}', stripped):
            # But include any text after the timestamp
            after = re.sub(r'^\[\d{2}:\d{2}[:\d]*\]\s*', '', stripped)
            if after:
                narrative_lines.append(after)
            continue
        # Skip stage directions (but they add immersion so count them if substantial)
        if re.match(r'^\[.*\]$', stripped) and len(stripped.split()) <= 8:
            continue
        narrative_lines.append(stripped)

    all_text = ' '.join(narrative_lines)
    words = all_text.split()
    return len(words)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_content.py <case_dir> [<envelope>]")
        sys.exit(2)

    case_dir = Path(sys.argv[1])
    target_envelope = sys.argv[2].upper() if len(sys.argv) > 2 else None
    config_dir = case_dir.parent.parent / 'config'

    issues = []
    def fail(msg): issues.append(("FAIL", msg))
    def warn(msg): issues.append(("WARN", msg))

    # Load required files
    try:
        catalog = load_json(case_dir / 'clue_catalog.json')
        plan = load_json(case_dir / 'case-plan.json')
    except FileNotFoundError as e:
        print(f"FAIL: Missing required file: {e}")
        sys.exit(1)

    # V9: Load doc_type_catalog as primary, template_registry as fallback
    doc_type_catalog_path = config_dir / 'doc_type_catalog.json'
    registry_path = config_dir / 'template_registry.json'
    doc_type_catalog = load_json(doc_type_catalog_path) if doc_type_catalog_path.exists() else {'types': {}}
    registry = load_json(registry_path) if registry_path.exists() else {'templates': {}}

    docs = catalog.get('documents', [])
    poi_names = {p.get('id'): p.get('name', '') for p in plan.get('pois', []) if isinstance(p, dict)}

    # Filter by envelope if specified
    if target_envelope:
        docs = [d for d in docs if d.get('envelope') == target_envelope]
        if not docs:
            fail(f"No documents found for envelope {target_envelope}")

    # Quality floors: doc_type_catalog (primary), template_registry (fallback)
    quality_floors = {}
    # Load from doc_type_catalog by type_key
    for type_key, type_info in doc_type_catalog.get('types', {}).items():
        quality_floors[type_key] = {
            'min_words': type_info.get('min_narrative_words', 100),
            'type_key': type_key,
        }
    # Legacy fallback from template_registry by type_id
    for tid, tpl in registry.get('templates', {}).items():
        tk = tpl.get('type_key', '')
        if tk and tk not in quality_floors:
            quality_floors[tk] = {
                'min_words': tpl.get('min_narrative_words', 50),
                'type_key': tk,
            }

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        did = doc.get('doc_id', '?')
        envelope = doc.get('envelope', '?')
        type_key = doc.get('type_key', '')
        tid = str(doc.get('type_id', ''))
        prefix = f"[{did}]"

        # Find the _content.md file
        content_path = case_dir / f'envelope_{envelope}' / f'{did}_content.md'
        if not content_path.exists():
            fail(f"{prefix} Missing file: {content_path.name}")
            continue

        content = content_path.read_text(encoding='utf-8')

        # ── Check 1: Not empty ──
        if len(content.strip()) < 10:
            fail(f"{prefix} Content file is nearly empty ({len(content.strip())} chars)")
            continue

        # ── Check 2: No placeholders ──
        for pattern in KNOWN_PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                fail(f"{prefix} Contains placeholder pattern: '{matches[0]}'")

        # ── Check 3: No HTML tags ──
        html_matches = HTML_TAG_PATTERN.findall(content)
        if html_matches:
            fail(f"{prefix} Contains HTML tags (must be plain Markdown): {html_matches[:3]}")

        # ── Check 4: Word count meets quality floor ──
        floor = quality_floors.get(type_key, {'min_words': 100, 'type_key': type_key})
        word_count = count_narrative_words(content, type_key)
        min_words = floor.get('min_words', 100) or 100

        if word_count < min_words:
            fail(f"{prefix} Narrative word count {word_count} < minimum {min_words} for {type_key}")

        # ── Check 5: key_mandatory_line present ──
        brief = doc.get('production_brief_writing', {})
        if isinstance(brief, dict):
            kml = brief.get('key_mandatory_line', '')
            if kml and len(kml) >= 10:
                # Check if the key line (or close variant) appears in content
                # Use fuzzy: check if key phrases from the line appear
                kml_words = set(kml.lower().split())
                content_lower = content.lower()
                # Check at least 60% of significant words appear
                significant_words = {w for w in kml_words if len(w) > 3}
                if significant_words:
                    found = sum(1 for w in significant_words if w in content_lower)
                    coverage = found / len(significant_words)
                    if coverage < 0.5:
                        warn(f"{prefix} key_mandatory_line may be missing — only {found}/{len(significant_words)} key words found in content")

        # ── Check 6: POI name consistency ──
        for poi_id, poi_name in poi_names.items():
            if poi_name and len(poi_name) > 3:
                # Check if this doc references this POI
                refs = doc.get('pois_referenced', [])
                if poi_id in refs:
                    # The POI should be mentioned by name in the content
                    name_parts = poi_name.split()
                    last_name = name_parts[-1] if name_parts else ''
                    if last_name and len(last_name) > 2 and last_name.lower() not in content.lower():
                        warn(f"{prefix} References {poi_id} ({poi_name}) but name not found in content")

        # ── Check 7: Type-specific checks ──

        # Interviews (type 11)
        if tid == '11':
            interview_brief = doc.get('production_brief_interview', {})
            if isinstance(interview_brief, dict):
                min_exchanges = interview_brief.get('min_exchanges', 16)
                # Count exchanges (lines starting with **SpeakerName:**)
                exchanges = len(re.findall(r'^\*\*[^*]+:\*\*', content, re.MULTILINE))
                if exchanges < (min_exchanges or 16):
                    fail(f"{prefix} Interview has {exchanges} exchanges, minimum {min_exchanges}")

                # Check for the_lie content
                the_lie = interview_brief.get('the_lie', '')
                if the_lie and len(the_lie) > 10:
                    # Fuzzy check: key words from the_lie should appear
                    lie_words = {w.lower() for w in the_lie.split() if len(w) > 4}
                    if lie_words:
                        found = sum(1 for w in lie_words if w in content.lower())
                        if found < len(lie_words) * 0.3:
                            warn(f"{prefix} the_lie content may be missing from interview")

                # Check for the_slip content
                the_slip = interview_brief.get('the_slip', {})
                if isinstance(the_slip, dict):
                    slip_what = the_slip.get('what', '')
                    if slip_what and len(slip_what) > 10:
                        slip_words = {w.lower() for w in slip_what.split() if len(w) > 4}
                        if slip_words:
                            found = sum(1 for w in slip_words if w in content.lower())
                            if found < len(slip_words) * 0.3:
                                warn(f"{prefix} the_slip content may be missing from interview")

        # 911 transcripts (type 6)
        if tid == '6':
            brief_911 = doc.get('production_brief_911', {})
            if isinstance(brief_911, dict):
                min_ex = brief_911.get('min_exchanges', 12)
                exchanges = len(re.findall(r'^\*\*[^*]+:\*\*', content, re.MULTILINE))
                if exchanges < (min_ex or 12):
                    fail(f"{prefix} 911 transcript has {exchanges} exchanges, minimum {min_ex}")

                # Check for timestamps
                timestamps = re.findall(r'\[\d{2}:\d{2}', content)
                if len(timestamps) < 3:
                    warn(f"{prefix} 911 transcript has few timestamps ({len(timestamps)}) — should have regular time markers")

        # Forensic reports (type 10)
        if tid == '10':
            # Method section should be substantial
            if 'method' in content.lower() or 'procedure' in content.lower() or 'examination' in content.lower():
                pass  # Good, has method section
            else:
                warn(f"{prefix} Forensic report may be missing method/examination section")

            # Should have specific measurements
            measurements = re.findall(r'\d+\.?\d*\s*(?:cm|mm|mg|ml|kg|lb|inch|°[CF])', content)
            if len(measurements) < 2:
                warn(f"{prefix} Forensic report has few measurements ({len(measurements)}) — should have ≥3 specific findings")

        # Entry/exit logs (type 8)
        if tid == '8':
            # Count log entries (lines with times)
            time_entries = re.findall(r'\d{1,2}:\d{2}', content)
            if len(time_entries) < 10:
                warn(f"{prefix} Entry/exit log has {len(time_entries)} time entries — should have ≥10")

        # Witness statements (type 16)
        if tid == '16':
            if word_count < 200:
                fail(f"{prefix} Witness statement has {word_count} narrative words — minimum 200")

    # ── Write report ──
    report_dir = case_dir / 'qa'
    report_dir.mkdir(parents=True, exist_ok=True)
    envelope_suffix = f'_{target_envelope}' if target_envelope else ''
    report_path = report_dir / f'validate_content{envelope_suffix}_report.md'

    lines = [f"# Content Validation Report{f' — Envelope {target_envelope}' if target_envelope else ''}", ""]
    fails = sum(1 for i in issues if i[0] == "FAIL")
    warns = sum(1 for i in issues if i[0] == "WARN")
    lines.append(f"**Result: {'FAIL' if fails > 0 else 'PASS'}**")
    lines.append(f"- FAIL: {fails}")
    lines.append(f"- WARN: {warns}")
    lines.append(f"- Documents checked: {len(docs)}")
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
    print(f"\n{'PASS' if fails == 0 else 'FAIL'} — {fails} fails, {warns} warnings ({len(docs)} docs checked)")
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    main()
