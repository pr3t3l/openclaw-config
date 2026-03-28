#!/usr/bin/env python3
"""Generates marketing videos using Google Veo 3 from video prompts or script hooks.

Reads video_prompts_draft.json (or falls back to reels_scripts_draft.json)
and calls Veo 3 via the Google GenAI SDK to generate short-form vertical videos.

Usage:
    python3 generate_marketing_videos.py <product_id> <week> [--quality standard]
    # Default: fast mode (~$1.20/video of 8s)
    # --quality standard: ~$3.20/video for final production

Dependencies:
    pip install google-genai --break-system-packages
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")
ENV_PATH = Path("/home/robotin/.openclaw/.env")

FAST_MODEL = "veo-3.0-fast-generate-001"
STANDARD_MODEL = "veo-3.0-generate-001"
FAST_RATE = 0.15   # $/second
STANDARD_RATE = 0.40  # $/second
DEFAULT_DURATION = 8

POLL_INTERVAL = 20
MAX_POLLS = 60  # 20min max wait


def load_env():
    """Load .env file into environment."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


def get_api_key() -> str:
    """Get Google API key from environment."""
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("Error: GOOGLE_API_KEY or GEMINI_API_KEY not found in .env")
        sys.exit(1)
    return key


def build_veo_prompt(video_prompt: dict) -> str:
    """Combine scene descriptions into a single Veo3 prompt."""
    veo3 = video_prompt.get("veo3_prompt", {})
    scenes = veo3.get("scenes", [])
    style = video_prompt.get("style", "ugc_feeling")

    parts = [f"Style: {style} video for social media marketing."]

    if veo3.get("overall_direction"):
        parts.append(veo3["overall_direction"])

    for scene in scenes:
        visual = scene.get("visual_prompt", "")
        camera = scene.get("camera_direction", "")
        text_overlay = scene.get("text_overlay", "")
        audio = scene.get("audio_notes", "")

        scene_desc = visual
        if camera:
            scene_desc += f" Camera: {camera}."
        if text_overlay:
            scene_desc += f" Text overlay: '{text_overlay}'."
        if audio:
            scene_desc += f" Audio: {audio}."
        parts.append(scene_desc)

    return " ".join(parts)


def build_prompt_from_script(script: dict) -> str:
    """Build a basic Veo3 prompt from a script's hook when video_prompts aren't available."""
    hook = script.get("hook", {})
    body = script.get("body", {})
    cta = script.get("cta", {})

    parts = ["Style: ugc_feeling vertical video for TikTok/Instagram Reels marketing."]

    if hook.get("visual"):
        parts.append(f"Opening scene: {hook['visual']}")
    if hook.get("text"):
        parts.append(f"Text overlay: '{hook['text']}'")
    if body.get("text"):
        parts.append(f"Middle: {body.get('visual', body['text'][:100])}")
    if cta.get("visual"):
        parts.append(f"Closing: {cta['visual']}")

    return " ".join(parts)


