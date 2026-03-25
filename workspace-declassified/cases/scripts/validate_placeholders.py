#!/usr/bin/env python3
"""
validate_placeholders.py — Scans entire case for ANY placeholder (v6)
Usage: python3 validate_placeholders.py <case_dir>
Exit code: 0 = PASS, 1 = FAIL

Zero tolerance. Runs before render and after render.
Catches anything per-doc validator might have missed.
"""

import json
import re
import sys
from pathlib import Path

PLACEHOLDER_PATTERNS = [
    (r'\{\{[^}]+\}\}', 'Handlebars placeholder'),
    (r'\{CONTENT_FROM_MD_FILE\}', 'Content injection marker'),
    (r'<TBD>', 'TBD marker'),
    (r'\[FILL\]', 'Fill marker'),
    (r'\[TODO\]', 'TODO marker'),
    (r'PLACEHOLDER', 'Placeholder text'),
    (r'Lorem ipsum', 'Lorem ipsum filler'),
]

STUB_PATTERNS = [
    (r'"type_key"\s*:\s*"some_type"', 'Stub type_key "some_type"'),
    (r'"in_world_title"\s*:\s*"Document \d+"', 'Stub title "Document N"'),
    (r'"reveals"\s*:\s*"Reveals something', 'Stub reveals'),
    (r'"player_inference"\s*:\s*"Player infers something', 'Stub player_inference'),
    (r'"summary"\s*:\s*"Write this doc', 'Stub summary'),
    (r'"key_information_to_include"\s*:\s*\[\s*"Info"\s*\]', 'Stub key_info'),
    (r'Internal QC anchor', 'QC anchor placeholder'),
]

# Known allowed exceptions
ALLOWED_IN_JSON = {
    '"content": "{{CONTENT_FROM_MD_FILE}}"',  # This is the injection marker that inject_and_render.js processes
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_placeholders.py <case_dir>")
        sys.exit(2)

    case_dir = Path(sys.argv[1])
    if not case_dir.exists():
        print(f"ERROR: Directory not found: {case_dir}")
        sys.exit(2)

    issues = []
    files_scanned = 0

    # Scan all .md files in envelope directories
    for md_file in case_dir.glob('envelope_*/*_content.md'):
        files_scanned += 1
        text = md_file.read_text(encoding='utf-8', errors='replace')
        rel = md_file.relative_to(case_dir)

        for pattern, desc in PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                issues.append(("FAIL", f"{rel}: {desc} found: {matches[:3]}"))

    # Scan all .json files in envelope directories
    for json_file in case_dir.glob('envelope_*/*.json'):
        files_scanned += 1
        text = json_file.read_text(encoding='utf-8', errors='replace')
        rel = json_file.relative_to(case_dir)

        for pattern, desc in PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            # Filter allowed exceptions
            filtered = []
            for m in matches:
                is_allowed = False
                for allowed in ALLOWED_IN_JSON:
                    if m in allowed:
                        is_allowed = True
                        break
                if not is_allowed:
                    filtered.append(m)
            if filtered:
                issues.append(("FAIL", f"{rel}: {desc} found: {filtered[:3]}"))

    # Scan all rendered .html files
    for html_file in case_dir.glob('envelope_*/*.html'):
        files_scanned += 1
        text = html_file.read_text(encoding='utf-8', errors='replace')
        rel = html_file.relative_to(case_dir)

        # In rendered HTML, NO {{}} should remain
        unresolved = re.findall(r'\{\{[^}]+\}\}', text)
        if unresolved:
            issues.append(("FAIL", f"{rel}: Unresolved template expressions: {unresolved[:3]}"))

        for pattern, desc in PLACEHOLDER_PATTERNS[2:]:  # Skip {{}} patterns already checked
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                issues.append(("FAIL", f"{rel}: {desc} found in rendered HTML: {matches[:3]}"))

    # Scan planning files for stubs
    for planning_file in ['clue_catalog.json', 'case-plan.json']:
        pf = case_dir / planning_file
        if pf.exists():
            files_scanned += 1
            text = pf.read_text(encoding='utf-8', errors='replace')
            for pattern, desc in STUB_PATTERNS:
                matches = re.findall(pattern, text)
                if matches:
                    issues.append(("FAIL", f"{planning_file}: {desc} — {len(matches)} occurrence(s)"))

    # Scan for empty form fields in content files (rendered as form with no values)
    for md_file in case_dir.glob('envelope_*/*_content.md'):
        text = md_file.read_text(encoding='utf-8', errors='replace')
        rel = md_file.relative_to(case_dir)
        empty_fields = re.findall(r'^[A-Z][A-Z\s/()]+:\s*$', text, re.MULTILINE)
        if len(empty_fields) > 3:
            issues.append(("FAIL", f"{rel}: {len(empty_fields)} empty form fields (e.g., {empty_fields[:3]})"))

    # Report
    report_dir = case_dir / 'qa'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / 'validate_placeholders_report.md'

    fails = len(issues)
    lines = ["# Placeholder Validation Report (v6)", ""]
    lines.append(f"**Result: {'FAIL' if fails > 0 else 'PASS'}**")
    lines.append(f"- Files scanned: {files_scanned}")
    lines.append(f"- Issues found: {fails}")
    lines.append("")

    if fails > 0:
        lines.append("## Failures")
        for level, msg in issues:
            lines.append(f"- ❌ {msg}")

    report_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Report: {report_path}")
    print(f"\n{'PASS' if fails == 0 else 'FAIL'} — {fails} issues in {files_scanned} files")
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    main()
