#!/usr/bin/env python3
"""Strategy Workflow Runner — generates the 5 strategic JSONs + manifests.

Orchestrates:
  Phase S1: market_analysis (claude-sonnet46)
  Phase S2: buyer_persona (claude-sonnet46)
  Gate S1: Telegram approval of market + persona
  Phase S3: brand_strategy (claude-sonnet46)
  Phase S4: seo_architecture (claude-sonnet46)
  Phase S5: channel_strategy (claude-sonnet46)
  Gate S2: Telegram approval of full strategy
  → Creates strategy_manifest.json + updates product_manifest.json
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPTS_DIR.parent / "skills"
PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")

AGENT_MODEL = "claude-sonnet46"
GATE_SUMMARY_MODEL = "chatgpt-gpt54"

sys.path.insert(0, str(SCRIPTS_DIR))

from llm_caller import call_llm, extract_json_from_response
from telegram_sender import send_message, send_gate
from artifact_validator import validate_artifact
from gate_handler import create_gate, format_strategy_gate_s1, format_strategy_gate_s2
from rollback_executor import stage_backup, rollback, cleanup_staging


PHASES = [
    {"name": "market_analysis", "skill": "market-analysis", "output": "market_analysis.json"},
    {"name": "buyer_persona", "skill": "buyer-persona", "output": "buyer_persona.json"},
    # Gate S1 here
    {"name": "brand_strategy", "skill": "brand-strategy", "output": "brand_strategy.json"},
    {"name": "seo_architecture", "skill": "seo-architecture", "output": "seo_architecture.json"},
    {"name": "channel_strategy", "skill": "channel-strategy", "output": "channel_strategy.json"},
    # Gate S2 here
]

# Skills that need chunked generation due to large outputs
CHUNKED_SKILLS = {
    "buyer_persona": {
        "chunks": [
            {
                "label": "segments_block_1",
                "instruction": "Generate ONLY the first 4 segments (segments array items 1-4). Output a JSON object with key 'segments' containing an array of 4 segment objects. Include all required fields per segment. Do NOT include comparative_table, priority_ranking, universal_fears, or activation_timeline yet.",
                "merge_key": "segments",
                "merge_mode": "extend",
            },
            {
                "label": "segments_block_2_and_rest",
                "instruction": "Generate the remaining segments (5+), the comparative_table, priority_ranking, universal_fears, and activation_timeline. Output a JSON object with keys: 'segments' (remaining segments), 'comparative_table', 'priority_ranking', 'universal_fears', 'activation_timeline'. All previous segments are already generated — do NOT repeat them.",
                "merge_key": None,
                "merge_mode": "merge_all",
            },
        ],
        "base_fields": {"schema_version": "3.0"},
    },
    "market_analysis": {
        "chunks": [
            {
                "label": "market_size_and_trends",
                "instruction": "Generate ONLY the market_size and trends sections. Output a JSON object with keys: 'market_size' and 'trends'. Do NOT include competitive_landscape, offer_patterns, market_gaps, or audience_intelligence yet.",
                "merge_key": None,
                "merge_mode": "merge_all",
            },
            {
                "label": "competitive_and_gaps",
                "instruction": "Generate ONLY the competitive_landscape, offer_patterns, market_gaps, and audience_intelligence sections. Output a JSON object with these 4 keys. Do NOT include market_size or trends.",
                "merge_key": None,
                "merge_mode": "merge_all",
            },
        ],
        "base_fields": {"schema_version": "3.0"},
    },
    "seo_architecture": {
        "chunks": [
            {
                "label": "keywords_1_to_5",
                "instruction": "Generate ONLY keyword_clusters 1-5 (core_transactional, use_case_date_night, use_case_game_night, use_case_dinner_party, use_case_solo). Output a JSON object with key 'keyword_clusters' containing an array of 5 cluster objects.",
                "merge_key": "keyword_clusters",
                "merge_mode": "extend",
            },
            {
                "label": "keywords_6_to_10_and_rest",
                "instruction": "Generate keyword_clusters 6-10 (use_case_gift, product_format, niche_true_crime_realism, themes, commercial_modifiers) PLUS url_architecture, pillar_cluster_strategy, content_calendar, and seo_warning. Output a JSON with keys: 'keyword_clusters' (clusters 6-10 only), 'url_architecture', 'pillar_cluster_strategy', 'content_calendar', 'seo_warning'.",
                "merge_key": None,
                "merge_mode": "merge_all",
            },
        ],
        "base_fields": {"schema_version": "3.0"},
    },
}


def run_strategy(product_id: str) -> bool:
    """Run the full strategy workflow. Returns True on success."""
    product_dir = PRODUCTS_DIR / product_id
    brief_path = product_dir / "product_brief.json"
    brief = json.loads(brief_path.read_text())

    # Determine version
    strategies_dir = product_dir / "strategies"
    existing = sorted([d.name for d in strategies_dir.iterdir() if d.is_dir()]) if strategies_dir.exists() else []
    next_version = f"v{len(existing) + 1}"
    version_dir = strategies_dir / next_version
    version_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"STRATEGY WORKFLOW — {product_id} ({next_version})")
    print(f"{'='*50}")

    brief_hash = hashlib.sha256(json.dumps(brief, sort_keys=True).encode()).hexdigest()[:12]
    artifacts = {}
    total_cost = 0.0

    # Run phases S1-S2 (market + persona)
    for phase in PHASES[:2]:
        print(f"\n--- Phase: {phase['name']} ---")
        result, cost = _run_agent_phase(phase, product_id, brief, version_dir, artifacts)
        if result is None:
            send_message(f"❌ Strategy failed at {phase['name']} for {product_id}")
            return False
        artifacts[phase["name"]] = result
        total_cost += cost

    # Gate S1
    print("\n--- Gate S1: Market + Persona Review ---")
    gate_msg = format_strategy_gate_s1(product_id, artifacts["market_analysis"], artifacts["buyer_persona"])
    send_message(gate_msg)
    gate = create_gate(product_id, "S1", "strategy", gate_msg,
                       [str(version_dir / "market_analysis.json"), str(version_dir / "buyer_persona.json")])
    print(f"Gate S1 created. Waiting for approval via Telegram.")
    print(f"  /strategy approve {product_id}")

    # In v1, we continue without waiting (async gate — user approves later)
    # The gate is recorded; runtime_orchestrator checks it before marketing runs

    # Run phases S3-S5 (brand + seo + channels)
    for phase in PHASES[2:]:
        print(f"\n--- Phase: {phase['name']} ---")
        result, cost = _run_agent_phase(phase, product_id, brief, version_dir, artifacts)
        if result is None:
            send_message(f"❌ Strategy failed at {phase['name']} for {product_id}")
            return False
        artifacts[phase["name"]] = result
        total_cost += cost

    # Gate S2
    print("\n--- Gate S2: Full Strategy Review ---")
    gate_msg = format_strategy_gate_s2(product_id, artifacts["brand_strategy"],
                                        artifacts["seo_architecture"], artifacts["channel_strategy"])
    send_message(gate_msg)
    gate = create_gate(product_id, "S2", "strategy", gate_msg,
                       [str(version_dir / f) for f in ["brand_strategy.json", "seo_architecture.json", "channel_strategy.json"]])

    # Create strategy_manifest.json
    manifest = {
        "product_id": product_id,
        "strategy_version": next_version,
        "source_brief_hash": brief_hash,
        "created_at": datetime.now().isoformat(),
        "created_by_workflow": "strategy-workflow",
        "status": "awaiting_approval",
        "validity": "valid",
        "approved_by": None,
        "approved_at": None,
        "outputs": {
            "market_analysis": "market_analysis.json",
            "buyer_persona": "buyer_persona.json",
            "brand_strategy": "brand_strategy.json",
            "seo_architecture": "seo_architecture.json",
            "channel_strategy": "channel_strategy.json",
        },
        "invalidation_rules": {
            "price_change_pct": 20,
            "target_audience_changed": True,
            "positioning_changed": True,
            "country_or_language_changed": True,
            "sales_drop_pct": 30,
            "max_age_days": 90,
        },
        "cost_usd": round(total_cost, 4),
    }
    (version_dir / "strategy_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    # Update product_manifest.json
    product_manifest = {
        "product_id": product_id,
        "product_name": brief.get("product_name", product_id),
        "active_strategy_version": next_version,
        "latest_strategy_version": next_version,
        "strategy_status": "awaiting_approval",
        "strategy_validity": "valid",
        "approved_at": None,
        "current_weekly_run": None,
        "files": {
            "product_brief": "product_brief.json",
            "market_analysis": f"strategies/{next_version}/market_analysis.json",
            "buyer_persona": f"strategies/{next_version}/buyer_persona.json",
            "brand_strategy": f"strategies/{next_version}/brand_strategy.json",
            "seo_architecture": f"strategies/{next_version}/seo_architecture.json",
            "channel_strategy": f"strategies/{next_version}/channel_strategy.json",
            "strategy_manifest": f"strategies/{next_version}/strategy_manifest.json",
        },
        "last_updated_at": datetime.now().isoformat(),
    }
    (product_dir / "product_manifest.json").write_text(json.dumps(product_manifest, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Strategy {next_version} COMPLETE")
    print(f"Cost: ${total_cost:.4f}")
    print(f"Status: awaiting_approval")
    print(f"Approve: /strategy approve {product_id}")
    print(f"{'='*50}")

    send_message(
        f"✅ Strategy {next_version} generada para {product_id}\n"
        f"5 archivos estratégicos creados\n"
        f"Costo: ${total_cost:.4f}\n\n"
        f"Revisa y aprueba:\n"
        f"/strategy approve {product_id}"
    )

    return True


def _build_system_prompt(skill_md: str, context: str, product_id: str, language: str) -> str:
    """Build the system prompt for an agent phase."""
    return f"""{skill_md}

