#!/usr/bin/env python3
"""
inject_poi_photos.py — Post-render POI portrait injection

Scans rendered HTML files in layout_specs/ for portrait placeholder divs,
matches them to POI portraits from art_briefs.json, replaces with base64
<img> tags, and re-renders to PDF via Chromium.

Runs AFTER ai_render.py, BEFORE merge/packaging.

Usage: python3 cases/scripts/inject_poi_photos.py <case_slug>
"""

import argparse
import base64
import json
import re
import subprocess
import sys
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

WORKSPACE = Path('/home/robotin/.openclaw/workspace-declassified')
RENDER_SCRIPT = WORKSPACE / 'cases' / 'render' / 'render_pdf_system_chromium.js'


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resize_image_to_base64(image_path, max_width=150):
    """Resize an image and return base64 data URI (JPEG q70)."""
    path = Path(image_path)
    if not path.exists():
        return None

    if HAS_PIL:
        img = Image.open(path)
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buf = BytesIO()
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(buf, format='JPEG', quality=70)
        data = base64.b64encode(buf.getvalue()).decode()
        return f'data:image/jpeg;base64,{data}'
    else:
        ext = path.suffix.lower().lstrip('.')
        if ext == 'jpg':
            ext = 'jpeg'
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        return f'data:image/{ext};base64,{data}'


def find_portrait_path(brief, case_dir):
    """Find the actual image file for a brief, checking multiple paths."""
    fn = brief.get('filename', '')
    if not fn:
        return None

    # Check thumbnail first, then full image
    stem = Path(fn).stem
    parent = Path(fn).parent
    thumb_candidates = [
        case_dir / parent / f'{stem}_thumb.jpg',
        case_dir / 'visuals' / 'canonical' / f'{Path(fn).name.rsplit(".", 1)[0]}_thumb.jpg',
    ]
    full_candidates = [
        case_dir / fn,
        case_dir / 'visuals' / 'canonical' / Path(fn).name,
    ]

    for p in thumb_candidates + full_candidates:
        if p.exists() and p.stat().st_size > 100:
            return p
    return None


def build_poi_map(art_briefs, case_dir):
    """Build a map of POI name -> {brief, image_path, data_uri}."""
    poi_map = {}
    for brief in art_briefs.get('briefs', []):
        if not isinstance(brief, dict):
            continue
        fn = brief.get('filename', '')
        is_poi = 'poi_' in fn.lower() or 'portrait' in fn.lower() or 'mugshot' in fn.lower()
        if not is_poi:
            continue

        poi_name = brief.get('for_poi', '')
        if not poi_name:
            continue

        img_path = find_portrait_path(brief, case_dir)
        if not img_path:
            continue

        data_uri = resize_image_to_base64(img_path, max_width=150)
        if not data_uri:
            continue

        poi_map[poi_name] = {
            'brief': brief,
            'image_path': img_path,
            'data_uri': data_uri,
        }
    return poi_map


# Regex for portrait placeholder divs
PLACEHOLDER_RE = re.compile(
    r'<div\s+class="portrait-placeholder"[^>]*>.*?</div>',
    re.DOTALL
)


def find_poi_near_placeholder(html, match_start, poi_names, window=20):
    """Search for POI names within ~20 lines of the placeholder position."""
    # Get surrounding context (roughly 20 lines before and after)
    lines = html[:match_start].split('\n')
    after_lines = html[match_start:].split('\n')

    context_before = '\n'.join(lines[-window:])
    context_after = '\n'.join(after_lines[:window])
    context = context_before + context_after

    for name in poi_names:
        # Check full name
        if name.lower() in context.lower():
            return name
        # Check last name
        parts = name.split()
        if len(parts) > 1 and parts[-1].lower() in context.lower():
            return name
        # Check first name
        if parts[0].lower() in context.lower():
            return name
    return None


