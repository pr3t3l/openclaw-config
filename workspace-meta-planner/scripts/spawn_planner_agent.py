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

# Pricing per million tokens
PRICING = {
    "claude-sonnet46": {"input": 3.0, "output": 15.0},
    "claude-opus46": {"input": 5.0, "output": 25.0},
    "chatgpt-gpt54": {"input": 0.0, "output": 0.0},  # OAuth subscription
    "gemini31pro-none": {"input": 1.25, "output": 10.0},
    "gemini31lite-none": {"input": 0.0, "output": 0.0},
    "minimax-m27": {"input": 0.30, "output": 1.20},
    "kimi-k25": {"input": 0.60, "output": 3.00},
    "step35-flash": {"input": 0.10, "output": 0.30},
}


def calculate_cost(model, input_tokens, output_tokens):
    """Calculate real cost from tokens and model pricing."""
    p = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * p["input"] / 1_000_000) + (output_tokens * p["output"] / 1_000_000)


def compress_contracts(contracts_json: dict) -> str:
    """Compress 04_contracts.json for implementation_planner context.

    The implementation planner needs to know WHAT artifacts to build and their
    purpose/key fields, NOT the full JSON Schema definitions, examples, or
    format-level validation rules.

    Reduces ~5,470 tokens to ~1,200 tokens without losing build-relevant info.
    """
    lines = []
    lines.append(f"Project: {contracts_json.get('project_name', 'unknown')}")
    lines.append(f"Artifacts to implement: {len(contracts_json.get('contracts', []))}")
    lines.append("")

    for contract in contracts_json.get("contracts", []):
        name = contract["artifact_name"]
        schema = contract.get("schema_definition", {})

        # Extract top-level required fields and their types (no nested schema)
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

        # Extract only business-logic validation rules (skip format/regex rules)
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


def compress_architecture(arch_json: dict) -> dict:
    """Strip verbose fields from architecture that don't affect build planning."""
    compressed = json.loads(json.dumps(arch_json))  # deep copy
    compressed.pop("red_team_findings", None)
    if "infrastructure_validation" in compressed:
        compressed["infrastructure_validation"].pop("notes", None)
    return compressed


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
                # Compress contracts for implementation_planner (saves ~4k tokens)
                if agent_name == "implementation_planner" and artifact_name == "04_contracts":
                    contracts_data = load_json(artifact_path)
                    compressed = compress_contracts(contracts_data)
                    parts.append(f"=== {artifact_name}.json (compressed for build planning) ===\n{compressed}\n=== END {artifact_name}.json ===")
                    print(f"  Context: {artifact_name} compressed ({len(compressed)} chars vs {artifact_path.stat().st_size} raw)")
                # Compress large architecture for implementation_planner
                elif agent_name == "implementation_planner" and artifact_name == "05_architecture_decision" and artifact_path.stat().st_size > 30000:
                    arch_data = load_json(artifact_path)
                    compressed_arch = compress_architecture(arch_data)
                    data = json.dumps(compressed_arch, indent=2, ensure_ascii=False)
                    parts.append(f"=== {artifact_name}.json (compressed) ===\n{data}\n=== END {artifact_name}.json ===")
                    print(f"  Context: {artifact_name} compressed ({len(data)} chars vs {artifact_path.stat().st_size} raw)")
                else:
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

    # Gate adjustments (injected as additional context)
    for gate_num in [1, 2, 3]:
        adj_path = run_dir / f"gate_{gate_num}_adjustments.json"
        if adj_path.exists():
            adj = load_json(adj_path)
            parts.append(f"=== HUMAN ADJUSTMENTS FROM GATE #{gate_num} (incorporate these) ===\n{adj['adjustments']}\n=== END ADJUSTMENTS ===")

    # Intake Q&A history (for iterative intake)
    if agent_name == "intake_analyst":
        qa_path = run_dir / "intake_qa_history.json"
        if qa_path.exists():
            qa = load_json(qa_path)
            if qa.get("rounds"):
                qa_text = json.dumps(qa["rounds"], indent=2, ensure_ascii=False)
                parts.append(f"=== PREVIOUS Q&A ROUNDS (use these answers, do NOT re-ask) ===\n{qa_text}\n=== END Q&A ===")

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


