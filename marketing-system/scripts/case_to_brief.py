#!/usr/bin/env python3
"""Extracts an enriched weekly_case_brief.json from a Declassified Cases pipeline output.

Reads case-plan.json, scene_descriptions.json, art_briefs.json, clue_catalog.json,
and experience_design.json to produce a rich brief that marketing agents can consume.

Usage:
    python3 case_to_brief.py <product_id> <week> <case_dir>

Example:
    python3 case_to_brief.py misterio-semanal 2026-W16 ~/.openclaw/workspace-declassified/cases/exports/cyber-ghost/
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")

MAX_SCENES = 5
MAX_CLUES = 8


def load_json(path: Path) -> dict | list | None:
    """Load JSON file, return None if missing."""
    if path.exists():
        return json.loads(path.read_text())
    return None


def extract_case_info(case_plan: dict) -> dict:
    """Extract case metadata from case-plan.json. Anti-spoiler: omit culprit identity."""
    suspects = []
    for poi in case_plan.get("pois", []):
        if poi.get("status") == "deceased":
            continue  # skip victim as suspect
        suspects.append({
            "name": poi["name"],
            "occupation": poi.get("role", ""),
            "why_suspicious": poi.get("surface_motive", ""),
        })

    # Build emotional arc from envelopes if available
    emotional_arc = {}
    if "emotional_arc" in case_plan:
        emotional_arc = case_plan["emotional_arc"]
    else:
        # Try to infer from structure
        for key in ["envelope_A", "envelope_B", "envelope_C", "envelope_R"]:
            if key in case_plan:
                emotional_arc[key] = case_plan[key]

    victim = case_plan.get("victim", {})

    return {
        "title": case_plan.get("title", ""),
        "slug": case_plan.get("slug", ""),
        "logline": case_plan.get("logline", ""),
        "setting": case_plan.get("setting", {}),
        "victim": {
            "name": victim.get("name", ""),
            "age": victim.get("age"),
            "occupation": victim.get("occupation", ""),
            "cause_of_death": victim.get("cause_of_death", ""),
        },
        "suspects": suspects,
        "emotional_arc": emotional_arc,
    }


def extract_experience_summary(case_plan: dict, experience_design: dict | None) -> dict:
    """Extract experience summary from case-plan and experience_design."""
    summary = {
        "envelopes": 4,  # default
        "total_documents": 0,
        "estimated_duration_hours": "2-4",
        "difficulty": case_plan.get("tier", "NORMAL"),
    }

    if experience_design:
        doc_map = experience_design.get("document_experience_map", {})
        summary["total_documents"] = len(doc_map)
        summary["experiential_style"] = experience_design.get("experiential_style", "")
        detective = experience_design.get("detective_persona", {})
        if detective:
            summary["detective_name"] = detective.get("name", "")

    return summary


def extract_scenes_for_video(scene_descriptions: dict | None) -> list:
    """Extract the most cinematic scenes for video prompts."""
    if not scene_descriptions:
        return []

    scenes = scene_descriptions.get("scenes", [])
    result = []
    for scene in scenes[:MAX_SCENES]:
        result.append({
            "scene_id": f"scene_{scene.get('for_doc', '')}",
            "for_doc": scene.get("for_doc", ""),
            "location": scene.get("location", ""),
            "visual_description": scene.get("visual_description", ""),
            "lighting": scene.get("lighting", ""),
            "atmosphere": scene.get("atmosphere", ""),
            "notable_objects": scene.get("notable_objects", []),
            "time_of_day": scene.get("time_of_day", ""),
            "marketing_use": _infer_marketing_use(scene),
        })

    return result


def _infer_marketing_use(scene: dict) -> str:
    """Infer how a scene can be used in marketing."""
    doc = scene.get("for_doc", "")
    if doc == "A1":
        return "Hook scene — discovery / crime scene"
    elif doc == "A2":
        return "Suspect lineup — detective board"
    elif "B" in doc:
        return "Investigation deepening — interrogation/evidence"
    elif "C" in doc:
        return "Revelation scene — critical evidence"
    elif "R" in doc:
        return "Resolution — case solved"
    return "Atmospheric / world-building"


def extract_poi_headshot_prompts(art_briefs: dict | None, case_plan: dict) -> list:
    """Extract DALL-E prompts for POI headshots."""
    if not art_briefs:
        return []

    briefs = art_briefs.get("briefs", [])
    poi_map = {p["id"]: p for p in case_plan.get("pois", [])}

    result = []
    seen_pois = set()
    for brief in briefs:
        if not brief.get("dall_e_prompt"):
            continue  # skip reuse entries
        poi_id = brief.get("for_poi", "")
        if poi_id in seen_pois:
            continue  # one prompt per POI
        seen_pois.add(poi_id)

        poi_info = poi_map.get(poi_id, {})
        result.append({
            "image_id": brief["image_id"],
            "name": poi_info.get("name", ""),
            "role": "victim" if poi_info.get("status") == "deceased" else "suspect",
            "dall_e_prompt": brief["dall_e_prompt"],
            "dall_e_params": brief.get("dall_e_params", {
                "model": "dall-e-3",
                "quality": "hd",
                "size": "1024x1024",
                "n": 1,
            }),
        })

    return result


def extract_key_clues(clue_catalog: dict | None) -> list:
    """Extract the most dramatic/visual clues for marketing hooks."""
    if not clue_catalog:
        return []

    documents = clue_catalog.get("documents", [])
    clues = []

    for doc in documents:
        doc_id = doc.get("doc_id", "")
        title = doc.get("in_world_title", "")
        player_inference = doc.get("player_inference", "")
        reveals = doc.get("reveals", "")

        if player_inference:
            clues.append({
                "doc_id": doc_id,
                "document_title": title,
                "clue_description": player_inference[:200],
                "intrigue_level": "high" if doc.get("envelope") in ("A", "C") else "medium",
                "hook_potential": _generate_hook_from_inference(player_inference),
            })

    # Sort by intrigue level and take top clues
    clues.sort(key=lambda x: 0 if x["intrigue_level"] == "high" else 1)
    return clues[:MAX_CLUES]


def _generate_hook_from_inference(inference: str) -> str:
    """Generate a hook question from a player inference."""
    # Simple heuristic: turn the inference into a question-style hook
    if len(inference) > 100:
        inference = inference[:100] + "..."
    return inference


def extract_social_media_plan(case_plan: dict) -> list:
    """Extract social media plan from case-plan if available."""
    plan = case_plan.get("social_media_plan", [])
    if isinstance(plan, list):
        return plan
    if isinstance(plan, dict):
        result = []
        for platform, details in plan.items():
            entry = {"platform": platform}
            if isinstance(details, dict):
                entry.update(details)
            elif isinstance(details, str):
                entry["case_purpose"] = details
            result.append(entry)
        return result
    return []


def generate_hook_angles(case_plan: dict, clues: list) -> list:
    """Generate hook angles from case data."""
    hooks = []

    logline = case_plan.get("logline", "")
    if logline:
        hooks.append(logline)

    victim = case_plan.get("victim", {})
    suspects = [p for p in case_plan.get("pois", []) if p.get("status") != "deceased"]

    if victim.get("name") and victim.get("cause_of_death"):
        hooks.append(f"{victim['name']} — {victim['cause_of_death']}")

    if len(suspects) > 0:
        hooks.append(f"{len(suspects)} sospechosos. Todos tienen motivo. Solo uno es culpable.")

    setting = case_plan.get("setting", {})
    if setting.get("atmosphere"):
        hooks.append(setting["atmosphere"][:120])

    for clue in clues[:3]:
        if clue.get("hook_potential"):
            hooks.append(clue["hook_potential"][:120])

    return hooks[:8]


def build_enriched_brief(product_id: str, week: str, case_dir: Path) -> dict:
    """Build the enriched weekly_case_brief.json."""
    # Load all source files
    case_plan = load_json(case_dir / "case-plan.json")
    if not case_plan:
        raise FileNotFoundError(f"case-plan.json not found in {case_dir}")

    scene_descriptions = load_json(case_dir / "scene_descriptions.json")
    art_briefs = load_json(case_dir / "art_briefs.json")
    clue_catalog = load_json(case_dir / "clue_catalog.json")
    experience_design = load_json(case_dir / "experience_design.json")

    # Extract components
    case_info = extract_case_info(case_plan)
    experience_summary = extract_experience_summary(case_plan, experience_design)
    scenes = extract_scenes_for_video(scene_descriptions)
    poi_prompts = extract_poi_headshot_prompts(art_briefs, case_plan)
    key_clues = extract_key_clues(clue_catalog)
    social_plan = extract_social_media_plan(case_plan)
    hook_angles = generate_hook_angles(case_plan, key_clues)

    brief = {
        "schema_version": "2.0",
        "product_id": product_id,
        "week": week,
        "generated_at": datetime.now().isoformat(),
        "source_case_dir": str(case_dir),
        "source_case_slug": case_plan.get("slug", ""),
        "case": {
            **case_info,
            "experience_summary": experience_summary,
        },
        "marketing_assets": {
            "scenes_for_video": scenes,
            "poi_headshot_prompts": poi_prompts,
            "key_clues_for_hooks": key_clues,
            "social_media_plan_from_case": social_plan,
        },
        "hook_angles_from_case": hook_angles,
    }

    return brief


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 case_to_brief.py <product_id> <week> <case_dir>")
        print("Example: python3 case_to_brief.py misterio-semanal 2026-W16 /path/to/case/")
        sys.exit(1)

    product_id = sys.argv[1]
    week = sys.argv[2]
    case_dir = Path(sys.argv[3]).expanduser().resolve()

    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}")
        sys.exit(1)

    # Build brief
    print(f"Extracting case brief from {case_dir}")
    brief = build_enriched_brief(product_id, week, case_dir)

    # Save to weekly_runs
    product_dir = PRODUCTS_DIR / product_id
    run_dir = product_dir / "weekly_runs" / week
    run_dir.mkdir(parents=True, exist_ok=True)

    output_path = run_dir / "weekly_case_brief.json"
    output_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False))

    # Summary
    case = brief["case"]
    assets = brief["marketing_assets"]
    print(f"\n{'='*50}")
    print(f"ENRICHED BRIEF — {product_id} ({week})")
    print(f"{'='*50}")
    print(f"Case: {case['title']} ({case['slug']})")
    print(f"Victim: {case['victim']['name']}")
    print(f"Suspects: {len(case['suspects'])}")
    print(f"Scenes for video: {len(assets['scenes_for_video'])}")
    print(f"POI headshot prompts: {len(assets['poi_headshot_prompts'])}")
    print(f"Key clues for hooks: {len(assets['key_clues_for_hooks'])}")
    print(f"Hook angles: {len(brief['hook_angles_from_case'])}")
    print(f"\nSaved to: {output_path}")
    print(f"Size: {len(json.dumps(brief)):,} chars")


if __name__ == "__main__":
    main()
