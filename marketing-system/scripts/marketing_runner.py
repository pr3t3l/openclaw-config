#!/usr/bin/env python3
"""Marketing Weekly Runner — generates content assets for a weekly run.

Orchestrates:
  1. Preflight (strategy valid + approved)
  2. Version pin strategy
  3. Phase M-scripts: script_generator (claude-sonnet46)
  4. Phase M-ads: ad_copy_generator (claude-sonnet46)
  5. Phase M-emails: email_generator (claude-sonnet46)
  6. Gate M1: Telegram review of scripts + ads + emails
  7. Phase M-calendar: calendar_generator (chatgpt-gpt54)
  8. Phase M-quality: semantic_quality_reviewer (chatgpt-gpt54)
  9. Gate M2: Telegram review of calendar + quality
  → Updates run_manifest.json

Usage:
  python3 marketing_runner.py <product_id> <week>
  python3 marketing_runner.py misterio-semanal 2026-W14
  python3 marketing_runner.py <product_id> <week> approve
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPTS_DIR.parent / "skills"
PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")

CREATIVE_MODEL = "claude-sonnet46"
UTILITY_MODEL = "chatgpt-gpt54"

sys.path.insert(0, str(SCRIPTS_DIR))

from llm_caller import call_llm, extract_json_from_response
from telegram_sender import send_message
from gate_handler import create_gate, resolve_gate


CONTENT_PHASES = [
    {"name": "script_generator", "skill": "script-generator",
     "output": "reels_scripts_draft.json", "model": CREATIVE_MODEL},
    {"name": "ad_copy_generator", "skill": "ad-copy-generator",
     "output": "meta_ads_copy_draft.json", "model": CREATIVE_MODEL},
    {"name": "email_generator", "skill": "email-generator",
     "output": "email_sequence_draft.json", "model": CREATIVE_MODEL},
]

POST_GATE_PHASES = [
    {"name": "calendar_generator", "skill": "calendar-generator",
     "output": "publishing_calendar_draft.json", "model": UTILITY_MODEL},
    {"name": "quality_reviewer", "skill": "quality-reviewer",
     "output": "quality_report.json", "model": UTILITY_MODEL},
]


def run_marketing(product_id: str, week: str = None) -> bool:
    """Run the full marketing weekly workflow."""
    from preflight_check import run_preflight

    # Preflight
    preflight = run_preflight(product_id, require_strategy=True)
    if not preflight["passed"]:
        msg = f"🛑 Marketing preflight failed:\n" + "\n".join(preflight["errors"])
        print(msg)
        send_message(msg)
        return False

    product_dir = PRODUCTS_DIR / product_id
    manifest = json.loads((product_dir / "product_manifest.json").read_text())
    strategy_version = manifest["active_strategy_version"]

    # Determine week
    if not week:
        now = datetime.now()
        week = f"{now.year}-W{now.isocalendar()[1]:02d}"

    # Create run directory
    run_dir = product_dir / "weekly_runs" / week
    drafts_dir = run_dir / "drafts"
    approved_dir = run_dir / "approved"
    reports_dir = run_dir / "reports"
    for d in [drafts_dir, approved_dir, reports_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"MARKETING WEEKLY — {product_id} ({week})")
    print(f"Strategy pinned: {strategy_version}")
    print(f"{'='*50}")

    # Load strategy context
    strategy_dir = product_dir / "strategies" / strategy_version
    strategy_context = _load_strategy_context(strategy_dir)

    # Load weekly case brief
    brief_path = run_dir / "weekly_case_brief.json"
    if not brief_path.exists():
        msg = (f"❌ Missing weekly_case_brief.json\n"
               f"Create: {brief_path}\n"
               f"Then re-run.")
        print(msg)
        send_message(msg)
        return False
    case_brief = json.loads(brief_path.read_text())

    # Load Growth feedback (optional)
    growth_context = _load_growth_context(product_dir)

    # Create run manifest
    run_manifest = {
        "product_id": product_id,
        "run_id": week,
        "started_at": datetime.now().isoformat(),
        "strategy_version_used": strategy_version,
        "status": "running",
        "gates": {
            "M1_content": {"status": "not_started"},
            "M2_calendar_quality": {"status": "not_started"},
        },
        "outputs": {},
        "cost_usd": 0.0,
    }

    # ─── Phase 1: Content Generation (scripts + ads + emails) ───
    print("\n=== PHASE 1: Content Generation ===")
    for phase in CONTENT_PHASES:
        print(f"\n--- {phase['name']} ---")
        result = _run_content_agent(
            phase, product_id, week, strategy_version,
            strategy_context, case_brief, growth_context, drafts_dir
        )
        if result:
            run_manifest["outputs"][phase["output"]] = f"drafts/{phase['output']}"
            print(f"  ✅ {phase['output']}")
        else:
            print(f"  ❌ {phase['name']} failed")
            run_manifest["outputs"][phase["output"]] = None

    # ─── Gate M1: Content Review ───
    print("\n--- Gate M1: Content Review ---")
    run_manifest["gates"]["M1_content"]["status"] = "pending"
    run_manifest["status"] = "awaiting_gate_M1"

    m1_summary = _format_content_gate(product_id, week, drafts_dir)
    send_message(m1_summary)
    create_gate(product_id, "M1", "marketing", m1_summary, run_id=week)

    # ─── Phase 2: Calendar + Quality (runs after M1 in v1 — async gate) ───
    print("\n=== PHASE 2: Calendar + Quality ===")

    # Calendar needs the draft outputs as context
    all_drafts = _load_drafts(drafts_dir)

    for phase in POST_GATE_PHASES:
        print(f"\n--- {phase['name']} ---")
        result = _run_content_agent(
            phase, product_id, week, strategy_version,
            strategy_context, case_brief, growth_context, drafts_dir,
            extra_context=all_drafts
        )
        if result:
            run_manifest["outputs"][phase["output"]] = f"drafts/{phase['output']}"
            print(f"  ✅ {phase['output']}")
        else:
            print(f"  ❌ {phase['name']} failed")

    # ─── Gate M2: Calendar + Quality ───
    print("\n--- Gate M2: Calendar + Quality ---")
    run_manifest["gates"]["M2_calendar_quality"]["status"] = "pending"
    run_manifest["status"] = "awaiting_gate_M2"

    m2_summary = _format_calendar_gate(product_id, week, drafts_dir)
    send_message(m2_summary)
    create_gate(product_id, "M2", "marketing", m2_summary, run_id=week)

    # Save run manifest
    run_manifest["completed_at"] = datetime.now().isoformat()
    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Marketing Weekly {week} COMPLETE")
    print(f"Status: awaiting approval")
    print(f"Approve: /marketing approve {week}")
    print(f"{'='*50}")

    send_message(
        f"🚀 Marketing Weekly {week} completo\n"
        f"Producto: {product_id} | Strategy: {strategy_version}\n\n"
        f"Assets generados:\n"
        + "\n".join(f"  - {k}" for k, v in run_manifest["outputs"].items() if v)
        + f"\n\nRevisa y aprueba:\n/marketing approve {week}"
    )

    return True


def approve_marketing(product_id: str, week: str) -> bool:
    """Approve marketing run — promote drafts to approved."""
    product_dir = PRODUCTS_DIR / product_id
    run_dir = product_dir / "weekly_runs" / week
    drafts_dir = run_dir / "drafts"
    approved_dir = run_dir / "approved"
    approved_dir.mkdir(exist_ok=True)

    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        print(f"No run manifest found for {week}")
        return False

    manifest = json.loads(manifest_path.read_text())

    # Copy drafts to approved
    promoted = []
    for f in drafts_dir.iterdir():
        if f.suffix == ".json" and "quality_report" not in f.name:
            shutil.copy2(f, approved_dir / f.name)
            promoted.append(f.name)

    # Update manifest
    manifest["status"] = "completed"
    manifest["approved_at"] = datetime.now().isoformat()
    manifest["approved_by"] = "Alfredo"
    for gate in manifest.get("gates", {}).values():
        if gate["status"] == "pending":
            gate["status"] = "approved"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    # Resolve gates
    for gate_name in ["M1", "M2"]:
        try:
            resolve_gate(product_id, gate_name, "approved", "Alfredo")
        except (ValueError, KeyError):
            pass

    msg = (f"✅ Marketing {week} APROBADO\n"
           f"Assets promovidos: {', '.join(promoted)}\n"
           f"Listos para publicar.")
    print(msg)
    send_message(msg)
    return True


def _run_content_agent(phase: dict, product_id: str, week: str,
                       strategy_version: str, strategy_ctx: dict,
                       case_brief: dict, growth_ctx: dict,
                       output_dir: Path, extra_context: dict = None) -> dict | None:
    """Run a single content generation agent."""
    skill_path = SKILLS_DIR / phase["skill"] / "SKILL.md"
    skill_md = skill_path.read_text()

    # Build context
    ctx_parts = []
    for name, data in strategy_ctx.items():
        ctx_parts.append(f"## {name}\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```")

    ctx_parts.append(f"## weekly_case_brief.json\n```json\n{json.dumps(case_brief, indent=2, ensure_ascii=False)}\n```")

    for name, data in growth_ctx.items():
        ctx_parts.append(f"## {name}\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```")

    if extra_context:
        for name, data in extra_context.items():
            ctx_parts.append(f"## {name}\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```")

    context = "\n\n".join(ctx_parts)
    lang = strategy_ctx.get("product_brief", {}).get("language", "es")

    system_prompt = f"""{skill_md}

