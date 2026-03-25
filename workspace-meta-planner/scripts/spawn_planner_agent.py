#!/usr/bin/env python3
"""
spawn_planner_agent.py — Execute a planner agent via LiteLLM proxy.

Reads the agent's SKILL.md, loads upstream artifacts as context,
calls the model via LiteLLM (curl, not Python requests — TL-01),
extracts JSON output, validates against schema, updates manifest.

Usage:
  python3 spawn_planner_agent.py <slug> <agent_name>

Examples:
  python3 spawn_planner_agent.py personal-finance intake_analyst
  python3 spawn_planner_agent.py personal-finance gap_finder
  python3 spawn_planner_agent.py personal-finance scope_framer
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

# Agent name (underscore) → skill directory name (hyphen)
AGENT_TO_SKILL = {
    "intake_analyst": "intake-analyst",
    "gap_finder": "gap-finder",
    "scope_framer": "scope-framer",
    "data_flow_mapper": "data-flow-mapper",
    "contract_designer": "contract-designer",
    "architecture_planner": "architecture-planner",
    "implementation_planner": "implementation-planner",
    "lessons_validator": "lessons-validator",
    "landscape_researcher": "landscape-researcher",
    "capability_mapper": "capability-mapper",
    "compliance_reviewer": "compliance-reviewer",
    "creative_strategist": "creative-strategist",
    "red_team": "red-team",
}

# Agent → artifact it produces
AGENT_TO_ARTIFACT = {
    "intake_analyst": "00_intake_summary",
    "gap_finder": "01_gap_analysis",
    "scope_framer": "02_scope_decision",
    "data_flow_mapper": "03_data_flow_map",
    "contract_designer": "04_contracts",
    "architecture_planner": "05_architecture_decision",
    "implementation_planner": "06_implementation_plan",
    "lessons_validator": "08_plan_review",
}

# Artifact dependency chain
ARTIFACT_ORDER = [
    "00_intake_summary",
    "01_gap_analysis",
    "02_scope_decision",
    "03_data_flow_map",
    "04_contracts",
    "05_architecture_decision",
    "06_implementation_plan",
    "07_cost_estimate",
    "08_plan_review",
]

# What upstream context each agent needs
AGENT_CONTEXT = {
    "intake_analyst": {"from_manifest": ["raw_idea"]},
    "gap_finder": {"artifacts": ["00_intake_summary"], "files": ["lessons_learned"]},
    "scope_framer": {"artifacts": ["00_intake_summary", "01_gap_analysis"]},
    "data_flow_mapper": {"artifacts": ["00_intake_summary", "01_gap_analysis", "02_scope_decision"]},
    "contract_designer": {"artifacts": ["03_data_flow_map"]},
    "architecture_planner": {},  # B3 uses spawn_debate.py, not spawn_planner_agent.py
    "implementation_planner": {"artifacts": ["05_architecture_decision", "04_contracts"]},
    "lessons_validator": {"artifacts": ["00_intake_summary", "01_gap_analysis", "02_scope_decision", "03_data_flow_map", "04_contracts", "05_architecture_decision", "06_implementation_plan", "07_cost_estimate"], "files": ["lessons_learned", "system_configuration"]},
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    return Path(path).read_text(encoding="utf-8")


def load_config():
    config = load_json(WORKSPACE / "planner_config.json")
    models = load_json(WORKSPACE / "models.json")
    return config, models


def get_model_for_agent(agent_name, models):
    """Look up the model for this agent from models.json."""
    if agent_name in models.get("agents", {}):
        return models["agents"][agent_name]["model"]
    if agent_name in models.get("conditional_modules", {}):
        return models["conditional_modules"][agent_name]["model"]
    raise ValueError(f"No model configured for agent '{agent_name}' in models.json")


def build_user_prompt(agent_name, slug, run_dir):
    """Build the user prompt with upstream context."""
    context = AGENT_CONTEXT.get(agent_name, {})
    parts = []

    # From manifest fields
    if "from_manifest" in context:
        manifest = load_json(run_dir / "manifest.json")
        for field in context["from_manifest"]:
            value = manifest.get(field)
            if value is not None:
                parts.append(f"=== {field.upper()} ===\n{value}\n=== END {field.upper()} ===")

    # Upstream artifacts
    if "artifacts" in context:
        for artifact_name in context["artifacts"]:
            artifact_path = run_dir / f"{artifact_name}.json"
            if artifact_path.exists():
                data = load_text(artifact_path)
                parts.append(f"=== {artifact_name}.json ===\n{data}\n=== END {artifact_name}.json ===")
            else:
                print(f"WARNING: Upstream artifact {artifact_name}.json not found at {artifact_path}")

    # Extra files (lessons_learned, system_configuration, etc.)
    if "files" in context:
        for file_key in context["files"]:
            if file_key == "lessons_learned":
                ll_path = Path(SHARED / "lessons_learned.md")
                if ll_path.exists():
                    data = load_text(ll_path)
                    parts.append(f"=== lessons_learned.md ===\n{data}\n=== END lessons_learned.md ===")
            elif file_key == "system_configuration":
                sc_path = WORKSPACE / "system_configuration.md"
                if sc_path.exists():
                    data = load_text(sc_path)
                    parts.append(f"=== system_configuration.md ===\n{data}\n=== END system_configuration.md ===")

    if not parts:
        return "No upstream context available."

    return "\n\n".join(parts)


def call_litellm(model, system_prompt, user_prompt, config, models, max_tokens=None):
    """Call LiteLLM proxy via curl (TL-01: never use Python requests in WSL)."""
    if max_tokens is None:
        max_tokens = config["defaults"]["max_tokens_standard"]

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

    payload_json = json.dumps(payload, ensure_ascii=True)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(payload_json.encode("utf-8"))
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

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=subprocess_timeout
        )

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
    """Extract JSON from the model's response.

    Tries in order:
    1. Direct JSON parse (response is pure JSON)
    2. Extract from ```json ... ``` fenced block
    3. Find first { ... } top-level object
    """
    # 1. Try direct parse
    stripped = content.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # 2. Try fenced block
    match = re.search(r"```json?\s*\n(.*?)```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Try finding first top-level { ... }
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


def validate_artifact(slug, artifact_name):
    """Run validate_schema.py and return (success, output)."""
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "validate_schema.py"), slug, artifact_name],
        capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0, result.stdout + result.stderr


def update_manifest(run_dir, artifact_name, content_str, usage, est_cost):
    """Update manifest.json with artifact status, hash, cost, timestamp. Invalidate downstream."""
    manifest_path = run_dir / "manifest.json"
    manifest = load_json(manifest_path)

    file_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest["artifacts"][artifact_name] = {
        "status": "fresh",
        "hash": file_hash,
        "cost_usd": round(est_cost, 4),
        "timestamp": now,
    }

    # Store token usage
    if "token_usage" not in manifest:
        manifest["token_usage"] = {}
    manifest["token_usage"][artifact_name] = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }

    # Invalidate downstream artifacts
    idx = ARTIFACT_ORDER.index(artifact_name)
    for downstream in ARTIFACT_ORDER[idx + 1:]:
        if manifest["artifacts"][downstream]["status"] == "fresh":
            manifest["artifacts"][downstream]["status"] = "stale"

    # Update totals
    manifest["total_cost_usd"] = round(
        sum((v.get("cost_usd") or 0) for v in manifest["artifacts"].values()), 4
    )
    manifest["last_modified"] = now

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <slug> <agent_name>")
        print(f"Example: {sys.argv[0]} personal-finance intake_analyst")
        sys.exit(1)

    slug = sys.argv[1]
    agent_name = sys.argv[2]

    # Validate agent
    if agent_name not in AGENT_TO_SKILL:
        print(f"ERROR: Unknown agent '{agent_name}'")
        print(f"  Available: {', '.join(sorted(AGENT_TO_SKILL.keys()))}")
        sys.exit(1)

    artifact_name = AGENT_TO_ARTIFACT.get(agent_name)
    if not artifact_name:
        print(f"ERROR: No artifact mapping for agent '{agent_name}'")
        sys.exit(1)

    # Validate run directory
    run_dir = WORKSPACE / "runs" / slug
    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}")
        print(f"  Initialize with: bash scripts/start_plan.sh {slug} \"<idea>\"")
        sys.exit(1)

    # Load config
    config, models = load_config()
    model = get_model_for_agent(agent_name, models)

    # Load SKILL.md
    skill_dir_name = AGENT_TO_SKILL[agent_name]
    skill_path = WORKSPACE / "skills" / skill_dir_name / "SKILL.md"
    if not skill_path.exists():
        print(f"ERROR: SKILL.md not found: {skill_path}")
        sys.exit(1)
    system_prompt = load_text(skill_path)

    # Build user prompt
    user_prompt = build_user_prompt(agent_name, slug, run_dir)

    print(f"Spawning: {agent_name}")
    print(f"  Slug: {slug}")
    print(f"  Model: {model}")
    print(f"  Artifact: {artifact_name}")

    # Call LiteLLM
    max_tokens = config["defaults"]["max_tokens_standard"]
    retries = 0
    max_retries = 1

    while True:
        print(f"\n  Calling LiteLLM ({model}, max_tokens={max_tokens})...")
        try:
            content, usage = call_litellm(model, system_prompt, user_prompt, config, models, max_tokens)
        except Exception as e:
            print(f"ERROR: API call failed: {e}")
            sys.exit(1)

        print(f"  Response: {usage.get('prompt_tokens', '?')} prompt / {usage.get('completion_tokens', '?')} completion tokens")

        # Extract JSON
        parsed = extract_json_from_response(content)
        if parsed is None:
            if retries < max_retries:
                retries += 1
                max_tokens = int(max_tokens * 1.5)
                print(f"  WARNING: No valid JSON in response. Retrying with max_tokens={max_tokens}...")
                continue
            else:
                # Save debug response
                debug_path = run_dir / f"debug_{agent_name}_response.txt"
                debug_path.write_text(content, encoding="utf-8")
                print(f"ERROR: Could not extract valid JSON from response after {max_retries} retries.")
                print(f"  Raw response saved to: {debug_path}")
                sys.exit(1)
        break

    # Write artifact
    content_str = json.dumps(parsed, indent=2, ensure_ascii=False)
    artifact_path = run_dir / f"{artifact_name}.json"
    artifact_path.write_text(content_str, encoding="utf-8")
    print(f"  Wrote: {artifact_path}")

    # Validate against schema
    print(f"\n  Validating against schema...")
    valid, output = validate_artifact(slug, artifact_name)
    print(f"  {output.strip()}")

    if not valid:
        print(f"\nERROR: Schema validation failed. Artifact written but manifest NOT updated.")
        sys.exit(1)

    # Get estimated cost from models.json
    agent_config = models.get("agents", {}).get(agent_name, {})
    est_cost = agent_config.get("est_cost", 0)

    # Update manifest
    update_manifest(run_dir, artifact_name, content_str, usage, est_cost)
    print(f"\n  Manifest updated: {artifact_name} → fresh (cost: ${est_cost:.4f})")
    print(f"\nDone: {agent_name} → {artifact_name}.json")


if __name__ == "__main__":
    main()
