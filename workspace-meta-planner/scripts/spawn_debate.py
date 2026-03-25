#!/usr/bin/env python3
"""
spawn_debate.py — Multi-model debate for Architecture Planner (B3).

Calls N models in parallel (or sequential fallback), collects proposals,
runs a judge to select the best, optionally runs red team.

Usage:
  python3 spawn_debate.py <slug>

Reads debate_level from manifest or intake_summary.
"""

import asyncio
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

ARTIFACT_ORDER = [
    "00_intake_summary", "01_gap_analysis", "02_scope_decision",
    "03_data_flow_map", "04_contracts", "05_architecture_decision",
    "06_implementation_plan", "07_cost_estimate", "08_plan_review",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    return Path(path).read_text(encoding="utf-8")


def call_litellm(model, system_prompt, user_prompt, config, models, max_tokens=None):
    """Call LiteLLM proxy via curl. Same pattern as spawn_planner_agent.py."""
    if max_tokens is None:
        max_tokens = config["defaults"]["max_tokens_debate"]

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
            raise Exception(f"Empty response. stderr: {result.stderr[:300]}")

        response = json.loads(result.stdout)

        if "error" in response:
            raise Exception(f"LiteLLM error: {response['error']}")

        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})

        return {
            "content": content,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "cost": 0,  # Estimated later
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
                    return json.loads(stripped[start:i + 1])
                except json.JSONDecodeError:
                    start = None

    return None


def get_debate_level(run_dir):
    """Get debate level from manifest or intake summary."""
    manifest = load_json(run_dir / "manifest.json")
    level = manifest.get("debate_level")
    if level:
        return level

    intake_path = run_dir / "00_intake_summary.json"
    if intake_path.exists():
        intake = load_json(intake_path)
        level = intake.get("debate_level_recommendation", "simple")
        # Update manifest
        manifest["debate_level"] = level
        with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return level

    return "simple"


def build_upstream_context(run_dir):
    """Load all upstream artifacts (00-04) as context."""
    parts = []
    for artifact in ARTIFACT_ORDER[:5]:  # 00 through 04
        path = run_dir / f"{artifact}.json"
        if path.exists():
            data = load_text(path)
            parts.append(f"=== {artifact}.json ===\n{data}\n=== END {artifact}.json ===")

    # Add system configuration
    sys_config = WORKSPACE / "system_configuration.md"
    if sys_config.exists():
        parts.append(f"=== system_configuration.md ===\n{load_text(sys_config)}\n=== END system_configuration.md ===")

    # Add models.json
    models_path = WORKSPACE / "models.json"
    if models_path.exists():
        parts.append(f"=== models.json ===\n{load_text(models_path)}\n=== END models.json ===")

    return "\n\n".join(parts)


def call_model_sync(model, system_prompt, user_prompt, config, models):
    """Synchronous call to a single model."""
    print(f"    Calling {model}...")
    result = call_litellm(model, system_prompt, user_prompt, config, models)
    tokens = result["prompt_tokens"] + result["completion_tokens"]
    print(f"    {model}: {tokens} tokens")
    return result


async def call_model_async(model, system_prompt, user_prompt, config, models):
    """Async wrapper for parallel execution."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, call_model_sync, model, system_prompt, user_prompt, config, models
    )


def run_models_parallel(debate_models, system_prompt, user_prompt, config, models):
    """Run multiple models in parallel using asyncio."""
    loop = asyncio.new_event_loop()
    try:
        tasks = [
            call_model_async(m, system_prompt, user_prompt, config, models)
            for m in debate_models
        ]
        results = loop.run_until_complete(asyncio.gather(*tasks))
        return list(zip(debate_models, results))
    finally:
        loop.close()


def run_models_sequential(debate_models, system_prompt, user_prompt, config, models):
    """Run multiple models sequentially."""
    results = []
    for m in debate_models:
        result = call_model_sync(m, system_prompt, user_prompt, config, models)
        results.append((m, result))
    return results


def build_judge_prompt(proposals, debate_level):
    """Build the prompt for the judge model."""
    parts = ["You are comparing architecture proposals from different AI models.\n"]
    parts.append("## Evaluation Criteria (weighted):\n")
    parts.append("| Criterion | Weight |")
    parts.append("|-----------|--------|")
    parts.append("| Feasibility with current infrastructure | 25% |")
    parts.append("| Cost efficiency | 25% |")
    parts.append("| Time to MVP | 20% |")
    parts.append("| Coverage of identified gaps | 15% |")
    parts.append("| Simplicity (fewer agents = better, at equal quality) | 15% |")
    parts.append("")

    for i, (model, proposal_json) in enumerate(proposals, 1):
        parts.append(f"## Proposal {i} (from {model}):\n```json\n{proposal_json}\n```\n")

    parts.append("\n## Your Task:")
    parts.append("1. Score each proposal on each criterion (0-100)")
    parts.append("2. Compute weighted total")
    parts.append("3. Select the winner")
    parts.append("4. Produce a MERGED final architecture that takes the best elements from the winning proposal")
    parts.append("5. If proposals have complementary strengths, merge the best of each")
    parts.append("")
    parts.append("Output a JSON with this structure:")
    parts.append('{ "judge_reasoning": "...", "scores": { "model_name": { "feasibility": N, "cost": N, "time_to_mvp": N, "gap_coverage": N, "simplicity": N, "weighted_total": N } }, "winner": "model_name", "final_architecture": { ...the winning/merged architecture matching 05_architecture_decision.schema.json... } }')

    return "\n".join(parts)


def save_proposal(run_dir, model, content):
    """Save individual proposal for debugging."""
    proposals_dir = run_dir / "debate_proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / f"proposal_{model}.json"
    path.write_text(content, encoding="utf-8")


def update_manifest(run_dir, content_str, total_tokens):
    """Update manifest with architecture decision artifact."""
    manifest = load_json(run_dir / "manifest.json")

    file_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest["artifacts"]["05_architecture_decision"] = {
        "status": "fresh",
        "hash": file_hash,
        "cost_usd": round(total_tokens * 0.00001, 4),  # rough estimate
        "timestamp": now,
    }

    # Invalidate downstream
    idx = ARTIFACT_ORDER.index("05_architecture_decision")
    for downstream in ARTIFACT_ORDER[idx + 1:]:
        if manifest["artifacts"][downstream]["status"] == "fresh":
            manifest["artifacts"][downstream]["status"] = "stale"

    manifest["total_cost_usd"] = round(
        sum((v.get("cost_usd") or 0) for v in manifest["artifacts"].values()), 4
    )
    manifest["last_modified"] = now

    with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <slug>")
        sys.exit(1)

    slug = sys.argv[1]
    run_dir = WORKSPACE / "runs" / slug

    if not run_dir.exists():
        print(f"ERROR: Run not found: {run_dir}")
        sys.exit(1)

    config = load_json(WORKSPACE / "planner_config.json")
    models = load_json(WORKSPACE / "models.json")

    # Get debate level
    debate_level = get_debate_level(run_dir)
    debate_models_list = models["debate_models"].get(debate_level, ["claude-sonnet46"])
    judge_model = models["judge"].get(debate_level)

    print(f"Architecture Debate: {slug}")
    print(f"  Debate level: {debate_level}")
    print(f"  Models: {debate_models_list}")
    print(f"  Judge: {judge_model or 'none (single model)'}")

    # Load system prompt (architecture planner SKILL.md)
    skill_path = WORKSPACE / "skills" / "architecture-planner" / "SKILL.md"
    if not skill_path.exists():
        print(f"ERROR: SKILL.md not found: {skill_path}")
        sys.exit(1)
    system_prompt = load_text(skill_path)

    # Build user prompt with all upstream context
    user_prompt = build_upstream_context(run_dir)
    user_prompt += "\n\nProduce your architecture proposal as valid JSON matching 05_architecture_decision.schema.json."

    total_tokens = 0

    # === SINGLE MODEL (simple) ===
    if len(debate_models_list) == 1 or not judge_model:
        model = debate_models_list[0]
        print(f"\n  Single model mode: {model}")
        result = call_model_sync(model, system_prompt, user_prompt, config, models)
        total_tokens += result["prompt_tokens"] + result["completion_tokens"]

        parsed = extract_json_from_response(result["content"])
        if not parsed:
            debug_path = run_dir / "debug_debate_response.txt"
            debug_path.write_text(result["content"], encoding="utf-8")
            print(f"ERROR: No valid JSON from {model}. Saved to {debug_path}")
            sys.exit(1)

        save_proposal(run_dir, model, json.dumps(parsed, indent=2, ensure_ascii=False))

        content_str = json.dumps(parsed, indent=2, ensure_ascii=False)
        artifact_path = run_dir / "05_architecture_decision.json"
        artifact_path.write_text(content_str, encoding="utf-8")
        print(f"\n  Wrote: {artifact_path}")

        # Validate
        val_result = subprocess.run(
            [sys.executable, str(WORKSPACE / "scripts" / "validate_schema.py"), slug, "05_architecture_decision"],
            capture_output=True, text=True, timeout=30
        )
        print(f"  {val_result.stdout.strip()}")
        if val_result.returncode != 0:
            print("ERROR: Schema validation failed.")
            sys.exit(1)

        update_manifest(run_dir, content_str, total_tokens)
        print(f"\n  Done. Total tokens: {total_tokens}")
        return

    # === MULTI-MODEL DEBATE (complex/critical) ===
    print(f"\n  Multi-model debate ({len(debate_models_list)} models)...")

    execution_mode = config["debate"]["execution_mode"]
    proposals = []

    if execution_mode == "parallel":
        try:
            print(f"  Execution: parallel")
            results = run_models_parallel(debate_models_list, system_prompt, user_prompt, config, models)
            for model, result in results:
                total_tokens += result["prompt_tokens"] + result["completion_tokens"]
                parsed = extract_json_from_response(result["content"])
                if parsed:
                    proposal_str = json.dumps(parsed, indent=2, ensure_ascii=False)
                    save_proposal(run_dir, model, proposal_str)
                    proposals.append((model, proposal_str))
                else:
                    print(f"  WARNING: No valid JSON from {model}, skipping")
                    save_proposal(run_dir, model, result["content"])
        except Exception as e:
            print(f"  Parallel failed ({e})")
            if config["debate"]["fallback_to_sequential"]:
                print(f"  Falling back to sequential...")
                proposals = []
                results = run_models_sequential(debate_models_list, system_prompt, user_prompt, config, models)
                for model, result in results:
                    total_tokens += result["prompt_tokens"] + result["completion_tokens"]
                    parsed = extract_json_from_response(result["content"])
                    if parsed:
                        proposal_str = json.dumps(parsed, indent=2, ensure_ascii=False)
                        save_proposal(run_dir, model, proposal_str)
                        proposals.append((model, proposal_str))
                    else:
                        print(f"  WARNING: No valid JSON from {model}, skipping")
                        save_proposal(run_dir, model, result["content"])
            else:
                raise
    else:
        print(f"  Execution: sequential")
        results = run_models_sequential(debate_models_list, system_prompt, user_prompt, config, models)
        for model, result in results:
            total_tokens += result["prompt_tokens"] + result["completion_tokens"]
            parsed = extract_json_from_response(result["content"])
            if parsed:
                proposal_str = json.dumps(parsed, indent=2, ensure_ascii=False)
                save_proposal(run_dir, model, proposal_str)
                proposals.append((model, proposal_str))
            else:
                print(f"  WARNING: No valid JSON from {model}, skipping")
                save_proposal(run_dir, model, result["content"])

    if not proposals:
        print("ERROR: No valid proposals from any model.")
        sys.exit(1)

    if len(proposals) == 1:
        print(f"  Only 1 valid proposal — using it directly (no judge needed)")
        content_str = proposals[0][1]
    else:
        # === JUDGE ===
        print(f"\n  Running judge ({judge_model})...")
        judge_system = (
            "You are a fair judge comparing structured architecture proposals. "
            "Evaluate using the criteria weights provided. "
            "Output valid JSON. Do not wrap in code fences."
        )
        judge_user = build_judge_prompt(proposals, debate_level)
        judge_result = call_litellm(judge_model, judge_system, judge_user, config, models)
        total_tokens += judge_result["prompt_tokens"] + judge_result["completion_tokens"]

        judge_parsed = extract_json_from_response(judge_result["content"])
        if judge_parsed:
            # Save judge evaluation
            proposals_dir = run_dir / "debate_proposals"
            proposals_dir.mkdir(parents=True, exist_ok=True)
            judge_path = proposals_dir / "judge_evaluation.json"
            judge_path.write_text(
                json.dumps(judge_parsed, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  Judge evaluation saved: {judge_path}")

            # Extract final architecture
            final_arch = judge_parsed.get("final_architecture")
            if final_arch:
                # Add judge metadata
                final_arch["judge_reasoning"] = judge_parsed.get("judge_reasoning")
                final_arch["debate_proposals"] = [
                    {"model": m, "summary": "see debate_proposals/"} for m, _ in proposals
                ]
                content_str = json.dumps(final_arch, indent=2, ensure_ascii=False)
            else:
                # Judge didn't produce final_architecture — use full judge output
                content_str = json.dumps(judge_parsed, indent=2, ensure_ascii=False)

            winner = judge_parsed.get("winner", "unknown")
            print(f"  Winner: {winner}")
        else:
            print("  WARNING: Judge produced no valid JSON — using first proposal")
            save_proposal(run_dir, "judge_raw", judge_result["content"])
            content_str = proposals[0][1]

    # === RED TEAM (critical only) ===
    if debate_level == "critical" and models.get("red_team"):
        red_team_model = models["red_team"]
        print(f"\n  Running red team ({red_team_model})...")
        red_team_system = (
            "You are a red team attacker. Find every way this architecture can fail. "
            "Be ruthless. Output a JSON object with a single key 'red_team_findings' "
            "containing an array of strings. Do not wrap in code fences."
        )
        red_team_user = f"Architecture decision to attack:\n{content_str}"
        try:
            rt_result = call_litellm(red_team_model, red_team_system, red_team_user, config, models)
            total_tokens += rt_result["prompt_tokens"] + rt_result["completion_tokens"]
            rt_parsed = extract_json_from_response(rt_result["content"])
            if rt_parsed:
                # Save red team findings
                rt_path = run_dir / "debate_proposals" / "red_team_findings.json"
                rt_path.write_text(
                    json.dumps(rt_parsed, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                # Merge findings into architecture
                arch = json.loads(content_str)
                findings = rt_parsed.get("red_team_findings", rt_parsed.get("findings", []))
                if isinstance(findings, list):
                    arch["red_team_findings"] = findings
                content_str = json.dumps(arch, indent=2, ensure_ascii=False)
                print(f"  Red team: {len(findings)} findings merged")
        except Exception as e:
            print(f"  WARNING: Red team failed ({e}), continuing without it")

    # Write final artifact
    artifact_path = run_dir / "05_architecture_decision.json"
    artifact_path.write_text(content_str, encoding="utf-8")
    print(f"\n  Wrote: {artifact_path}")

    # Validate
    val_result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "validate_schema.py"), slug, "05_architecture_decision"],
        capture_output=True, text=True, timeout=30
    )
    print(f"  {val_result.stdout.strip()}")

    if val_result.returncode != 0:
        print("WARNING: Schema validation failed. Artifact written but may need manual fix.")

    update_manifest(run_dir, content_str, total_tokens)
    print(f"\n  Done. Total tokens: {total_tokens}")


if __name__ == "__main__":
    main()
