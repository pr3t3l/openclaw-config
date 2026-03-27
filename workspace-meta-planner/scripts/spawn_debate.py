#!/usr/bin/env python3
"""
spawn_debate.py — Multi-model 3-round debate for any planner phase.

Round 1: Independent proposals from N models
Round 2: Cross-critique + refinement (each model sees others' work)
Round 3: Consolidation (one model merges the best elements)
Optional: Red Team (adversarial review, critical/deep only)

Usage:
  python3 spawn_debate.py <slug> [--phase <phase_name>]
  phase_name: architecture_planner (default), gap_finder, scope_framer,
              data_flow_mapper, lessons_validator
"""

import argparse
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

# Phase → (skill_dir, artifact_name, upstream_artifacts)
PHASE_CONFIG = {
    "architecture_planner": ("architecture-planner", "05_architecture_decision", ["00_intake_summary", "01_gap_analysis", "02_scope_decision", "03_data_flow_map", "04_contracts"]),
    "gap_finder": ("gap-finder", "01_gap_analysis", ["00_intake_summary"]),
    "scope_framer": ("scope-framer", "02_scope_decision", ["00_intake_summary", "01_gap_analysis"]),
    "data_flow_mapper": ("data-flow-mapper", "03_data_flow_map", ["00_intake_summary", "01_gap_analysis", "02_scope_decision"]),
    "lessons_validator": ("lessons-validator", "08_plan_review", ["00_intake_summary", "01_gap_analysis", "02_scope_decision", "03_data_flow_map", "04_contracts", "05_architecture_decision", "06_implementation_plan", "07_cost_estimate"]),
}


def calculate_cost(model, input_tokens, output_tokens):
    p = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * p["input"] / 1_000_000) + (output_tokens * p["output"] / 1_000_000)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    return Path(path).read_text(encoding="utf-8")


