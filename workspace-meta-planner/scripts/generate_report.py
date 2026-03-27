#!/usr/bin/env python3
"""
generate_report.py — Generate an HTML report for a completed plan.

1. Reads all 9 artifacts + manifest + debate proposals
2. Calls Sonnet to generate narrative section (in user's language)
3. Builds fact_pack, calls GPT-5.2 to review narrative against facts
4. If GPT found issues, regenerates narrative with corrections
5. Builds visual + technical sections programmatically
6. Assembles self-contained HTML report

Usage: python3 generate_report.py <slug>
Output: runs/<slug>/<slug>_report.html
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/home/robotin/.openclaw/workspace-meta-planner")

PRICING = {
    "claude-sonnet46": {"input": 3.0, "output": 15.0},
    "chatgpt-gpt54": {"input": 0.0, "output": 0.0},  # OAuth subscription
}


def load_json_safe(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_text_safe(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def call_litellm(model, system_prompt, user_prompt, max_tokens=8192):
    """Simplified call for report generation."""
    models_cfg = load_json_safe(WORKSPACE / "models.json") or {}
    proxy_url = models_cfg.get("litellm_proxy", "http://127.0.0.1:4000")
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

    try:
        cmd = ["curl", "-s", "-S", "--max-time", "300", "-H", "Content-Type: application/json"]
        if api_key:
            cmd.extend(["-H", f"Authorization: Bearer {api_key}"])
        cmd.extend(["--data-binary", f"@{tmp_path}", f"{proxy_url}/v1/chat/completions"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=350)
        if result.returncode != 0:
            raise Exception(f"curl failed: {result.stderr[:200]}")

        response = json.loads(result.stdout)
        if "error" in response:
            raise Exception(f"API error: {response['error']}")

        return response["choices"][0]["message"]["content"]
    finally:
        os.unlink(tmp_path)


def build_narrative_context(run_dir):
    """Build context for narrative generation."""
    parts = []
    manifest = load_json_safe(run_dir / "manifest.json")
    if manifest:
        parts.append(f"Plan ID: {manifest.get('plan_id')}")
        parts.append(f"Raw idea: {manifest.get('raw_idea', 'N/A')}")
        parts.append(f"Total cost: ${manifest.get('total_cost_usd', 0):.4f}")

    artifact_names = [
        "00_intake_summary", "01_gap_analysis", "02_scope_decision",
        "03_data_flow_map", "04_contracts", "05_architecture_decision",
        "06_implementation_plan", "07_cost_estimate", "08_plan_review",
    ]
    for name in artifact_names:
        data = load_text_safe(run_dir / f"{name}.json")
        if data:
            # Truncate large artifacts
            if len(data) > 4000:
                data = data[:4000] + "\n... (truncated)"
            parts.append(f"=== {name} ===\n{data}")

    # Debate proposals summary
    debate_dir = run_dir / "debate_proposals"
    if debate_dir.exists():
        judge = load_json_safe(debate_dir / "judge_evaluation.json")
        if judge:
            parts.append(f"=== Judge Evaluation ===\n{json.dumps(judge, indent=2)[:2000]}")
        rt = load_json_safe(debate_dir / "red_team_findings.json")
        if rt:
            parts.append(f"=== Red Team Findings ===\n{json.dumps(rt, indent=2)[:2000]}")

    return "\n\n".join(parts)


def build_visual_html(run_dir):
    """Build visual section programmatically."""
    manifest = load_json_safe(run_dir / "manifest.json") or {}
    gaps = load_json_safe(run_dir / "01_gap_analysis.json") or {}
    scope = load_json_safe(run_dir / "02_scope_decision.json") or {}
    cost = load_json_safe(run_dir / "07_cost_estimate.json") or {}

    html = ['<h2>Visual Summary</h2>']

    # Cost table
    html.append('<h3>Cost Breakdown by Phase</h3>')
    html.append('<table><tr><th>Phase</th><th>Artifact</th><th>Model</th><th>Tokens</th><th>Cost</th></tr>')
    for name, info in manifest.get("artifacts", {}).items():
        num = int(name[:2])
        phase = "A" if num <= 2 else "B" if num <= 5 else "C"
        model = info.get("model", "N/A")
        inp = info.get("input_tokens", "-")
        out = info.get("output_tokens", "-")
        c = info.get("cost_usd", 0)
        html.append(f'<tr><td>{phase}</td><td>{name}</td><td>{model}</td><td>{inp}/{out}</td><td>${c:.4f}</td></tr>')
    html.append(f'<tr style="font-weight:bold"><td colspan="4">TOTAL</td><td>${manifest.get("total_cost_usd", 0):.4f}</td></tr>')
    html.append('</table>')

    # Gap summary
    html.append('<h3>Gap Analysis</h3>')
    html.append(f'<p>Readiness score: <strong>{gaps.get("readiness_score", "N/A")}/100</strong> | '
                f'Blockers: {gaps.get("blocker_count", 0)} | Advisory: {gaps.get("advisory_count", 0)}</p>')
    html.append('<ul>')
    for g in gaps.get("gaps", [])[:8]:
        sev = g.get("severity", "?").upper()
        html.append(f'<li><strong>[{sev}]</strong> {g.get("id", "?")}: {g.get("description", "")[:120]}</li>')
    html.append('</ul>')

    # Scope comparison
    html.append('<h3>Scope Options</h3>')
    html.append('<table><tr><th>Version</th><th>Features</th><th>Agents</th><th>Hours</th><th>Cost/Run</th></tr>')
    for ver_name in ["mvp", "standard", "advanced"]:
        ver = scope.get("versions", {}).get(ver_name, {})
        features = len(ver.get("features_included", []))
        agents = ver.get("estimated_agents_scripts", "?")
        hours = ver.get("estimated_effort_hours", "?")
        cpr = ver.get("estimated_cost_per_run", "?")
        html.append(f'<tr><td>{ver_name.upper()}</td><td>{features} features</td><td>{agents}</td><td>{hours}h</td><td>${cpr}</td></tr>')
    html.append('</table>')

    # Per-run cost
    html.append('<h3>Estimated Workflow Cost</h3>')
    html.append(f'<p>Per run: <strong>${cost.get("per_run_total", 0):.4f}</strong> | '
                f'Monthly ({cost.get("monthly_estimate", {}).get("runs_per_month", "?")}/mo): '
                f'<strong>${cost.get("monthly_estimate", {}).get("total_monthly_cost", 0):.4f}</strong> | '
                f'Budget feasible: {"Yes" if cost.get("budget_feasible") else "No"}</p>')

    return "\n".join(html)


def build_technical_html(run_dir):
    """Build technical section from raw artifacts."""
    html = ['<h2>Technical Details</h2>']

    arch = load_json_safe(run_dir / "05_architecture_decision.json")
    if arch:
        components = arch.get("components", {})
        html.append('<h3>Architecture</h3>')
        html.append('<h4>Agents</h4><ul>')
        for a in components.get("agents", []):
            html.append(f'<li><strong>{a.get("name")}</strong> ({a.get("model")}) — {a.get("purpose", "")[:100]}</li>')
        html.append('</ul>')
        html.append('<h4>Scripts</h4><ul>')
        for s in components.get("scripts", []):
            html.append(f'<li><strong>{s.get("name")}</strong> ({s.get("language", "?")}) — {s.get("purpose", "")[:100]}</li>')
        html.append('</ul>')

    plan = load_json_safe(run_dir / "06_implementation_plan.json")
    if plan:
        html.append('<h3>Implementation Plan</h3>')
        for phase in plan.get("phases", []):
            html.append(f'<h4>Phase {phase.get("phase_number")}: {phase.get("name")}</h4>')
            html.append(f'<p>Effort: {phase.get("estimated_effort_hours")}h | Gate: {"Yes" if phase.get("human_gate", {}).get("required") else "No"}</p>')
            html.append('<ul>')
            for task in phase.get("tasks", []):
                html.append(f'<li>{task}</li>')
            html.append('</ul>')

    review = load_json_safe(run_dir / "08_plan_review.json")
    if review:
        html.append(f'<h3>Verdict: {review.get("verdict", "UNKNOWN")}</h3>')
        html.append(f'<p>{review.get("summary", "")}</p>')
        if review.get("revision_items"):
            html.append('<h4>Revision Items</h4><ul>')
            for item in review["revision_items"]:
                html.append(f'<li>{item}</li>')
            html.append('</ul>')

    return "\n".join(html)


def assemble_html(narrative, visual_html, technical_html, manifest):
    """Assemble the final HTML report."""
    plan_id = manifest.get("plan_id", "unknown")
    total_cost = manifest.get("total_cost_usd", 0)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Plan Report: {plan_id}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }}
  h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
  h2 {{ color: #16213e; margin-top: 40px; border-bottom: 1px solid #e0e0e0; padding-bottom: 8px; }}
  h3 {{ color: #0f3460; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #16213e; color: white; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  .narrative {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #0f3460; margin: 20px 0; }}
  .meta {{ color: #666; font-size: 0.9em; }}
  ul {{ padding-left: 20px; }}
  li {{ margin: 4px 0; }}
  nav {{ background: #16213e; color: white; padding: 12px 20px; border-radius: 8px; margin-bottom: 30px; }}
  nav a {{ color: #a8d8ea; margin-right: 20px; text-decoration: none; }}
  nav a:hover {{ color: white; text-decoration: underline; }}
</style>
</head>
<body>
<h1>Plan Report: {plan_id}</h1>
<p class="meta">Generated: {now} | Planning cost: ${total_cost:.4f}</p>

<nav>
  <a href="#narrative">Narrative</a>
  <a href="#visual">Visual Summary</a>
  <a href="#technical">Technical Details</a>
</nav>

<section id="narrative">
<h2>Narrative</h2>
<div class="narrative">
{narrative}
</div>
</section>

<section id="visual">
{visual_html}
</section>

<section id="technical">
{technical_html}
</section>

<footer>
<p class="meta">Generated by Meta-Workflow Planner | <a href="https://github.com/pr3t3l/openclaw-config">openclaw-config</a></p>
</footer>
</body>
</html>"""


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <slug>")
        sys.exit(1)

    slug = sys.argv[1]
    run_dir = WORKSPACE / "runs" / slug

    if not run_dir.exists():
        print(f"ERROR: Run not found: {run_dir}")
        sys.exit(1)

    manifest = load_json_safe(run_dir / "manifest.json") or {}
    print(f"Generating report for: {slug}")

    # Step 1: Generate narrative with Sonnet
    print("  Generating narrative (Sonnet)...")
    skill = load_text_safe(WORKSPACE / "skills" / "report-generator" / "SKILL.md") or ""
    context = build_narrative_context(run_dir)
    narrative = call_litellm("claude-sonnet46", skill, context)
    print(f"  Narrative generated ({len(narrative)} chars)")

    # Step 2: Build fact pack
    print("  Building fact pack...")
    subprocess.run([sys.executable, str(WORKSPACE / "scripts" / "build_fact_pack.py"), slug],
                   capture_output=True, timeout=30)
    fact_pack = load_json_safe(run_dir / "fact_pack.json") or {}

    # Step 3: GPT reviews narrative against facts
    print("  Reviewing narrative (GPT-5.2)...")
    review_prompt = (
        f"Review this narrative summary of a workflow plan.\n"
        f"Check it against the verified facts below.\n"
        f"Flag any inaccuracies, missing important points, or misleading claims.\n"
        f"If everything is accurate, respond with just 'ACCURATE'.\n\n"
        f"NARRATIVE:\n{narrative}\n\n"
        f"VERIFIED FACTS:\n{json.dumps(fact_pack, indent=2)}"
    )
    review = call_litellm("chatgpt-gpt54", "You are a fact-checker. Be concise.", review_prompt, max_tokens=2000)

    # Step 4: Regenerate if issues found
    if "ACCURATE" not in review.upper()[:20]:
        print(f"  GPT found issues — regenerating narrative...")
        narrative = call_litellm("claude-sonnet46", skill,
                                 context + f"\n\nCORRECTIONS FROM REVIEWER:\n{review}")
        print(f"  Narrative regenerated ({len(narrative)} chars)")
    else:
        print("  Narrative approved by reviewer")

    # Step 5: Build visual + technical sections
    visual_html = build_visual_html(run_dir)
    technical_html = build_technical_html(run_dir)

    # Step 6: Assemble HTML
    report_html = assemble_html(narrative, visual_html, technical_html, manifest)
    report_path = run_dir / f"{slug}_report.html"
    report_path.write_text(report_html, encoding="utf-8")

    print(f"\n  Report generated: {report_path}")
    print(f"  Size: {len(report_html)} bytes")


if __name__ == "__main__":
    main()
