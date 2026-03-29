#!/usr/bin/env python3
"""Growth Intelligence Runner — 10-step analysis pipeline.

Steps:
  1. Read metrics_input.json
  2. metrics_calculator.py → calculated_metrics.json
  3. Metrics Interpreter (chatgpt-gpt54) → performance_report.json
  4. Diagnosis Agent (claude-sonnet46) → diagnosis.json + optimization_actions.json
  5. experiment_manager.py → update experiments_log.json
  6. Learning Extractor (chatgpt-gpt54) → append to knowledge_base_marketing.json
  7. pattern_promoter.py → evaluate promotions
  8. Evaluate strategy alerts → strategy_alert.json if applicable
  9. Write growth_run_manifest.json
  10. Telegram: report + actions + promotions

Usage:
  python3 growth_runner.py <product_id> <week>
  python3 growth_runner.py misterio-semanal 2026-W14
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPTS_DIR.parent / "skills"
PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")

INTERPRETER_MODEL = "chatgpt-gpt54"
DIAGNOSIS_MODEL = "claude-sonnet46"
EXTRACTOR_MODEL = "chatgpt-gpt54"

ALERT_COOLDOWN_DAYS = 14

sys.path.insert(0, str(SCRIPTS_DIR))

from llm_caller import call_llm, extract_json_from_response
from telegram_sender import send_message
from metrics_calculator import calculate as calc_metrics
from experiment_manager import process_proposals
from pattern_promoter import evaluate_promotions
import db


def _db_write(fn, *args, **kwargs):
    """Safe DB write — logs errors but never blocks the runner."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"  WARN: DB write failed ({fn.__name__}): {e}")
        return None


def _week_to_date(week_str):
    """Convert '2026-W17' to the Monday date of that ISO week."""
    return datetime.strptime(f"{week_str}-1", "%G-W%V-%u").date()