PRODUCT CONTEXT:
{context}

OUTPUT RULES:
- Output ONLY valid JSON wrapped in ```json fences
- product_id must be "{product_id}"
- generated_at must be current ISO datetime
- All text content in {language}
"""


def _build_context(brief: dict, prior_artifacts: dict) -> str:
    """Build context string from brief + prior artifacts."""
    context_parts = [f"## product_brief.json\n```json\n{json.dumps(brief, indent=2, ensure_ascii=False)}\n```"]
    for name, data in prior_artifacts.items():
        context_parts.append(f"## {name}.json\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```")
    return "\n\n".join(context_parts)


def _run_chunked_generation(phase_name: str, skill_md: str, context: str,
                            product_id: str, language: str, version_dir: Path) -> tuple:
    """Run chunked generation for skills with large outputs. Returns (parsed_json, cost)."""
    chunk_config = CHUNKED_SKILLS[phase_name]
    chunks = chunk_config["chunks"]
    base = dict(chunk_config["base_fields"])
    base["product_id"] = product_id
    base["generated_at"] = datetime.now().isoformat()

    consolidated = dict(base)
    total_cost = 0.0

    for i, chunk in enumerate(chunks):
        print(f"    Chunk {i+1}/{len(chunks)}: {chunk['label']}")
        chunk_system = f"""{skill_md}

PRODUCT CONTEXT:
{context}

CHUNKED GENERATION MODE:
You are generating ONLY a portion of the full output.
{chunk['instruction']}

OUTPUT RULES:
- Output ONLY valid JSON wrapped in ```json fences
- All text content in {language}
"""
        chunk_user = f"Generate the {chunk['label']} chunk for product {product_id}. Output ONLY the JSON for this chunk."

        try:
            text, usage = call_llm(AGENT_MODEL, chunk_system, chunk_user, max_tokens=16384, temperature=0.4)
            parsed = extract_json_from_response(text)

            if not parsed:
                print(f"    ERROR: No valid JSON in chunk {chunk['label']}")
                debug_path = version_dir / f"debug_{phase_name}_chunk_{i}.txt"
                debug_path.write_text(text)
                return None, 0

            # Merge chunk into consolidated result
            if chunk["merge_mode"] == "extend":
                key = chunk["merge_key"]
                if key not in consolidated:
                    consolidated[key] = []
                chunk_data = parsed.get(key, [])
                if isinstance(chunk_data, list):
                    consolidated[key].extend(chunk_data)
                else:
                    consolidated[key] = chunk_data
            elif chunk["merge_mode"] == "merge_all":
                for key, value in parsed.items():
                    if key in consolidated and isinstance(consolidated[key], list) and isinstance(value, list):
                        consolidated[key].extend(value)
                    else:
                        consolidated[key] = value

            print(f"    ✅ Chunk {chunk['label']} merged ({len(json.dumps(parsed))} chars)")
            print(f"    Tokens: {usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out")

        except Exception as e:
            print(f"    ERROR in chunk {chunk['label']}: {e}")
            return None, 0

    return consolidated, total_cost