def call_litellm(model, system_prompt, user_prompt, config, models_cfg, max_tokens=None):
    """Call LiteLLM proxy via curl."""
    if max_tokens is None:
        max_tokens = config["defaults"]["max_tokens_debate"]

    proxy_url = models_cfg["litellm_proxy"]
    api_key = models_cfg.get("litellm_api_key", "")

    payload = json.dumps({
        "model": model, "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }, ensure_ascii=True)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(payload.encode("utf-8"))
        tmp_path = f.name

    curl_timeout = config["defaults"]["curl_max_time"]
    sub_timeout = curl_timeout + config["defaults"]["subprocess_buffer"]

    try:
        cmd = ["curl", "-s", "-S", "--max-time", str(curl_timeout), "-H", "Content-Type: application/json"]
        if api_key:
            cmd.extend(["-H", f"Authorization: Bearer {api_key}"])
        cmd.extend(["--data-binary", f"@{tmp_path}", f"{proxy_url}/v1/chat/completions"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=sub_timeout)
        if result.returncode != 0:
            raise Exception(f"curl failed (rc={result.returncode}): {result.stderr[:300]}")
        if not result.stdout.strip():
            raise Exception(f"Empty response. stderr: {result.stderr[:300]}")

        response = json.loads(result.stdout)
        if "error" in response:
            raise Exception(f"LiteLLM error: {response['error']}")

        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        inp = usage.get("prompt_tokens", 0)
        out = usage.get("completion_tokens", 0)
        return {"content": content, "prompt_tokens": inp, "completion_tokens": out, "cost": calculate_cost(model, inp, out)}
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
            if depth == 0: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(stripped[start:i + 1])
                except json.JSONDecodeError:
                    start = None
    return None


def build_upstream_context(run_dir, upstream_artifacts):
    """Load specified upstream artifacts as context."""
    parts = []
    for artifact in upstream_artifacts:
        path = run_dir / f"{artifact}.json"
        if path.exists():
            parts.append(f"=== {artifact}.json ===\n{load_text(path)}\n=== END {artifact}.json ===")

    # System config + models.json (always useful)
    for fname in ["system_configuration.md"]:
        p = WORKSPACE / fname
        if p.exists():
            parts.append(f"=== {fname} ===\n{load_text(p)}\n=== END {fname} ===")

    models_path = WORKSPACE / "models.json"
    if models_path.exists():
        parts.append(f"=== models.json ===\n{load_text(models_path)}\n=== END models.json ===")

    # Lessons learned for relevant phases
    ll_path = SHARED / "lessons_learned.md"
    if ll_path.exists():
        parts.append(f"=== lessons_learned.md ===\n{load_text(ll_path)}\n=== END lessons_learned.md ===")

    return "\n\n".join(parts)


def save_proposal(run_dir, filename, content):
    """Save a proposal/result file in debate_proposals/."""
    proposals_dir = run_dir / "debate_proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    (proposals_dir / filename).write_text(content, encoding="utf-8")


def call_model_sync(model, system_prompt, user_prompt, config, models_cfg):
    """Call one model and return result dict."""
    print(f"    Calling {model}...")
    result = call_litellm(model, system_prompt, user_prompt, config, models_cfg)
    print(f"    {model}: {result['prompt_tokens'] + result['completion_tokens']} tokens (${result['cost']:.4f})")
    return result


def build_cross_critique_prompt(my_proposal, others):
    """Build prompt for round 2: cross-critique + refinement."""
    parts = [
        "You previously proposed this:",
        f"```json\n{my_proposal}\n```",
        "\nHere are proposals from other models:\n",
    ]
    for mdl, prop in others:
        parts.append(f"=== Proposal from {mdl} ===\n{prop}\n=== END ===\n")
    parts.append(
        "\nYour tasks:\n"
        "1. CRITIQUE each other proposal: What did they get right that you missed? What did they get wrong?\n"
        "2. REVISE your own proposal incorporating the best ideas from others and fixing any issues they found in yours.\n"
        "3. Be specific about what you changed and why.\n\n"
        "Output your REVISED proposal as valid JSON matching the same schema as your original."
    )
    return "\n".join(parts)


def build_consolidation_prompt(v2_proposals):
    """Build prompt for round 3: consolidation."""
    parts = [
        "Three AI models have debated and refined their proposals through cross-critique. "
        "Here are their final (v2) proposals:\n"
    ]
    for mdl, prop in v2_proposals:
        parts.append(f"=== Proposal v2 from {mdl} ===\n{prop}\n=== END ===\n")
    parts.append(
        "\nYour task: Create the BEST POSSIBLE final output by:\n"
        "1. Taking the strongest elements from each proposal\n"
        "2. Resolving any remaining disagreements with your judgment\n"
        "3. Ensuring consistency across all components\n"
        "4. Noting where the models agreed (high confidence) vs disagreed (risks to monitor)\n\n"
        "Output valid JSON matching the expected schema."
    )
    return "\n".join(parts)


RED_TEAM_PROMPT = """You are a ruthless security and systems engineer reviewing this architecture.
Your ONLY job is to find every way this can fail, break, be exploited, or cause problems.

DO NOT propose fixes. Only find problems.
Find all HIGH-SIGNAL issues you can justify. Maximum 10 issues — quality over quantity.
Do NOT pad with low-value findings. Every issue must be a real risk.

Classify each issue by severity:
- CRITICAL: Will definitely break in production. Must fix before building.
- HIGH: Likely to cause problems. Should fix before building.
- MEDIUM: Could cause problems under certain conditions. Fix in v2.
- LOW: Minor risk. Nice to fix but not blocking.

Categories: race conditions, data integrity, cost estimation accuracy, security,
error handling, human gate bypass, scalability, silent quality degradation,
dependency failures, maintenance risks.

Output JSON: {"total_issues": N, "issues": [{"id": "RT-001", "severity": "CRITICAL", "category": "...", "title": "...", "description": "...", "attack_vector": "..."}], "overall_risk_assessment": "..."}

Architecture to attack:
"""


def update_manifest(run_dir, artifact_name, content_str, total_cost, total_input, total_output, model_desc, debate_detail=None):
    """Update manifest with debate artifact."""
    manifest = load_json(run_dir / "manifest.json")
    file_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "status": "fresh", "hash": file_hash, "model": model_desc,
        "input_tokens": total_input, "output_tokens": total_output,
        "cost_usd": round(total_cost, 6), "timestamp": now,
    }
    if debate_detail:
        entry["debate_detail"] = debate_detail

    manifest["artifacts"][artifact_name] = entry

    # Invalidate downstream
    idx = ARTIFACT_ORDER.index(artifact_name)
    for downstream in ARTIFACT_ORDER[idx + 1:]:
        if manifest["artifacts"][downstream]["status"] == "fresh":
            manifest["artifacts"][downstream]["status"] = "stale"

    manifest["total_cost_usd"] = round(
        sum((v.get("cost_usd") or 0) for v in manifest["artifacts"].values()), 6
    )
    manifest["last_modified"] = now
    with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Multi-model debate")
    parser.add_argument("slug", help="Run slug")
    parser.add_argument("--phase", default="architecture_planner",
                        choices=list(PHASE_CONFIG.keys()),
                        help="Phase to run debate on")
    args = parser.parse_args()

    slug = args.slug
    phase = args.phase
    run_dir = WORKSPACE / "runs" / slug

    if not run_dir.exists():
        print(f"ERROR: Run not found: {run_dir}")
        sys.exit(1)

    config = load_json(WORKSPACE / "planner_config.json")
    models_cfg = load_json(WORKSPACE / "models.json")
    manifest = load_json(run_dir / "manifest.json")

    # Phase config
    skill_dir, artifact_name, upstream = PHASE_CONFIG[phase]
    skill_path = WORKSPACE / "skills" / skill_dir / "SKILL.md"
    if not skill_path.exists():
        print(f"ERROR: SKILL.md not found: {skill_path}")
        sys.exit(1)
    system_prompt = load_text(skill_path)
    user_prompt = build_upstream_context(run_dir, upstream)
    user_prompt += "\n\nProduce your proposal as valid JSON matching the expected schema."

    # Determine models (from manifest debate_level or intake)
    debate_level = manifest.get("debate_level")
    if not debate_level:
        intake_path = run_dir / "00_intake_summary.json"
        if intake_path.exists():
            debate_level = load_json(intake_path).get("debate_level_recommendation", "simple")
        else:
            debate_level = "simple"
        manifest["debate_level"] = debate_level
        with open(run_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

    analysis_level = manifest.get("analysis_level", "regular")
    debate_models_list = models_cfg["debate_models"].get(debate_level, ["claude-sonnet46"])
    consolidator_model = models_cfg["judge"].get(debate_level) or debate_models_list[0]

    print(f"Debate: {phase} ({slug})")
    print(f"  Analysis: {analysis_level} | Debate level: {debate_level}")
    print(f"  Models: {debate_models_list} | Consolidator: {consolidator_model}")

    total_cost = 0
    total_input = 0
    total_output = 0
    debate_detail = {}

    # === SINGLE MODEL (simple + regular) ===
    if len(debate_models_list) == 1:
        model = debate_models_list[0]
        print(f"\n  Single model: {model}")
        result = call_model_sync(model, system_prompt, user_prompt, config, models_cfg)
        total_input += result["prompt_tokens"]
        total_output += result["completion_tokens"]
        total_cost += result["cost"]

        parsed = extract_json_from_response(result["content"])
        if not parsed:
            save_proposal(run_dir, f"debug_{phase}_response.txt", result["content"])
            print(f"ERROR: No valid JSON from {model}.")
            sys.exit(1)

        save_proposal(run_dir, f"r1_proposal_{model}.json", json.dumps(parsed, indent=2, ensure_ascii=False))
        content_str = json.dumps(parsed, indent=2, ensure_ascii=False)

    else:
        # === MULTI-MODEL 3-ROUND DEBATE ===

        # ROUND 1: Independent proposals
        print(f"\n  === ROUND 1: Independent Proposals ===")
        r1_proposals = []
        r1_details = []
        for mdl in debate_models_list:
            result = call_model_sync(mdl, system_prompt, user_prompt, config, models_cfg)
            total_input += result["prompt_tokens"]
            total_output += result["completion_tokens"]
            total_cost += result["cost"]
            parsed = extract_json_from_response(result["content"])
            prop_str = json.dumps(parsed, indent=2, ensure_ascii=False) if parsed else result["content"]
            save_proposal(run_dir, f"r1_proposal_{mdl}.json", prop_str)
            if parsed:
                r1_proposals.append((mdl, prop_str))
            else:
                print(f"    WARNING: No valid JSON from {mdl} in R1")
            r1_details.append({"model": mdl, "input_tokens": result["prompt_tokens"],
                               "output_tokens": result["completion_tokens"], "cost_usd": round(result["cost"], 6)})

        if not r1_proposals:
            print("ERROR: No valid proposals from any model in Round 1.")
            sys.exit(1)

        # ROUND 2: Cross-critique + refinement
        print(f"\n  === ROUND 2: Cross-Critique + Refinement ===")
        r2_proposals = []
        r2_details = []
        for mdl, my_prop in r1_proposals:
            others = [(m, p) for m, p in r1_proposals if m != mdl]
            if not others:
                r2_proposals.append((mdl, my_prop))
                continue
            critique_prompt = build_cross_critique_prompt(my_prop, others)
            result = call_model_sync(mdl, system_prompt, critique_prompt, config, models_cfg)
            total_input += result["prompt_tokens"]
            total_output += result["completion_tokens"]
            total_cost += result["cost"]
            parsed = extract_json_from_response(result["content"])
            prop_str = json.dumps(parsed, indent=2, ensure_ascii=False) if parsed else my_prop
            save_proposal(run_dir, f"r2_proposal_{mdl}.json", prop_str)
            r2_proposals.append((mdl, prop_str))
            r2_details.append({"model": mdl, "input_tokens": result["prompt_tokens"],
                               "output_tokens": result["completion_tokens"], "cost_usd": round(result["cost"], 6)})

        # ROUND 3: Consolidation
        print(f"\n  === ROUND 3: Consolidation ({consolidator_model}) ===")
        consolidation_prompt = build_consolidation_prompt(r2_proposals)
        cons_result = call_model_sync(consolidator_model, system_prompt, consolidation_prompt, config, models_cfg)
        total_input += cons_result["prompt_tokens"]
        total_output += cons_result["completion_tokens"]
        total_cost += cons_result["cost"]
        cons_parsed = extract_json_from_response(cons_result["content"])

        if cons_parsed:
            save_proposal(run_dir, "consolidation.json", json.dumps(cons_parsed, indent=2, ensure_ascii=False))
            content_str = json.dumps(cons_parsed, indent=2, ensure_ascii=False)
        else:
            print("  WARNING: Consolidator produced no valid JSON — using best R2 proposal")
            save_proposal(run_dir, "consolidation_raw.txt", cons_result["content"])
            content_str = r2_proposals[0][1]

        cons_detail = {"model": consolidator_model, "input_tokens": cons_result["prompt_tokens"],
                       "output_tokens": cons_result["completion_tokens"], "cost_usd": round(cons_result["cost"], 6)}

        debate_detail = {
            "rounds": 3,
            "round_1": r1_details,
            "round_2": r2_details,
            "consolidation": cons_detail,
        }

    # === RED TEAM (critical or deep) ===
    run_red_team = (debate_level == "critical" or analysis_level == "deep") and models_cfg.get("red_team")
    if run_red_team and len(debate_models_list) > 1:
        rt_model = models_cfg["red_team"]
        print(f"\n  === RED TEAM ({rt_model}) ===")
        try:
            rt_result = call_litellm(rt_model, RED_TEAM_PROMPT, content_str, config, models_cfg)
            total_input += rt_result["prompt_tokens"]
            total_output += rt_result["completion_tokens"]
            total_cost += rt_result["cost"]
            rt_parsed = extract_json_from_response(rt_result["content"])
            if rt_parsed:
                save_proposal(run_dir, "red_team_findings.json", json.dumps(rt_parsed, indent=2, ensure_ascii=False))
                # Merge findings into main artifact
                arch = json.loads(content_str)
                findings = rt_parsed.get("issues", rt_parsed.get("red_team_findings", []))
                if isinstance(findings, list):
                    arch["red_team_findings"] = [f.get("title", str(f)) if isinstance(f, dict) else f for f in findings]
                content_str = json.dumps(arch, indent=2, ensure_ascii=False)
                print(f"    {len(findings)} findings merged")
            debate_detail["red_team"] = {
                "model": rt_model, "input_tokens": rt_result["prompt_tokens"],
                "output_tokens": rt_result["completion_tokens"], "cost_usd": round(rt_result["cost"], 6),
            }
        except Exception as e:
            print(f"    WARNING: Red team failed ({e})")

    # Write artifact
    artifact_path = run_dir / f"{artifact_name}.json"
    artifact_path.write_text(content_str, encoding="utf-8")
    print(f"\n  Wrote: {artifact_path}")

    # Validate
    val = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "validate_schema.py"), slug, artifact_name],
        capture_output=True, text=True, timeout=30,
    )
    print(f"  {val.stdout.strip()}")
    if val.returncode != 0:
        print("WARNING: Schema validation failed.")

    # Model description
    model_desc = "+".join(debate_models_list)
    if len(debate_models_list) > 1:
        model_desc = f"debate:{model_desc}|cons:{consolidator_model}"
        if debate_detail.get("red_team"):
            model_desc += f"|rt:{models_cfg['red_team']}"

    update_manifest(run_dir, artifact_name, content_str, total_cost, total_input, total_output, model_desc, debate_detail or None)
    print(f"\n  Done. Cost: ${total_cost:.6f} ({total_input}in/{total_output}out)")


if __name__ == "__main__":
    main()