def run_growth(product_id: str, week: str) -> bool:
    """Run the full Growth Intelligence pipeline."""
    product_dir = PRODUCTS_DIR / product_id
    growth_dir = product_dir / "weekly_runs" / week / "growth"
    growth_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"GROWTH INTELLIGENCE — {product_id} ({week})")
    print(f"{'='*50}")

    # Load strategy version
    manifest_path = product_dir / "product_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    strategy_version = manifest.get("active_strategy_version", "unknown")

    # ─── Step 1: Verify metrics_input ───
    input_path = growth_dir / "metrics_input.json"
    if not input_path.exists():
        msg = f"❌ Missing metrics_input.json\nCreate: {input_path}"
        print(msg)
        send_message(msg)
        return False
    metrics_input = json.loads(input_path.read_text())
    print("Step 1: ✅ metrics_input.json loaded")

    # DB: resolve week date and find campaign
    week_date = _week_to_date(week)
    campaign = _db_write(db.get_campaign, product_id, f"weekly-{week}")
    campaign_db_id = campaign["id"] if campaign else None

    # ─── Step 2: Metrics Calculator (deterministic) ───
    print("\nStep 2: Calculating metrics...")
    calculated = calc_metrics(product_id, week)

    # DB: save platform metrics from metrics_input
    for platform_key in ["meta_ads", "email", "tiktok", "instagram", "google_ads"]:
        if platform_key in metrics_input:
            m = metrics_input[platform_key]
            _db_write(db.save_platform_metrics, product_id, campaign_db_id, week_date, platform_key, {
                "spend": m.get("spend", 0), "impressions": m.get("impressions", 0),
                "clicks": m.get("clicks", 0), "conversions": m.get("conversions", 0),
                "revenue": m.get("revenue", 0), "reach": m.get("reach", 0),
                "roas": m.get("roas", 0), "engagement_rate": m.get("engagement_rate", 0),
            })

    # ─── Step 3: Metrics Interpreter (LLM) ───
    print("\nStep 3: Interpreting metrics...")
    perf_report = _run_interpreter(product_id, week, strategy_version, calculated, growth_dir)

    # ─── Step 4: Diagnosis Agent (LLM) ───
    print("\nStep 4: Running diagnosis...")
    diagnosis, opt_actions = _run_diagnosis(product_id, week, strategy_version,
                                             calculated, product_dir, growth_dir)

    # DB: save growth analysis
    if diagnosis:
        _db_write(db.save_growth_analysis, product_id, campaign_db_id, week_date, {
            "performance_report": perf_report or {},
            "diagnosis": diagnosis,
            "optimization_actions": opt_actions or {},
            "root_cause": diagnosis.get("root_cause"),
            "decision_level": diagnosis.get("decision_level"),
            "problem_domain": diagnosis.get("problem_domain"),
        }, recommendations=(opt_actions or {}).get("actions", []))

    # ─── Step 5: Experiment Manager (deterministic) ───
    print("\nStep 5: Processing experiments...")
    if diagnosis:
        exp_result = process_proposals(product_id, week, diagnosis)
    else:
        exp_result = {"new_experiments_registered": [], "closures_processed": []}

    # ─── Step 6: Learning Extractor (LLM) ───
    print("\nStep 6: Extracting learnings...")
    kb_updates = _run_learning_extractor(product_id, week, calculated,
                                          diagnosis, metrics_input, product_dir, growth_dir)

    # DB: save KB entries
    if kb_updates:
        for p in kb_updates.get("new_winning_patterns", []):
            _db_write(db.add_kb_entry, product_id, {
                "pattern_id": p.get("pattern_id", ""),
                "category": "winning_patterns",
                "title": p.get("pattern", "")[:200],
                "description": p.get("pattern", ""),
                "evidence": [{"text": p.get("evidence", ""), "runs": p.get("evidence_runs_count", 1)}],
                "status": "active",
                "confidence": {"high": 0.9, "medium": 0.7, "low": 0.4}.get(p.get("confidence", "low"), 0.5),
            })
        for p in kb_updates.get("new_losing_patterns", []):
            _db_write(db.add_kb_entry, product_id, {
                "pattern_id": p.get("pattern_id", ""),
                "category": "losing_patterns",
                "title": p.get("pattern", "")[:200],
                "description": p.get("pattern", ""),
                "evidence": [{"text": p.get("evidence", ""), "runs": p.get("evidence_runs_count", 1)}],
                "status": "active",
                "confidence": {"high": 0.9, "medium": 0.7, "low": 0.4}.get(p.get("confidence", "low"), 0.5),
            })

    # DB: save experiments
    if diagnosis:
        for exp in diagnosis.get("proposed_experiments", []):
            exp_id = exp.get("experiment_id") or exp.get("related_pattern_id", "")
            if exp_id:
                _db_write(db.save_experiment, product_id, {
                    "experiment_id": exp_id,
                    "experiment_name": exp.get("hypothesis", exp_id)[:100],
                    "hypothesis": exp.get("hypothesis", ""),
                    "status": "proposed",
                    "metadata": {"proposed_in_week": week, "variable": exp.get("variable")},
                })

    # ─── Step 7: Pattern Promoter (deterministic) ───
    print("\nStep 7: Evaluating pattern promotions...")
    promotions = evaluate_promotions(product_id)

    # ─── Step 8: Strategy Alert Evaluation ───
    print("\nStep 8: Evaluating strategy alerts...")
    alert = _evaluate_strategy_alert(product_id, week, calculated, product_dir, growth_dir)

    # ─── Step 9: Growth Run Manifest ───
    print("\nStep 9: Writing growth_run_manifest.json...")
    run_manifest = {
        "product_id": product_id,
        "growth_run_id": f"GR-{week}",
        "related_marketing_run_id": week,
        "strategy_version_used": strategy_version,
        "metrics_source": "manual_json",
        "started_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat(),
        "status": "completed",
        "outputs_generated": [
            f for f in ["calculated_metrics.json", "performance_report.json",
                        "diagnosis.json", "optimization_actions.json"]
            if (growth_dir / f).exists()
        ],
        "persistent_artifacts_updated": [],
        "alert_generated": alert is not None,
        "decision_level": diagnosis.get("decision_level", "tactical") if diagnosis else "unknown",
        "approved_actions": None,
        "experiments_registered": exp_result.get("new_experiments_registered", []),
        "pattern_promotions": promotions,
    }
    if kb_updates:
        run_manifest["persistent_artifacts_updated"].append("knowledge_base_marketing.json")
    (growth_dir / "growth_run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=False))

    # ─── Step 10: Telegram Report ───
    print("\nStep 10: Sending Telegram report...")
    tg_msg = _format_telegram_report(product_id, week, strategy_version,
                                      perf_report, diagnosis, opt_actions,
                                      exp_result, promotions, alert)
    send_message(tg_msg)

    print(f"\n{'='*50}")
    print(f"Growth Intelligence {week} COMPLETE")
    print(f"{'='*50}")
    return True


def _run_interpreter(product_id, week, strategy_version, calculated, growth_dir):
    skill_md = (SKILLS_DIR / "metrics-interpreter" / "SKILL.md").read_text()
    model_path = PRODUCTS_DIR / product_id / "metrics_model.json"
    model = json.loads(model_path.read_text()) if model_path.exists() else {}

    ctx = (f"## calculated_metrics.json\n```json\n{json.dumps(calculated, indent=2)}\n```\n\n"
           f"## metrics_model.json\n```json\n{json.dumps(model, indent=2)}\n```")

    system = f"{skill_md}\n\nCONTEXT:\n{ctx}\n\nproduct_id: \"{product_id}\"\nrun_id: \"{week}\"\nstrategy_version_used: \"{strategy_version}\""
    user = f"Generate performance_report.json for {product_id} {week}. Output ONLY the JSON."

    try:
        text, usage = call_llm(INTERPRETER_MODEL, system, user, max_tokens=4096)
        parsed = extract_json_from_response(text)
        if parsed:
            (growth_dir / "performance_report.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
            print(f"  ✅ performance_report.json ({usage.get('output_tokens', '?')} tokens out)")
            return parsed
    except Exception as e:
        print(f"  ❌ Interpreter failed: {e}")
    return None


def _run_diagnosis(product_id, week, strategy_version, calculated, product_dir, growth_dir):
    skill_md = (SKILLS_DIR / "diagnosis-agent" / "SKILL.md").read_text()

    # Build context
    ctx_parts = [f"## calculated_metrics.json\n```json\n{json.dumps(calculated, indent=2)}\n```"]

    kb_path = product_dir / "knowledge_base_marketing.json"
    if kb_path.exists():
        ctx_parts.append(f"## knowledge_base_marketing.json\n```json\n{kb_path.read_text()}\n```")

    exp_path = product_dir / "experiments_log.json"
    if exp_path.exists():
        ctx_parts.append(f"## experiments_log.json\n```json\n{exp_path.read_text()}\n```")

    strat_dir = product_dir / "strategies" / strategy_version
    for f in ["buyer_persona.json", "brand_strategy.json"]:
        p = strat_dir / f
        if p.exists():
            ctx_parts.append(f"## {f}\n```json\n{p.read_text()}\n```")

    ctx = "\n\n".join(ctx_parts)

    # Compute next week for optimization_actions.for_run
    try:
        week_num = int(week.split("W")[1])
        year = int(week.split("-W")[0])
        next_week = f"{year}-W{week_num+1:02d}"
    except (ValueError, IndexError):
        next_week = week

    system = (f"{skill_md}\n\nCONTEXT:\n{ctx}\n\n"
              f"product_id: \"{product_id}\"\nrun_id: \"{week}\"\n"
              f"next_week (for optimization_actions.for_run): \"{next_week}\"\n"
              f"strategy_version_used: \"{strategy_version}\"")
    user = f"Generate diagnosis.json and optimization_actions.json for {product_id} {week}. Output BOTH as separate JSON blocks."

    try:
        text, usage = call_llm(DIAGNOSIS_MODEL, system, user, max_tokens=8192, temperature=0.3)
        print(f"  Tokens: {usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out")

        # Extract both JSON blocks
        import re
        blocks = re.findall(r"```(?:json)?\s*\n([\s\S]*?)```", text)
        diagnosis = None
        opt_actions = None

        for block in blocks:
            try:
                parsed = json.loads(block.strip())
                if "root_cause" in parsed:
                    diagnosis = parsed
                elif "actions" in parsed:
                    opt_actions = parsed
            except json.JSONDecodeError:
                continue

        if not diagnosis and not opt_actions:
            # Try single block
            parsed = extract_json_from_response(text)
            if parsed and "root_cause" in parsed:
                diagnosis = parsed

        if diagnosis:
            (growth_dir / "diagnosis.json").write_text(json.dumps(diagnosis, indent=2, ensure_ascii=False))
            print(f"  ✅ diagnosis.json")
        if opt_actions:
            (growth_dir / "optimization_actions.json").write_text(json.dumps(opt_actions, indent=2, ensure_ascii=False))
            print(f"  ✅ optimization_actions.json")

        if not diagnosis:
            (growth_dir / "debug_diagnosis_response.txt").write_text(text)

        return diagnosis, opt_actions

    except Exception as e:
        print(f"  ❌ Diagnosis failed: {e}")
        return None, None


def _run_learning_extractor(product_id, week, calculated, diagnosis, metrics_input, product_dir, growth_dir):
    skill_md = (SKILLS_DIR / "learning-extractor" / "SKILL.md").read_text()

    ctx_parts = [f"## calculated_metrics.json\n```json\n{json.dumps(calculated, indent=2)}\n```"]
    if diagnosis:
        ctx_parts.append(f"## diagnosis.json\n```json\n{json.dumps(diagnosis, indent=2)}\n```")

    content_used = metrics_input.get("content_used", {})
    if content_used:
        ctx_parts.append(f"## content_used\n```json\n{json.dumps(content_used, indent=2)}\n```")

    kb_path = product_dir / "knowledge_base_marketing.json"
    if kb_path.exists():
        ctx_parts.append(f"## knowledge_base_marketing.json\n```json\n{kb_path.read_text()}\n```")

    ctx = "\n\n".join(ctx_parts)
    system = f"{skill_md}\n\nCONTEXT:\n{ctx}\n\nproduct_id: \"{product_id}\"\nextracted_from_run: \"{week}\""
    user = f"Generate new_kb_entries.json for {product_id} {week}. Output ONLY the JSON."

    try:
        text, usage = call_llm(EXTRACTOR_MODEL, system, user, max_tokens=4096)
        parsed = extract_json_from_response(text)
        if parsed:
            (growth_dir / "new_kb_entries.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
            # Append to KB
            _append_to_kb(product_dir, parsed)
            print(f"  ✅ KB updated ({usage.get('output_tokens', '?')} tokens out)")
            return parsed
    except Exception as e:
        print(f"  ❌ Learning Extractor failed: {e}")
    return None


def _append_to_kb(product_dir, new_entries):
    """Append new patterns to knowledge_base_marketing.json (never overwrite)."""
    kb_path = product_dir / "knowledge_base_marketing.json"
    kb = json.loads(kb_path.read_text()) if kb_path.exists() else {
        "product_id": product_dir.name,
        "last_updated": None,
        "tactical_learnings": {"winning_patterns": [], "losing_patterns": []},
        "strategic_signals": [],
    }

    existing_ids = set()
    for cat in ["winning_patterns", "losing_patterns"]:
        for p in kb.get("tactical_learnings", {}).get(cat, []):
            existing_ids.add(p.get("pattern_id"))

    for p in new_entries.get("new_winning_patterns", []):
        if p.get("pattern_id") not in existing_ids:
            kb["tactical_learnings"]["winning_patterns"].append(p)

    for p in new_entries.get("new_losing_patterns", []):
        if p.get("pattern_id") not in existing_ids:
            kb["tactical_learnings"]["losing_patterns"].append(p)

    # Reinforce existing patterns
    for reinforcement in new_entries.get("existing_patterns_reinforced", []):
        pid = reinforcement.get("pattern_id")
        for cat in ["winning_patterns", "losing_patterns"]:
            for p in kb["tactical_learnings"][cat]:
                if p.get("pattern_id") == pid:
                    p["evidence_runs_count"] = p.get("evidence_runs_count", 0) + 1
                    p["last_confirmed_at"] = new_entries.get("extracted_from_run")

    kb["last_updated"] = new_entries.get("extracted_from_run")
    kb_path.write_text(json.dumps(kb, indent=2, ensure_ascii=False))


def _evaluate_strategy_alert(product_id, week, calculated, product_dir, growth_dir):
    """Evaluate if a strategy alert should be generated."""
    alerts = calculated.get("alerts", [])
    trends = calculated.get("trends", {})

    critical_signals = []
    for a in alerts:
        if a.get("severity") in ("warning", "critical"):
            critical_signals.append(f"{a['metric']}: {a['condition']}")

    if trends.get("cpa_3w") == "rising":
        critical_signals.append("CPA rising 3 consecutive weeks")
    if trends.get("roas_3w") == "falling":
        critical_signals.append("ROAS falling 3 consecutive weeks")

    if not critical_signals:
        return None

    # Check cooldown
    runs_dir = product_dir / "weekly_runs"
    if runs_dir.exists():
        for w_dir in sorted(runs_dir.iterdir(), reverse=True):
            alert_path = w_dir / "growth" / "strategy_alert.json"
            if alert_path.exists():
                prev_alert = json.loads(alert_path.read_text())
                realert_after = prev_alert.get("realert_allowed_after")
                if realert_after:
                    if datetime.now().isoformat() < realert_after:
                        print(f"  ⏳ Alert cooldown active until {realert_after}")
                        return None
                break  # Only check most recent alert

    alert = {
        "product_id": product_id,
        "alert_id": f"SA-{week}",
        "alert_type": "soft_invalid",
        "detected_at": week,
        "signals": critical_signals,
        "recommendation": "Revisar estrategia. Considerar re-ejecutar Strategy Workflow.",
        "urgency": "high" if len(critical_signals) >= 3 else "medium",
        "cooldown_days": ALERT_COOLDOWN_DAYS,
        "realert_allowed_after": (datetime.now() + timedelta(days=ALERT_COOLDOWN_DAYS)).isoformat(),
    }
    (growth_dir / "strategy_alert.json").write_text(json.dumps(alert, indent=2, ensure_ascii=False))
    print(f"  ⚠️ Strategy alert generated: {alert['alert_type']}")
    return alert


def _format_telegram_report(product_id, week, strategy_version,
                             perf_report, diagnosis, opt_actions,
                             exp_result, promotions, alert):
    lines = [
        f"📊 Growth Report — {week}",
        f"Producto: {product_id} | Strategy: {strategy_version}",
        "",
    ]

    # Metrics
    if perf_report:
        ms = perf_report.get("metrics_summary", {})
        lines += [
            "Métricas:",
            f"  CTR: {ms.get('ctr', '?')}%",
            f"  CPA: ${ms.get('cpa', '?')}",
            f"  Conversiones: {ms.get('conversions', '?')} | Revenue: ${ms.get('revenue', '?')}",
            f"  ROAS: {ms.get('roas', '?')}x | Spend: ${ms.get('spend', '?')}",
            f"  Health: {perf_report.get('overall_health', '?')}",
            "",
        ]
        interp = perf_report.get("interpretation", "")
        if interp:
            lines += [f"Interpretación: {interp}", ""]

    # Diagnosis
    if diagnosis:
        lines += [
            f"Diagnóstico: {diagnosis.get('root_cause', '?')}",
            f"  Nivel: {diagnosis.get('decision_level', '?').upper()} | Dominio: {diagnosis.get('problem_domain', '?')}",
            "",
        ]

    # Actions
    if opt_actions:
        actions = opt_actions.get("actions", [])
        if actions:
            lines.append("Acciones propuestas:")
            for a in actions:
                lines.append(f"  [{a.get('priority', '?').upper()}] {a.get('action', '?')}")
            lines.append("")

    # Experiments
    new_exps = exp_result.get("new_experiments_registered", [])
    if new_exps:
        lines.append(f"Experimentos nuevos: {', '.join(new_exps)}")

    # Promotions
    promo = promotions.get("promote_candidates", [])
    if promo:
        lines.append("Patterns para confirmar:")
        for p in promo:
            lines.append(f"  {p['pattern_id']}: {p['pattern']}")

    # Alert
    if alert:
        lines += [
            "",
            f"⚠️ ALERTA ESTRATÉGICA: {alert['alert_type']}",
            f"Señales: {', '.join(alert['signals'])}",
            f"Recomendación: {alert['recommendation']}",
        ]

    lines += ["", "/growth approve " + week, "/growth adjust " + week]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 growth_runner.py <product_id> <week>")
        sys.exit(1)
    run_growth(sys.argv[1], sys.argv[2])