def update_manifest(run_dir, artifact_name, content_str, usage, model_name):
    """Update manifest.json with artifact status, hash, real cost from tokens. Invalidate downstream."""
    manifest_path = run_dir / "manifest.json"
    manifest = load_json(manifest_path)

    file_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    real_cost = calculate_cost(model_name, input_tokens, output_tokens)

    manifest["artifacts"][artifact_name] = {
        "status": "fresh",
        "hash": file_hash,
        "model": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(real_cost, 6),
        "timestamp": now,
    }

    # Remove legacy token_usage if present
    manifest.pop("token_usage", None)

    # Invalidate downstream artifacts
    idx = ARTIFACT_ORDER.index(artifact_name)
    for downstream in ARTIFACT_ORDER[idx + 1:]:
        if manifest["artifacts"][downstream]["status"] == "fresh":
            manifest["artifacts"][downstream]["status"] = "stale"

    # Update totals
    manifest["total_cost_usd"] = round(
        sum((v.get("cost_usd") or 0) for v in manifest["artifacts"].values()), 6
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

    # --- Intake iterative pre-check (PATCH-1) ---
    if agent_name == "intake_analyst":
        pending_path = run_dir / "intake_pending_questions.json"
        answers_path = run_dir / "intake_answers.json"
        qa_history_path = run_dir / "intake_qa_history.json"

        if pending_path.exists():
            if not answers_path.exists():
                print(f"  ERROR: Pending questions exist but no answers found.")
                print(f"  Answer questions in: {pending_path}")
                print(f"  Save answers to: {answers_path}")
                print(f"  Format: {{\"answers\": [\"answer1\", \"answer2\", ...]}}")
                sys.exit(1)
            else:
                pending = load_json(pending_path)
                answers = load_json(answers_path)
                qa_history = load_json(qa_history_path) if qa_history_path.exists() else {"rounds": []}
                qa_history["rounds"].append({
                    "round": pending.get("round", len(qa_history["rounds"]) + 1),
                    "questions": pending.get("questions", []),
                    "answers": answers.get("answers", []),
                    "answered_at": datetime.now(timezone.utc).isoformat(),
                })
                with open(qa_history_path, "w", encoding="utf-8") as f:
                    json.dump(qa_history, f, indent=2, ensure_ascii=False)
                pending_path.unlink()
                answers_path.unlink()
                print(f"  Merged answers into Q&A history (round {len(qa_history['rounds'])})")

        qa_history = load_json(qa_history_path) if qa_history_path.exists() else {"rounds": []}
        current_round = len(qa_history["rounds"]) + 1
        if current_round > 5:
            print(f"  Max rounds (5) reached. Forcing READY.")
            intake_path = run_dir / "00_intake_summary.json"
            if intake_path.exists():
                intake = load_json(intake_path)
                intake["status"] = "READY"
                intake["critical_missing_data"] = []
                with open(intake_path, "w", encoding="utf-8") as f:
                    json.dump(intake, f, indent=2, ensure_ascii=False)
            sys.exit(0)

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

    # Calculate real cost from tokens
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    real_cost = calculate_cost(model, input_tokens, output_tokens)

    # Update manifest
    update_manifest(run_dir, artifact_name, content_str, usage, model)
    print(f"\n  Manifest updated: {artifact_name} → fresh (model: {model}, cost: ${real_cost:.6f})")

    # --- Intake post-check: save pending questions if NEEDS_CLARIFICATION ---
    if agent_name == "intake_analyst" and parsed.get("status") == "NEEDS_CLARIFICATION":
        questions = parsed.get("critical_missing_data", parsed.get("clarification_questions", []))
        qa_history = load_json(run_dir / "intake_qa_history.json") if (run_dir / "intake_qa_history.json").exists() else {"rounds": []}
        current_round = len(qa_history["rounds"]) + 1
        pending = {
            "round": current_round,
            "questions": questions,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(run_dir / "intake_pending_questions.json", "w", encoding="utf-8") as f:
            json.dump(pending, f, indent=2, ensure_ascii=False)
        print(f"\n  NEEDS_CLARIFICATION (round {current_round})")
        for i, q in enumerate(questions, 1):
            print(f"    {i}. {q}")
        print(f"\n  Save answers to: {run_dir / 'intake_answers.json'}")
        print(f'  Format: {{"answers": ["answer1", "answer2", ...]}}')
        print(f"  Then re-run: python3 {sys.argv[0]} {slug} intake_analyst")

    print(f"\nDone: {agent_name} → {artifact_name}.json")


if __name__ == "__main__":
    main()