CONTEXT:
{context}

REQUIRED FIELDS:
- product_id: "{product_id}"
- run_id: "{week}"
- strategy_version_used: "{strategy_version}"
- All text content in {lang}
"""

    user_prompt = f"Generate {phase['output']} for {product_id} week {week}. Output ONLY the JSON."

    try:
        text, usage = call_llm(phase["model"], system_prompt, user_prompt,
                                max_tokens=8192, temperature=0.5)
        parsed = extract_json_from_response(text)
        if not parsed:
            (output_dir / f"debug_{phase['name']}.txt").write_text(text)
            return None

        out_path = output_dir / phase["output"]
        out_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
        print(f"  Tokens: {usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out")
        return parsed

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def _load_strategy_context(strategy_dir: Path) -> dict:
    """Load all strategy files as context."""
    ctx = {}
    for f in ["buyer_persona.json", "brand_strategy.json", "channel_strategy.json",
              "seo_architecture.json", "market_analysis.json"]:
        path = strategy_dir / f
        if path.exists():
            ctx[f.replace(".json", "")] = json.loads(path.read_text())
    return ctx


def _load_growth_context(product_dir: Path) -> dict:
    """Load Growth feedback files if they exist."""
    ctx = {}
    kb_path = product_dir / "knowledge_base_marketing.json"
    if kb_path.exists():
        kb = json.loads(kb_path.read_text())
        # Only include if there's actual content
        if kb.get("tactical_learnings", {}).get("winning_patterns") or \
           kb.get("tactical_learnings", {}).get("losing_patterns"):
            ctx["knowledge_base_marketing"] = kb

    # Find latest optimization_actions from previous week's growth
    runs_dir = product_dir / "weekly_runs"
    if runs_dir.exists():
        weeks = sorted([d.name for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
        for w in weeks:
            opt_path = runs_dir / w / "growth" / "optimization_actions.json"
            if opt_path.exists():
                ctx["optimization_actions"] = json.loads(opt_path.read_text())
                break

    return ctx


def _load_drafts(drafts_dir: Path) -> dict:
    """Load all draft files as context."""
    ctx = {}
    for f in drafts_dir.iterdir():
        if f.suffix == ".json":
            try:
                ctx[f.stem] = json.loads(f.read_text())
            except json.JSONDecodeError:
                pass
    return ctx


def _format_content_gate(product_id: str, week: str, drafts_dir: Path) -> str:
    """Format Gate M1 message for Telegram."""
    lines = [f"🎬 Marketing {week} — Gate M1: Content Review",
             f"Producto: {product_id}", ""]

    for fname, label in [
        ("reels_scripts_draft.json", "Video Scripts"),
        ("meta_ads_copy_draft.json", "Ad Copy"),
        ("email_sequence_draft.json", "Email Sequence"),
    ]:
        path = drafts_dir / fname
        if path.exists():
            data = json.loads(path.read_text())
            if "scripts" in data:
                lines.append(f"✅ {label}: {len(data['scripts'])} scripts x 2 variants")
            elif "ad_set" in data:
                variants = data.get("ad_set", {}).get("variants", [])
                lines.append(f"✅ {label}: {len(variants)} variants")
            elif "sequence" in data:
                lines.append(f"✅ {label}: {len(data['sequence'])} emails")
            else:
                lines.append(f"✅ {label}: generado")
        else:
            lines.append(f"❌ {label}: no generado")

    lines += ["", "Decisión:", f"/marketing approve {week}", f"/marketing reject {week}"]
    return "\n".join(lines)


def _format_calendar_gate(product_id: str, week: str, drafts_dir: Path) -> str:
    """Format Gate M2 message for Telegram."""
    lines = [f"📅 Marketing {week} — Gate M2: Calendar + Quality",
             f"Producto: {product_id}", ""]

    cal_path = drafts_dir / "publishing_calendar_draft.json"
    if cal_path.exists():
        cal = json.loads(cal_path.read_text())
        total = cal.get("summary", {}).get("total_posts", "?")
        lines.append(f"✅ Calendar: {total} posts scheduled")
    else:
        lines.append(f"❌ Calendar: no generado")

    qr_path = drafts_dir / "quality_report.json"
    if qr_path.exists():
        qr = json.loads(qr_path.read_text())
        lines.append(f"✅ Quality: {qr.get('overall_status', '?')}")
        for asset in qr.get("assets", []):
            issues = [i for i in asset.get("issues", []) if i.get("severity") == "critical"]
            if issues:
                lines.append(f"  ⚠ {asset['asset_type']}: {len(issues)} critical issues")
    else:
        lines.append(f"❌ Quality report: no generado")

    lines += ["", "Decisión:", f"/marketing approve {week}", f"/marketing reject {week}"]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 marketing_runner.py <product_id> <week> [approve]")
        sys.exit(1)

    product_id = sys.argv[1]
    week = sys.argv[2]

    if len(sys.argv) > 3 and sys.argv[3] == "approve":
        approve_marketing(product_id, week)
    else:
        run_marketing(product_id, week)
