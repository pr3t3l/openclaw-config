#!/usr/bin/env python3
"""
spawn_implementation_blocks.py — Block-based implementation plan generation.

Splits the implementation_planner work into smaller blocks (each with its own
LLM call at reduced max_tokens), then merges into 06_implementation_plan.json.
Avoids API disconnects on large outputs.

Block definitions are loaded from planner_config.json -> block_mode.implementation_planner.

Usage:
  python3 spawn_implementation_blocks.py <slug>
  python3 spawn_implementation_blocks.py <slug> --dry-run
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/home/robotin/.openclaw/workspace-meta-planner")
SHARED = Path("/home/robotin/.openclaw/shared")

AGENT_NAME = "implementation_planner"
ARTIFACT_NAME = "06_implementation_plan"
UPSTREAM_ARTIFACTS = ["05_architecture_decision", "04_contracts"]

ARTIFACT_ORDER = [
    "00_intake_summary", "01_gap_analysis", "02_scope_decision",
    "03_data_flow_map", "04_contracts", "05_architecture_decision",
    "06_implementation_plan", "07_cost_estimate", "08_plan_review",
]

PRICING = {
    "claude-sonnet46": {"input": 3.0, "output": 15.0},
    "claude-opus46": {"input": 5.0, "output": 25.0},
    "chatgpt-gpt54": {"input": 0.0, "output": 0.0},
    "gemini31pro-none": {"input": 1.25, "output": 10.0},
    "gemini31lite-none": {"input": 0.0, "output": 0.0},
    "minimax-m27": {"input": 0.30, "output": 1.20},
    "kimi-k25": {"input": 0.60, "output": 3.00},
    "step35-flash": {"input": 0.10, "output": 0.30},
}


def calculate_cost(model, input_tokens, output_tokens):
    p = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * p["input"] / 1_000_000) + (output_tokens * p["output"] / 1_000_000)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    return Path(path).read_text(encoding="utf-8")


def compress_contracts(contracts_json):
    """Compress 04_contracts.json — keep only build-relevant info."""
    lines = []
    lines.append(f"Project: {contracts_json.get('project_name', 'unknown')}")
    lines.append(f"Artifacts to implement: {len(contracts_json.get('contracts', []))}")
    lines.append("")
    for contract in contracts_json.get("contracts", []):
        name = contract["artifact_name"]
        schema = contract.get("schema_definition", {})
        fields = []
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        for field_name, field_def in props.items():
            ftype = field_def.get("type", "unknown")
            if isinstance(ftype, list):
                ftype = "/".join(ftype)
            req_mark = " (required)" if field_name in required else ""
            desc = field_def.get("description", "")
            if desc:
                fields.append(f"  - {field_name}: {ftype}{req_mark} — {desc}")
            else:
                fields.append(f"  - {field_name}: {ftype}{req_mark}")
        biz_rules = []
        for rule in contract.get("validation_rules", []):
            rule_lower = rule.lower()
            if any(skip in rule_lower for skip in [
                "pattern", "semver", "regex", "octal", "uuid",
                "must follow", "must match pattern", "must be a valid"
            ]):
                continue
            biz_rules.append(f"  - {rule}")
        lines.append(f"### {name}")
        lines.append(f"Format: {contract.get('format', 'json')}")
        lines.append(f"Est. size: {contract.get('estimated_size_tokens', '?')} tokens")
        lines.append("Fields:")
        lines.extend(fields)
        if biz_rules:
            lines.append("Key rules:")
            lines.extend(biz_rules)
        lines.append("")
    return "\n".join(lines)


def build_upstream_context(run_dir):
    """Build upstream context with contract compression."""
    parts = []
    for artifact_name in UPSTREAM_ARTIFACTS:
        artifact_path = run_dir / f"{artifact_name}.json"
        if artifact_path.exists():
            if artifact_name == "04_contracts":
                contracts_data = load_json(artifact_path)
                compressed = compress_contracts(contracts_data)
                parts.append(f"=== {artifact_name}.json (compressed for build planning) ===\n{compressed}\n=== END {artifact_name}.json ===")
                print(f"  Context: {artifact_name} compressed ({len(compressed)} chars vs {artifact_path.stat().st_size} raw)")
            else:
                data = load_text(artifact_path)
                parts.append(f"=== {artifact_name}.json ===\n{data}\n=== END {artifact_name}.json ===")
        else:
            print(f"  WARNING: Upstream artifact {artifact_name}.json not found at {artifact_path}")

    for gate_num in [1, 2, 3]:
        adj_path = run_dir / f"gate_{gate_num}_adjustments.json"
        if adj_path.exists():
            adj = load_json(adj_path)
            parts.append(
                f"=== HUMAN ADJUSTMENTS FROM GATE #{gate_num} (incorporate these) ===\n"
                f"{adj['adjustments']}\n=== END ADJUSTMENTS ==="
            )

    return "\n\n".join(parts) if parts else "No upstream context available."


def call_litellm(model, system_prompt, user_prompt, config, models, max_tokens):
    """Call LiteLLM proxy via curl (TL-01: never use Python requests in WSL)."""
    proxy_url = models["litellm_proxy"]
    api_key = models.get("litellm_api_key", "")

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
        tmp_path = f.name

    curl_timeout = config["defaults"]["curl_max_time"]
    subprocess_timeout = curl_timeout + config["defaults"]["subprocess_buffer"]

    try:
        cmd = [
            "curl", "-s", "-S", "--max-time", str(curl_timeout),
            "-H", "Content-Type: application/json",
        ]
        if api_key:
            cmd.extend(["-H", f"Authorization: Bearer {api_key}"])
        cmd.extend(["--data-binary", f"@{tmp_path}", f"{proxy_url}/v1/chat/completions"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=subprocess_timeout)

        if result.returncode != 0:
            raise Exception(f"curl failed (rc={result.returncode}): {result.stderr[:300]}")
        if not result.stdout.strip():
            raise Exception(f"Empty response from LiteLLM. stderr: {result.stderr[:300]}")

        response = json.loads(result.stdout)
        if "error" in response:
            raise Exception(f"LiteLLM error: {response['error']}")

        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        return content, {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
    finally:
        os.unlink(tmp_path)


def extract_json_from_response(content):
    """Extract JSON from model response."""
    stripped = content.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    match = re.search(r"```json?\s*\n(.*?)```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    depth = 0
    start = None
    for i, ch in enumerate(stripped):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(stripped[start : i + 1])
                except json.JSONDecodeError:
                    start = None
    return None


def validate_artifact(slug):
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "validate_schema.py"), slug, ARTIFACT_NAME],
        capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0, result.stdout + result.stderr


def update_manifest(run_dir, content_str, usage_totals, model_name, total_retries):
    manifest_path = run_dir / "manifest.json"
    manifest = load_json(manifest_path)

    file_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    input_tokens = usage_totals["prompt_tokens"]
    output_tokens = usage_totals["completion_tokens"]
    real_cost = calculate_cost(model_name, input_tokens, output_tokens)

    manifest["artifacts"][ARTIFACT_NAME] = {
        "status": "fresh",
        "hash": file_hash,
        "model": f"{model_name}|by-blocks|{total_retries}",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(real_cost, 6),
        "timestamp": now,
    }
    manifest.pop("token_usage", None)

    idx = ARTIFACT_ORDER.index(ARTIFACT_NAME)
    for downstream in ARTIFACT_ORDER[idx + 1:]:
        if manifest["artifacts"].get(downstream, {}).get("status") == "fresh":
            manifest["artifacts"][downstream]["status"] = "stale"

    manifest["total_cost_usd"] = round(
        sum((v.get("cost_usd") or 0) for v in manifest["artifacts"].values()), 6
    )
    manifest["last_modified"] = now

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def generate_block(block_name, block_task, base_context, system_prompt, model,
                   config, models, max_tokens, max_retries, fallback_model, blocks_dir):
    """Generate a single block with retry and fallback. Returns (parsed, usage, retries_used, used_model)."""
    user_prompt = (
        base_context
        + "\n\n=== EXECUTION OVERRIDE ===\n"
        "Generate implementation plan by block. Output ONLY valid JSON. "
        "This block must contain phases[] plus optional deferred_to_v2[] only if relevant.\n"
        "=== END EXECUTION OVERRIDE ===\n\n"
        f"=== BLOCK TASK ===\n{block_task}\n=== END BLOCK TASK ==="
    )

    retries_used = 0

    for phase_label, phase_model, attempts in [
        ("primary", model, max_retries),
        ("fallback", fallback_model, max_retries if fallback_model else 0),
    ]:
        if attempts == 0:
            continue
        for attempt in range(1, attempts + 1):
            retries_used += 1
            try:
                print(f"    {phase_label} attempt {attempt}/{attempts} ({phase_model})...")
                content, usage = call_litellm(phase_model, system_prompt, user_prompt,
                                              config, models, max_tokens)

                raw_path = blocks_dir / f"{block_name}.raw.txt"
                raw_path.write_text(content, encoding="utf-8")

                parsed = extract_json_from_response(content)
                if parsed is None:
                    repair_script = WORKSPACE / "scripts" / "json_repair.py"
                    if repair_script.exists():
                        repaired_path = blocks_dir / f"{block_name}.repaired.json"
                        repair = subprocess.run(
                            [sys.executable, str(repair_script), str(raw_path), str(repaired_path)],
                            capture_output=True, text=True, timeout=30
                        )
                        if repair.returncode == 0 and repaired_path.exists():
                            parsed = json.loads(repaired_path.read_text(encoding="utf-8"))

                if parsed is None:
                    raise Exception("No valid JSON in response (extraction + repair failed)")

                block_path = blocks_dir / f"{block_name}.json"
                block_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
                return parsed, usage, retries_used, phase_model

            except Exception as e:
                print(f"    RETRY {block_name} {phase_label} {attempt}/{attempts} failed: {e}")

    raise RuntimeError(f"Block {block_name} failed after all retries (primary + fallback)")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <slug> [--dry-run]")
        sys.exit(1)

    slug = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    run_dir = WORKSPACE / "runs" / slug
    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}")
        print(f"  Initialize with: bash scripts/start_plan.sh {slug} \"<idea>\"")
        sys.exit(1)

    config = load_json(WORKSPACE / "planner_config.json")
    models = load_json(WORKSPACE / "models.json")

    if AGENT_NAME not in models.get("agents", {}):
        print(f"ERROR: No model configured for '{AGENT_NAME}' in models.json")
        sys.exit(1)
    model = models["agents"][AGENT_NAME]["model"]

    block_cfg = config.get("block_mode", {}).get("implementation_planner", {})
    if not block_cfg:
        print("ERROR: block_mode.implementation_planner not found in planner_config.json")
        sys.exit(1)

    blocks = block_cfg.get("blocks", [])
    if not blocks:
        print("ERROR: No blocks defined in block_mode.implementation_planner.blocks")
        sys.exit(1)

    max_tokens = block_cfg.get("max_tokens_per_block", 5000)
    max_retries = block_cfg.get("max_retries_per_block", 3)
    fallback_model = block_cfg.get("fallback_model")

    skill_path = WORKSPACE / "skills" / "implementation-planner" / "SKILL.md"
    if not skill_path.exists():
        print(f"ERROR: SKILL.md not found: {skill_path}")
        sys.exit(1)
    system_prompt = load_text(skill_path)

    base_context = build_upstream_context(run_dir)

    print(f"Spawning: {AGENT_NAME} (block mode)")
    print(f"  Slug: {slug}")
    print(f"  Model: {model}")
    print(f"  Fallback: {fallback_model or 'none'}")
    print(f"  Blocks: {len(blocks)}")
    print(f"  max_tokens/block: {max_tokens}")
    print(f"  max_retries/block: {max_retries}")
    print(f"  Context size: ~{len(base_context)} chars")
    print()

    for i, block in enumerate(blocks, 1):
        print(f"  Block {i}/{len(blocks)}: {block['name']}")
        print(f"    Task: {block['task'][:80]}...")

    if dry_run:
        print("\n  --dry-run: Config loaded successfully. No LLM calls made.")
        sys.exit(0)

    blocks_dir = run_dir / "implementation_blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0}
    total_retries = 0
    effective_model = model

    for i, block in enumerate(blocks, 1):
        block_name = block["name"]
        block_task = block["task"]
        print(f"\n  [{i}/{len(blocks)}] Generating block: {block_name}")

        parsed, usage, retries_used, used_model = generate_block(
            block_name, block_task, base_context, system_prompt,
            model, config, models, max_tokens, max_retries, fallback_model, blocks_dir
        )

        results[block_name] = parsed
        usage_totals["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_totals["completion_tokens"] += usage.get("completion_tokens", 0)
        total_retries += retries_used
        effective_model = used_model

        phases_count = len(parsed.get("phases", []))
        print(f"    OK: {phases_count} phases, "
              f"{usage.get('prompt_tokens', 0)}+{usage.get('completion_tokens', 0)} tokens")

    # Merge blocks
    print(f"\n  Merging {len(results)} blocks...")
    all_phases = []
    all_deferred = []
    for block in blocks:
        block_data = results[block["name"]]
        all_phases.extend(block_data.get("phases", []))
        all_deferred.extend(block_data.get("deferred_to_v2", []))

    all_phases = sorted(all_phases, key=lambda x: x.get("phase_number", 999))

    final = {
        "project_name": results[blocks[0]["name"]].get("project_name", f"Implementation Plan ({slug})"),
        "phases": all_phases,
        "deferred_to_v2": all_deferred,
        "total_estimated_hours": sum(float(p.get("estimated_effort_hours", 0)) for p in all_phases),
    }

    content_str = json.dumps(final, indent=2, ensure_ascii=False)
    artifact_path = run_dir / f"{ARTIFACT_NAME}.json"
    artifact_path.write_text(content_str, encoding="utf-8")
    print(f"  Wrote: {artifact_path}")
    print(f"  Total phases: {len(all_phases)}, deferred items: {len(all_deferred)}")

    # Validate
    print(f"\n  Validating against schema...")
    valid, output = validate_artifact(slug)
    print(f"  {output.strip()}")

    if not valid:
        print(f"\nERROR: Schema validation failed. Artifact written but manifest NOT updated.")
        sys.exit(1)

    real_cost = calculate_cost(effective_model, usage_totals["prompt_tokens"], usage_totals["completion_tokens"])
    update_manifest(run_dir, content_str, usage_totals, effective_model, total_retries)

    print(f"\n  Manifest updated: {ARTIFACT_NAME} -> fresh "
          f"(model: {effective_model}|by-blocks|{total_retries}, cost: ${real_cost:.6f})")
    print(f"  Tokens total: {usage_totals['prompt_tokens']} prompt / "
          f"{usage_totals['completion_tokens']} completion")
    print(f"\nDone: {AGENT_NAME} -> {ARTIFACT_NAME}.json (block mode, {len(blocks)} blocks)")


if __name__ == "__main__":
    main()