def generate_video(client, model: str, prompt: str, output_path: Path,
                   aspect_ratio: str = "9:16") -> dict:
    """Generate a video using Veo 3. Returns result dict."""
    from google.genai import types

    config = types.GenerateVideosConfig(aspect_ratio=aspect_ratio)

    try:
        operation = client.models.generate_videos(
            model=model,
            prompt=prompt,
            config=config,
        )

        polls = 0
        while not operation.done:
            if polls >= MAX_POLLS:
                return {"status": "failed", "error": f"Timeout after {polls * POLL_INTERVAL}s"}
            time.sleep(POLL_INTERVAL)
            operation = client.operations.get(operation)
            polls += 1
            if polls % 3 == 0:
                print(f"      Polling... ({polls * POLL_INTERVAL}s)")

        if not operation.result or not operation.result.generated_videos:
            return {"status": "failed", "error": "No video in result"}

        video = operation.result.generated_videos[0]
        client.files.download(file=video.video)
        video.video.save(str(output_path))

        return {"status": "generated", "error": None}

    except Exception as e:
        error_msg = str(e)
        # Check for content policy
        if "safety" in error_msg.lower() or "policy" in error_msg.lower() or "blocked" in error_msg.lower():
            return {"status": "failed", "error": f"Content policy: {error_msg[:200]}"}
        return {"status": "failed", "error": error_msg[:300]}


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 generate_marketing_videos.py <product_id> <week> [--quality standard]")
        sys.exit(1)

    product_id = sys.argv[1]
    week = sys.argv[2]
    quality = "fast"
    if "--quality" in sys.argv:
        idx = sys.argv.index("--quality")
        if idx + 1 < len(sys.argv):
            quality = sys.argv[idx + 1]

    model = STANDARD_MODEL if quality == "standard" else FAST_MODEL
    rate = STANDARD_RATE if quality == "standard" else FAST_RATE

    load_env()
    api_key = get_api_key()

    from google import genai
    client = genai.Client(api_key=api_key)

    product_dir = PRODUCTS_DIR / product_id
    run_dir = product_dir / "weekly_runs" / week
    drafts_dir = run_dir / "drafts"
    videos_dir = drafts_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    # Load video prompts or fall back to scripts
    video_prompts_path = drafts_dir / "video_prompts_draft.json"
    scripts_path = drafts_dir / "reels_scripts_draft.json"

    prompts_to_generate = []

    if video_prompts_path.exists():
        vp_data = json.loads(video_prompts_path.read_text())
        for vp in vp_data.get("video_prompts", []):
            prompts_to_generate.append({
                "video_id": vp.get("video_id", f"V-{len(prompts_to_generate)+1:03d}"),
                "source_script_id": vp.get("source_script_id", ""),
                "creative_id": vp.get("creative_id", ""),
                "persona_id": vp.get("persona_id", ""),
                "prompt": build_veo_prompt(vp),
                "duration": vp.get("duration", DEFAULT_DURATION),
            })
        print(f"Loaded {len(prompts_to_generate)} prompts from video_prompts_draft.json")
    elif scripts_path.exists():
        scripts_data = json.loads(scripts_path.read_text())
        for lane in scripts_data.get("lanes", []):
            # Generate video for first script of each lane only (to save cost)
            scripts = lane.get("scripts", [])
            if scripts:
                s = scripts[0]
                prompts_to_generate.append({
                    "video_id": f"V-{week}-{s.get('script_id', len(prompts_to_generate)+1)}",
                    "source_script_id": s.get("script_id", ""),
                    "creative_id": s.get("creative_id", ""),
                    "persona_id": lane.get("persona_id", ""),
                    "prompt": build_prompt_from_script(s),
                    "duration": s.get("duration_seconds", DEFAULT_DURATION),
                })
        print(f"Loaded {len(prompts_to_generate)} prompts from reels_scripts_draft.json (fallback)")
    else:
        print("Error: No video_prompts_draft.json or reels_scripts_draft.json found")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"VIDEO GENERATION — {product_id} ({week})")
    print(f"Model: {model} ({quality})")
    print(f"Rate: ${rate}/second")
    print(f"Videos to generate: {len(prompts_to_generate)}")
    print(f"{'='*50}")

    manifest_videos = []
    total_cost = 0.0
    generated = 0
    failed = 0

    for i, vp in enumerate(prompts_to_generate):
        video_id = vp["video_id"]
        output_path = videos_dir / f"{video_id}.mp4"
        duration = vp["duration"]
        cost = duration * rate

        print(f"\n  [{i+1}/{len(prompts_to_generate)}] {video_id}")
        print(f"    Persona: {vp['persona_id']}")
        print(f"    Prompt: {vp['prompt'][:100]}...")
        print(f"    Est. cost: ${cost:.2f}")

        result = generate_video(client, model, vp["prompt"], output_path)

        if result["status"] == "failed" and result.get("error"):
            # Retry once with simplified prompt
            print(f"    Failed: {result['error'][:100]}")
            print(f"    Retrying with simplified prompt...")
            simple_prompt = vp["prompt"][:500]  # Truncate to simplify
            result = generate_video(client, model, simple_prompt, output_path)

        entry = {
            "video_id": video_id,
            "source_script_id": vp["source_script_id"],
            "creative_id": vp["creative_id"],
            "persona_id": vp["persona_id"],
            "file_path": f"videos/{video_id}.mp4",
            "duration_seconds": duration,
            "aspect_ratio": "9:16",
            "cost_usd": cost if result["status"] == "generated" else 0,
            "status": result["status"],
            "error": result.get("error"),
        }
        manifest_videos.append(entry)

        if result["status"] == "generated":
            generated += 1
            total_cost += cost
            print(f"    ✅ Generated (${cost:.2f})")
        else:
            failed += 1
            print(f"    ❌ Failed: {result.get('error', 'unknown')[:100]}")

    # Save manifest
    manifest = {
        "product_id": product_id,
        "week": week,
        "generated_at": datetime.now().isoformat(),
        "model": model,
        "quality": quality,
        "videos": manifest_videos,
        "total_cost_usd": round(total_cost, 2),
        "total_generated": generated,
        "total_failed": failed,
    }
    manifest_path = videos_dir / "video_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Done: {generated} generated, {failed} failed")
    print(f"Cost: ${total_cost:.2f} ({model})")
    print(f"Videos: {videos_dir}")
    print(f"{'='*50}")

    # Telegram notification
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from telegram_sender import send_message
        send_message(
            f"🎥 Videos generados — {week}\n"
            f"{'✅' if failed == 0 else '⚠️'} {generated}/{len(prompts_to_generate)} videos generados\n"
            f"💰 Costo: ${total_cost:.2f} (Veo 3 {quality.title()})\n"
            f"📁 Guardados en weekly_runs/{week}/drafts/videos/"
        )
    except Exception:
        pass  # Telegram optional


if __name__ == "__main__":
    main()