def inject_portraits(html_path, poi_map):
    """Replace portrait placeholders in an HTML file. Returns list of injected POI names."""
    html = html_path.read_text(encoding='utf-8')
    poi_names = list(poi_map.keys())
    injected = []

    def replace_placeholder(match):
        placeholder_html = match.group(0)
        match_start = match.start()

        # Try to find which POI this placeholder is for
        # First check inside the placeholder div itself
        for name in poi_names:
            if name.lower() in placeholder_html.lower():
                poi = poi_map[name]
                injected.append(name)
                return f'<img src="{poi["data_uri"]}" alt="{name}" style="max-width:150px; border-radius:4px;" />'
            parts = name.split()
            if len(parts) > 1 and parts[-1].lower() in placeholder_html.lower():
                poi = poi_map[name]
                injected.append(name)
                return f'<img src="{poi["data_uri"]}" alt="{name}" style="max-width:150px; border-radius:4px;" />'

        # Search nearby context
        nearby_poi = find_poi_near_placeholder(html, match_start, poi_names)
        if nearby_poi:
            poi = poi_map[nearby_poi]
            injected.append(nearby_poi)
            return f'<img src="{poi["data_uri"]}" alt="{nearby_poi}" style="max-width:150px; border-radius:4px;" />'

        # No match found — leave placeholder
        return placeholder_html

    new_html = PLACEHOLDER_RE.sub(replace_placeholder, html)

    if injected:
        html_path.write_text(new_html, encoding='utf-8')

    return injected


def render_pdf(html_path, pdf_path):
    """Re-render HTML to PDF via Chromium."""
    if not RENDER_SCRIPT.exists():
        print(f'    WARN: render script not found: {RENDER_SCRIPT}')
        return False
    try:
        result = subprocess.run(
            ['node', str(RENDER_SCRIPT), str(html_path), str(pdf_path)],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and pdf_path.exists():
            return True
        else:
            print(f'    WARN: PDF render failed: {result.stderr[:200]}')
            return False
    except Exception as e:
        print(f'    WARN: PDF render error: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Inject POI portraits into rendered HTML documents')
    parser.add_argument('slug', help='Case slug')
    args = parser.parse_args()

    case_dir = WORKSPACE / 'cases' / 'exports' / args.slug
    if not case_dir.exists():
        print(f'ERROR: Case directory not found: {case_dir}')
        sys.exit(1)

    briefs_path = case_dir / 'art_briefs.json'
    if not briefs_path.exists():
        print(f'ERROR: art_briefs.json not found at {briefs_path}')
        sys.exit(1)

    layout_dir = case_dir / 'layout_specs'
    if not layout_dir.exists():
        print(f'ERROR: layout_specs/ not found — run ai_render.py first')
        sys.exit(1)

    art_briefs = load_json(briefs_path)
    poi_map = build_poi_map(art_briefs, case_dir)

    if not poi_map:
        print('No POI portraits found in art_briefs.json with existing image files.')
        return

    print(f'POI Portrait Injection')
    print(f'  Case: {args.slug}')
    print(f'  POIs with portraits: {len(poi_map)}')
    for name in poi_map:
        print(f'    - {name}: {poi_map[name]["image_path"].name}')
    print()

    html_files = sorted(layout_dir.glob('*.html'))
    if not html_files:
        print('No HTML files found in layout_specs/')
        return

    total_injected = 0
    files_modified = 0

    for html_path in html_files:
        doc_id = html_path.stem
        injected = inject_portraits(html_path, poi_map)

        if injected:
            files_modified += 1
            total_injected += len(injected)
            print(f'  {doc_id}: injected {len(injected)} portrait(s) — {", ".join(injected)}')

            # Re-render PDF
            pdf_path = layout_dir / f'{doc_id}.pdf'
            if render_pdf(html_path, pdf_path):
                size_kb = pdf_path.stat().st_size / 1024
                print(f'    PDF re-rendered: {pdf_path.name} ({size_kb:.0f}KB)')
            else:
                print(f'    PDF re-render failed for {doc_id}')

    print()
    print(f'Results: {total_injected} portraits injected across {files_modified} files')
    if total_injected == 0:
        print('  (No portrait placeholders found in any HTML files)')
    print('Done.')


if __name__ == '__main__':
    main()