def _run_agent_phase(phase: dict, product_id: str, brief: dict,
                     version_dir: Path, prior_artifacts: dict) -> tuple:
    """Run one agent phase. Returns (parsed_json, cost) or (None, 0) on failure."""
    skill_path = SKILLS_DIR / phase["skill"] / "SKILL.md"
    skill_md = skill_path.read_text()
    output_file = phase["output"]
    phase_name = phase["name"]

    context = _build_context(brief, prior_artifacts)
    language = brief.get('language', 'es')
    system_prompt = _build_system_prompt(skill_md, context, product_id, language)

    # Proactively use chunked generation for known large-output skills
    use_chunked = phase_name in CHUNKED_SKILLS

    if use_chunked:
        print(f"  Using chunked generation (output expected to be large)")
        parsed, cost = _run_chunked_generation(phase_name, skill_md, context,
                                                product_id, language, version_dir)
        if parsed is None:
            send_message(f"❌ Chunked generation failed for {phase_name}")
            return None, 0
    else:
        user_prompt = f"Generate {output_file} for product {product_id}. Output ONLY the JSON."

        try:
            text, usage = call_llm(AGENT_MODEL, system_prompt, user_prompt, max_tokens=16384, temperature=0.4)
            cost = 0

            parsed = extract_json_from_response(text)
            if not parsed:
                # Fallback: if this skill has chunked config, try chunked
                if phase_name in CHUNKED_SKILLS:
                    print(f"  JSON parse failed, retrying with chunked generation...")
                    parsed, cost = _run_chunked_generation(phase_name, skill_md, context,
                                                            product_id, language, version_dir)
                    if parsed is None:
                        return None, 0
                else:
                    print(f"  ERROR: No valid JSON in response for {phase_name}")
                    debug_path = version_dir / f"debug_{phase_name}.txt"
                    debug_path.write_text(text)
                    return None, 0

        except Exception as e:
            print(f"  ERROR in {phase_name}: {e}")
            return None, 0

    # Validate and save
    out_path = version_dir / output_file
    out_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
    validation = validate_artifact(out_path)

    if not validation["valid"]:
        print(f"  WARN: Validation issues: {validation['errors']}")

    print(f"  ✅ {output_file} written ({len(json.dumps(parsed))} chars)")
    return parsed, cost


