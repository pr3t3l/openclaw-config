#!/usr/bin/env python3
"""
spawn_images.py — Generate POI canonical portraits via DALL-E 3

Reads art_briefs.json, generates canonical portraits (non-reusable briefs),
downloads images, and creates 100px JPEG q70 thumbnails for API embedding.

Usage: python3 spawn_images.py <case_slug> [--dry-run] [--skip-existing]

Requires:
  - OPENAI_API_KEY in environment or ~/.openclaw/.env
  - PIL/Pillow for thumbnail generation
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

WORKSPACE = Path('/home/robotin/.openclaw/workspace-declassified')
COST_PER_IMAGE = 0.04  # DALL-E 3 standard 1024x1024


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_openai_key():
    """Load OpenAI key from env or .env file (prefers OPENAI_IMAGE_GEN_KEY)."""
    key = os.environ.get('OPENAI_IMAGE_GEN_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
    if key:
        return key
    env_path = WORKSPACE.parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith('OPENAI_IMAGE_GEN_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith('OPENAI_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise ValueError(
        'OPENAI_IMAGE_GEN_KEY / OPENAI_API_KEY not set. '
        'Set it in environment or ~/.openclaw/.env'
    )


def generate_image(api_key, prompt, size='1024x1024', quality='standard'):
    """Call DALL-E 3 via curl and return the image URL."""
    payload = json.dumps({
        'model': 'dall-e-3',
        'prompt': prompt,
        'n': 1,
        'size': size,
        'quality': quality,
        'response_format': 'url'
    }, ensure_ascii=True)

    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
        f.write(payload.encode('utf-8'))
        tmp_path = f.name

    try:
        result = subprocess.run([
            'curl', '-s', '-S', '--max-time', '120',
            'https://api.openai.com/v1/images/generations',
            '-H', f'Authorization: Bearer {api_key}',
            '-H', 'Content-Type: application/json',
            '--data-binary', f'@{tmp_path}'
        ], capture_output=True, text=True, timeout=130)

        if result.returncode != 0:
            raise Exception(f'curl failed (rc={result.returncode}): {result.stderr[:200]}')

        if not result.stdout.strip():
            raise Exception(f'Empty response. stderr: {result.stderr[:200]}')

        response = json.loads(result.stdout)

        if 'error' in response:
            err = response['error']
            raise Exception(f'API error: {err.get("message", str(err))}')

        data = response.get('data', [])
        if not data:
            raise Exception(f'No image data in response: {result.stdout[:300]}')

        return data[0].get('url', ''), data[0].get('revised_prompt', '')

    finally:
        os.unlink(tmp_path)


def download_image(url, dest_path):
    """Download an image URL to disk via curl."""
    result = subprocess.run([
        'wget', '-q', '-O', str(dest_path), url
    ], capture_output=True, text=True, timeout=70)

    if result.returncode != 0:
        raise Exception(f'Download failed: {result.stderr[:200]}')

    if not dest_path.exists() or dest_path.stat().st_size < 1000:
        raise Exception(f'Downloaded file too small or missing: {dest_path}')

    return dest_path.stat().st_size


def create_thumbnail(src_path, thumb_path, max_width=100, quality=70):
    """Resize image to max_width and save as JPEG q70 thumbnail (TL-02)."""
    if not HAS_PIL:
        print(f"    WARN: PIL not available, skipping thumbnail for {src_path.name}")
        return False

    img = Image.open(src_path)
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(thumb_path, format='JPEG', quality=quality)
    return True


def log_cost_to_manifest(case_dir, count, failures, total_cost):
    """Log image generation cost to manifest.json."""
    manifest_path = case_dir / 'manifest.json'
    if not manifest_path.exists():
        return
    try:
        manifest = load_json(manifest_path)
        if 'cost_tracking' not in manifest:
            manifest['cost_tracking'] = {'phases': {}, 'totals': {}, 'images': {}}
        ct = manifest['cost_tracking']

        # Update images section
        images = ct.setdefault('images', {})
        images['generated'] = (images.get('generated') or 0) + count
        images['failed'] = (images.get('failed') or 0) + failures
        images['model'] = 'dall-e-3'
        images['total_cost'] = round((images.get('total_cost') or 0) + total_cost, 4)

        # Update totals
        totals = ct.setdefault('totals', {})
        totals['images_generated'] = (totals.get('images_generated') or 0) + count
        totals['estimated_total_usd'] = round(
            (totals.get('estimated_total_usd') or 0) + total_cost, 4)

        # Update pipeline state
        if 'pipeline_state' not in manifest:
            manifest['pipeline_state'] = {}
        manifest['pipeline_state']['image_generation'] = 'completed'

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"  Cost logged to manifest.json")
    except Exception as e:
        print(f"  WARN: Could not update manifest: {e}")


def main():
    parser = argparse.ArgumentParser(description='Generate POI portraits via DALL-E 3')
    parser.add_argument('slug', help='Case slug')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be generated without calling API')
    parser.add_argument('--skip-existing', action='store_true',
                        help='Skip briefs where the image file already exists')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Seconds between API calls to avoid rate limits (default: 2)')
    args = parser.parse_args()

    slug = args.slug
    case_dir = WORKSPACE / 'cases' / 'exports' / slug
    canonical_dir = case_dir / 'visuals' / 'canonical'

    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        sys.exit(1)

    # Ensure canonical directory exists early
    canonical_dir.mkdir(parents=True, exist_ok=True)

    briefs_path = case_dir / 'art_briefs.json'
    if not briefs_path.exists():
        print(f"ERROR: art_briefs.json not found at {briefs_path}")
        sys.exit(1)

    briefs_data = load_json(briefs_path)
    brief_list = briefs_data.get('briefs', briefs_data.get('art_briefs', []))

    # Filter to non-reusable briefs (canonical portraits to generate)
    to_generate = []
    for b in brief_list:
        if not isinstance(b, dict):
            continue
        if b.get('reusable_from_library', False):
            continue
        filename = b.get('filename', '')
        if not filename:
            continue
        prompt = b.get('dall_e_prompt', b.get('prompt', ''))
        if not prompt:
            print(f"  SKIP: {filename} — no dall_e_prompt")
            continue
        to_generate.append({
            'filename': filename,
            'prompt': prompt,
            'poi': b.get('for_poi', ''),
            'image_id': b.get('image_id', ''),
            'params': b.get('dall_e_params', {}),
        })

    if not to_generate:
        print("No canonical portraits to generate.")
        return

    print(f"POI Portrait Generation (DALL-E 3)")
    print(f"  Case: {slug}")
    print(f"  Portraits to generate: {len(to_generate)}")
    print(f"  Estimated cost: ${len(to_generate) * COST_PER_IMAGE:.2f}")
    print()

    if args.dry_run:
        for i, brief in enumerate(to_generate, 1):
            print(f"  [{i}] {brief['filename']} (POI: {brief['poi']})")
            print(f"      Prompt: {brief['prompt'][:100]}...")
        print(f"\nDry run complete. Would generate {len(to_generate)} images.")
        return

    api_key = load_openai_key()
    generated = 0
    failed = 0

    for i, brief in enumerate(to_generate, 1):
        filename = brief['filename']
        dest_path = case_dir / filename
        thumb_path = case_dir / Path(filename).parent / (Path(filename).stem + '_thumb.jpg')

        # Skip existing if requested
        if args.skip_existing and dest_path.exists() and dest_path.stat().st_size > 1000:
            print(f"  [{i}/{len(to_generate)}] SKIP (exists): {filename}")
            continue

        print(f"  [{i}/{len(to_generate)}] Generating: {filename} (POI: {brief['poi']})")
        print(f"    Prompt: {brief['prompt'][:80]}...")

        try:
            url, revised_prompt = generate_image(api_key, brief['prompt'])
            if revised_prompt and revised_prompt != brief['prompt']:
                print(f"    Revised prompt: {revised_prompt[:80]}...")

            size_bytes = download_image(url, dest_path)
            size_kb = size_bytes / 1024
            print(f"    Downloaded: {dest_path.name} ({size_kb:.0f}KB)")

            # Create thumbnail
            if create_thumbnail(dest_path, thumb_path):
                thumb_kb = thumb_path.stat().st_size / 1024
                print(f"    Thumbnail: {thumb_path.name} ({thumb_kb:.1f}KB)")

            generated += 1

        except Exception as e:
            print(f"    ERROR: {e}")
            failed += 1

        # Rate limit delay between calls
        if i < len(to_generate):
            time.sleep(args.delay)

    print()
    print(f"Results: {generated} generated, {failed} failed")
    print(f"Total cost: ${generated * COST_PER_IMAGE:.2f}")

    # Log to manifest
    if generated > 0 or failed > 0:
        log_cost_to_manifest(case_dir, generated, failed, generated * COST_PER_IMAGE)

    print("\nDone.")


if __name__ == '__main__':
    main()
