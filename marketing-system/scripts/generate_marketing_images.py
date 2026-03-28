#!/usr/bin/env python3
"""Generates marketing images from POI headshot prompts in the enriched weekly_case_brief.

Reads poi_headshot_prompts from weekly_case_brief.json and calls DALL-E 3 via LiteLLM
to generate the images. Saves them to weekly_runs/<week>/drafts/images/.

Usage:
    python3 generate_marketing_images.py <product_id> <week>

Example:
    python3 generate_marketing_images.py misterio-semanal 2026-W16
"""

import base64
import json
import subprocess
import sys
import tempfile
import os
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")
LITELLM_URL = "http://127.0.0.1:4000/v1/images/generations"
LITELLM_KEY = "sk-litellm-local"


def generate_image(prompt: str, params: dict, output_path: Path) -> bool:
    """Generate an image via LiteLLM DALL-E proxy. Returns True on success."""
    payload = {
        "model": params.get("model", "dall-e-3"),
        "prompt": prompt,
        "n": params.get("n", 1),
        "size": params.get("size", "1024x1024"),
        "quality": params.get("quality", "hd"),
        "response_format": "b64_json",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["curl", "-s", "-S", "--max-time", "120",
             LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {LITELLM_KEY}",
             "--data-binary", f"@{tmp_path}"],
            capture_output=True, text=True, timeout=150
        )

        if result.returncode != 0:
            print(f"    curl failed (rc={result.returncode}): {result.stderr[:200]}")
            return False

        resp = json.loads(result.stdout)

        if "error" in resp:
            print(f"    API error: {resp['error']}")
            return False

        # Extract base64 image data
        data = resp.get("data", [])
        if not data:
            print(f"    No image data in response")
            return False

        b64_data = data[0].get("b64_json", "")
        if not b64_data:
            # Try URL-based response
            url = data[0].get("url", "")
            if url:
                print(f"    Got URL response (download not implemented): {url[:80]}")
                # Save URL reference instead
                output_path.with_suffix(".url.txt").write_text(url)
                return True
            print(f"    No b64_json or url in response")
            return False

        # Decode and save
        img_bytes = base64.b64decode(b64_data)
        output_path.write_bytes(img_bytes)
        print(f"    Saved: {output_path.name} ({len(img_bytes):,} bytes)")
        return True

    except subprocess.TimeoutExpired:
        print(f"    Timeout generating image")
        return False
    except Exception as e:
        print(f"    Error: {e}")
        return False
    finally:
        os.unlink(tmp_path)


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 generate_marketing_images.py <product_id> <week>")
        sys.exit(1)

    product_id = sys.argv[1]
    week = sys.argv[2]

    product_dir = PRODUCTS_DIR / product_id
    run_dir = product_dir / "weekly_runs" / week
    brief_path = run_dir / "weekly_case_brief.json"

    if not brief_path.exists():
        print(f"Error: No weekly_case_brief.json found at {brief_path}")
        print("Run case_to_brief.py first.")
        sys.exit(1)

    brief = json.loads(brief_path.read_text())
    prompts = brief.get("marketing_assets", {}).get("poi_headshot_prompts", [])

    if not prompts:
        print("No POI headshot prompts found in brief.")
        sys.exit(0)

    # Create images directory
    images_dir = run_dir / "drafts" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"MARKETING IMAGE GENERATION — {product_id} ({week})")
    print(f"{'='*50}")
    print(f"POI headshot prompts: {len(prompts)}")

    generated = 0
    failed = 0
    manifest = []

    for prompt_info in prompts:
        image_id = prompt_info["image_id"]
        name = prompt_info.get("name", "unknown")
        role = prompt_info.get("role", "suspect")
        dall_e_prompt = prompt_info.get("dall_e_prompt", "")
        dall_e_params = prompt_info.get("dall_e_params", {})

        if not dall_e_prompt:
            print(f"  Skipping {image_id} — no prompt")
            continue

        # Clean filename
        safe_name = name.lower().replace(" ", "_").replace(".", "")
        output_path = images_dir / f"{safe_name}_{role}.png"

        print(f"\n  Generating: {name} ({role})")
        print(f"    Prompt: {dall_e_prompt[:80]}...")

        success = generate_image(dall_e_prompt, dall_e_params, output_path)
        entry = {
            "image_id": image_id,
            "name": name,
            "role": role,
            "output_path": str(output_path.relative_to(run_dir)),
            "generated": success,
            "generated_at": datetime.now().isoformat(),
        }
        manifest.append(entry)

        if success:
            generated += 1
        else:
            failed += 1

    # Save manifest
    manifest_path = images_dir / "image_manifest.json"
    manifest_data = {
        "product_id": product_id,
        "week": week,
        "generated_at": datetime.now().isoformat(),
        "total_prompts": len(prompts),
        "generated": generated,
        "failed": failed,
        "images": manifest,
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Done: {generated} generated, {failed} failed")
    print(f"Images: {images_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