def approve_strategy(product_id: str) -> bool:
    """Approve the current strategy (called from commands)."""
    product_dir = PRODUCTS_DIR / product_id
    manifest_path = product_dir / "product_manifest.json"

    if not manifest_path.exists():
        print("No product manifest found")
        return False

    manifest = json.loads(manifest_path.read_text())
    version = manifest.get("active_strategy_version")

    if not version:
        print("No active strategy version")
        return False

    # Update strategy_manifest
    strat_manifest_path = product_dir / "strategies" / version / "strategy_manifest.json"
    if strat_manifest_path.exists():
        sm = json.loads(strat_manifest_path.read_text())
        sm["status"] = "approved"
        sm["approved_by"] = "Alfredo"
        sm["approved_at"] = datetime.now().isoformat()
        strat_manifest_path.write_text(json.dumps(sm, indent=2, ensure_ascii=False))

    # Update product_manifest
    manifest["strategy_status"] = "approved"
    manifest["strategy_validity"] = "valid"
    manifest["approved_at"] = datetime.now().isoformat()
    manifest["last_updated_at"] = datetime.now().isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    # Resolve gates
    from gate_handler import resolve_gate
    for gate_name in ["S1", "S2"]:
        try:
            resolve_gate(product_id, gate_name, "approved", "Alfredo")
        except ValueError:
            pass  # Already resolved or doesn't exist

    msg = f"✅ Strategy {version} APROBADA para {product_id}\nMarketing puede correr ahora."
    print(msg)
    send_message(msg)
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 strategy_runner.py <product_id> [approve]")
        sys.exit(1)

    product_id = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "approve":
        approve_strategy(product_id)
    else:
        run_strategy(product_id)
