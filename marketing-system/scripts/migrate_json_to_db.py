"""
Migrate JSON files from ~/.openclaw/products/misterio-semanal/ to PostgreSQL.
Uses db.py wrapper. Idempotent — safe to run multiple times.
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

# Ensure we can import db.py from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

PRODUCT_DIR = Path.home() / ".openclaw" / "products" / "misterio-semanal"

# Map iso week string "2026-W14" to a Monday date
def week_to_date(iso_week: str) -> date:
    return datetime.strptime(iso_week + "-1", "%G-W%V-%u").date()


def load_json(path: Path) -> dict | None:
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return None
    with open(path) as f:
        return json.load(f)


# =========================================================================
# 1. Project + Product Catalog from product_brief.json
# =========================================================================
def migrate_project():
    print("\n=== 1. Project + Product Catalog ===")
    brief = load_json(PRODUCT_DIR / "product_brief.json")
    if not brief:
        return

    p = db.upsert_project(
        project_id=brief["product_id"],
        project_name=brief["product_name"],
        project_type="digital_experience",
        description=brief.get("description"),
        website_url=brief.get("platform_url"),
        config={
            "language": brief.get("language"),
            "country": brief.get("country"),
            "monthly_budget": brief.get("monthly_marketing_budget"),
            "billing": brief.get("billing"),
        },
    )
    print(f"  [OK] project: {p['project_id']}")

    pid = db.upsert_product(
        project_id=brief["product_id"],
        sku="caso-semanal-base",
        product_name=brief["product_name"],
        price=brief.get("price", 19.99),
        description=brief.get("description"),
        currency=brief.get("currency", "USD"),
        category="digital_experience",
    )
    print(f"  [OK] product_catalog id={pid}")


# =========================================================================
# 2. Strategy versions + outputs + buyer segments
# =========================================================================
def migrate_strategy(version_num: int, strategy_dir: Path, status_override: str = None):
    print(f"\n=== 2. Strategy v{version_num} from {strategy_dir.name} ===")
    manifest = load_json(strategy_dir / "strategy_manifest.json")
    if not manifest:
        return

    project_id = manifest["product_id"]
    st = manifest.get("status", "draft")
    if status_override:
        st = status_override

    sv = db.create_strategy_version(
        project_id, version_num,
        status=st if st != "approved" else "approved",
        description=f"Strategy {manifest.get('strategy_version', f'v{version_num}')} — {manifest.get('created_by_workflow', 'unknown')}",
    )
    # If approved, set approved status properly
    if st == "approved":
        db.approve_strategy_version(project_id, version_num)
    print(f"  [OK] strategy_version: v{version_num} status={st}")

    # Strategy outputs
    output_types = ["market_analysis", "buyer_persona", "brand_strategy", "seo_architecture", "channel_strategy"]
    for otype in output_types:
        filename = manifest.get("outputs", {}).get(otype)
        if not filename:
            continue
        data = load_json(strategy_dir / filename)
        if not data:
            continue

        # For buyer_persona, extract segments separately
        if otype == "buyer_persona":
            migrate_buyer_segments(project_id, version_num, data)

        so_id = db.save_strategy_output(
            project_id, version_num, otype, data,
            title=otype.replace("_", " ").title(),
        )
        print(f"  [OK] strategy_output: {otype} id={so_id}")


def migrate_buyer_segments(project_id: str, version: int, persona_data: dict):
    segments = persona_data.get("segments", [])
    for seg in segments:
        pain_points = seg.get("pain_points", [])
        # Build messaging from buying_triggers + purchase_barriers
        messaging = {
            "buying_triggers": seg.get("buying_triggers", []),
            "purchase_barriers": seg.get("purchase_barriers", []),
            "preferred_channels": seg.get("preferred_channels", []),
        }
        profile = {
            "avatar": seg.get("avatar", {}),
            "motivation": seg.get("motivation", ""),
        }

        bs_id = db.upsert_buyer_segment(
            project_id=project_id,
            segment_id=seg["segment_id"],
            segment_name=seg["segment_name"],
            priority=seg.get("priority", "secondary"),
            use_case=seg.get("use_case", ""),
            profile=profile,
            version=version,
            pain_points=pain_points,
            messaging=messaging,
        )
        print(f"  [OK] buyer_segment: {seg['segment_id']} id={bs_id}")


# =========================================================================
# 3. Weekly runs → campaigns + campaign_runs + assets
# =========================================================================
def migrate_weekly_runs():
    print("\n=== 3. Weekly Runs ===")
    project_id = "misterio-semanal"
    weekly_dir = PRODUCT_DIR / "weekly_runs"
    if not weekly_dir.exists():
        print("  [SKIP] weekly_runs/ not found")
        return

    # Create a single "weekly_product" campaign for all runs
    campaign_db_id = db.create_campaign(
        project_id=project_id,
        campaign_id="weekly-mystery-cases",
        campaign_name="Weekly Mystery Cases — Declassified",
        campaign_type="weekly_product",
        status="active",
    )
    print(f"  [OK] campaign: weekly-mystery-cases (db id={campaign_db_id})")

    for week_dir in sorted(weekly_dir.iterdir()):
        if not week_dir.is_dir():
            continue
        week_id = week_dir.name  # e.g. "2026-W14"
        manifest = load_json(week_dir / "run_manifest.json")
        if not manifest:
            print(f"  [SKIP] {week_id}: no run_manifest.json")
            continue

        wsd = week_to_date(week_id)

        # Map run status
        status_map = {
            "completed": "completed",
            "completed_with_override": "completed",
            "awaiting_gate_M1": "review",
            "awaiting_gate_M2": "review",
            "in_progress": "generating",
        }
        run_status = status_map.get(manifest.get("status", "planned"), "planned")

        # Case brief for theme
        case_brief = load_json(week_dir / "weekly_case_brief.json")
        theme = case_brief.get("case_name", week_id) if case_brief else week_id

        run_id = db.create_run(
            campaign_id=campaign_db_id,
            project_id=project_id,
            week_start_date=wsd,
            status=run_status,
            theme=theme,
            config={
                "strategy_version_used": manifest.get("strategy_version_used"),
                "cost_usd": manifest.get("cost_usd", 0),
                "gates": manifest.get("gates", {}),
            },
        )
        print(f"  [OK] campaign_run: {week_id} → id={run_id} status={run_status}")

        # Migrate drafts as assets
        drafts_dir = week_dir / "drafts"
        if drafts_dir.exists():
            migrate_drafts(project_id, campaign_db_id, run_id, week_id, wsd, drafts_dir)

        # Migrate growth analysis if present
        growth_dir = week_dir / "growth"
        if growth_dir.exists():
            migrate_growth(project_id, campaign_db_id, wsd, growth_dir)


def migrate_drafts(project_id, campaign_db_id, run_id, week_id, wsd, drafts_dir):
    # Map draft files to asset types
    draft_map = {
        "reels_scripts_draft.json": ("reel_script", "tiktok"),
        "meta_ads_copy_draft.json": ("meta_ad", "meta_ads"),
        "email_sequence_draft.json": ("email", "email"),
        "publishing_calendar_draft.json": ("calendar", None),
    }

    for filename, (asset_type, platform) in draft_map.items():
        data = load_json(drafts_dir / filename)
        if not data:
            continue

        creative_id = f"{project_id}/{week_id}/{asset_type}"
        aid = db.save_asset(
            run_id=run_id,
            project_id=project_id,
            campaign_id=campaign_db_id,
            creative_id=creative_id,
            asset_type=asset_type,
            content=data,
            platform=platform,
            title=f"{asset_type.replace('_', ' ').title()} — {week_id}",
            status="draft" if data.get("status", "draft") == "draft" else "approved",
            week_start_date=wsd,
            metadata={"source_file": filename, "kb_patterns_used": data.get("kb_patterns_used", [])},
        )
        print(f"    [OK] asset: {creative_id} id={aid}")

    # Quality report as a separate asset
    qr = load_json(drafts_dir / "quality_report.json")
    if qr:
        qr_id = db.save_asset(
            run_id=run_id,
            project_id=project_id,
            campaign_id=campaign_db_id,
            creative_id=f"{project_id}/{week_id}/quality_report",
            asset_type="report",
            content=qr,
            title=f"Quality Report — {week_id}",
            status="approved" if qr.get("overall_status") == "pass" else "draft",
            week_start_date=wsd,
        )
        print(f"    [OK] asset: quality_report id={qr_id}")


# =========================================================================
# 4. Growth analyses
# =========================================================================
def migrate_growth(project_id, campaign_db_id, wsd, growth_dir):
    diagnosis = load_json(growth_dir / "diagnosis.json")
    calc_metrics = load_json(growth_dir / "calculated_metrics.json")
    perf_report = load_json(growth_dir / "performance_report.json")
    optimization = load_json(growth_dir / "optimization_actions.json")

    if diagnosis:
        results = {
            "root_cause": diagnosis.get("root_cause"),
            "confidence": diagnosis.get("confidence"),
            "reasoning": diagnosis.get("reasoning"),
            "problem_domain": diagnosis.get("problem_domain"),
            "evidence": diagnosis.get("evidence", []),
        }
        recommendations = []
        if optimization:
            recommendations = optimization.get("actions", optimization.get("optimization_actions", []))
            if not isinstance(recommendations, list):
                recommendations = [recommendations]

        ga_id = db.save_growth_analysis(
            project_id=project_id,
            campaign_id=campaign_db_id,
            week_start_date=wsd,
            results_dict={
                "diagnosis": results,
                "calculated_metrics": calc_metrics or {},
                "performance_report": perf_report or {},
            },
            recommendations=recommendations,
        )
        print(f"    [OK] growth_analysis id={ga_id}")


# =========================================================================
# 5. Knowledge base
# =========================================================================
def migrate_knowledge_base():
    print("\n=== 4. Knowledge Base ===")
    kb_data = load_json(PRODUCT_DIR / "knowledge_base_marketing.json")
    if not kb_data:
        return

    project_id = kb_data["product_id"]
    count = 0

    for category, patterns in kb_data.get("tactical_learnings", {}).items():
        for p in patterns:
            kb_id = db.add_kb_entry(project_id, {
                "pattern_id": p["pattern_id"],
                "category": category,
                "title": p["pattern"][:200],
                "description": p["pattern"],
                "evidence": [{"text": p.get("evidence", ""), "runs": p.get("evidence_runs_count", 0)}],
                "status": "active" if p.get("status") == "tentative" else p.get("status", "active"),
                "confidence": {"high": 0.9, "medium": 0.7, "low": 0.4}.get(p.get("confidence", "low"), 0.5),
                "metadata": {
                    "last_confirmed_at": p.get("last_confirmed_at"),
                    "contradictions": p.get("contradictions", []),
                    "minimum_sample_met": p.get("minimum_sample_met"),
                },
            })
            print(f"  [OK] kb: {p['pattern_id']} id={kb_id}")
            count += 1

    print(f"  Total: {count} KB entries migrated")


# =========================================================================
# 6. Experiments
# =========================================================================
def migrate_experiments():
    print("\n=== 5. Experiments ===")
    exp_data = load_json(PRODUCT_DIR / "experiments_log.json")
    if not exp_data:
        return

    project_id = exp_data["product_id"]
    for e in exp_data.get("experiments", []):
        exp_id = db.save_experiment(project_id, {
            "experiment_id": e["experiment_id"],
            "experiment_name": e.get("hypothesis", "")[:100],
            "hypothesis": e.get("hypothesis"),
            "status": e.get("status", "planned"),
            "variants": [
                {"name": "A", "description": e.get("variant_a", "")},
                {"name": "B", "description": e.get("variant_b", "")},
            ],
            "results": {
                "result": e.get("result"),
                "decision": e.get("decision"),
            } if e.get("result") else {},
            "conclusion": e.get("decision"),
            "metadata": {
                "proposed_by": e.get("proposed_by"),
                "proposed_at": e.get("proposed_at"),
                "variable": e.get("variable"),
                "success_metric": e.get("success_metric"),
                "success_threshold": e.get("success_threshold"),
                "sample_size_target": e.get("sample_size_target"),
                "min_duration_weeks": e.get("min_duration_weeks"),
                "related_pattern_id": e.get("related_pattern_id"),
                "notes": e.get("notes"),
            },
        })
        print(f"  [OK] experiment: {e['experiment_id']} id={exp_id}")


# =========================================================================
# Main
# =========================================================================
def main():
    print("=" * 60)
    print("Migration: JSON → PostgreSQL (marketing schema)")
    print(f"Source: {PRODUCT_DIR}")
    print("=" * 60)

    migrate_project()
    migrate_strategy(1, PRODUCT_DIR / "strategies" / "_archived_v1_baseline", status_override="superseded")
    migrate_strategy(2, PRODUCT_DIR / "strategies" / "v2")
    migrate_weekly_runs()
    migrate_knowledge_base()
    migrate_experiments()

    # Final verification
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    conn = db.get_conn()
    cur = conn.cursor()
    tables = [
        "projects", "strategy_versions", "strategy_outputs", "buyer_segments",
        "product_catalog", "campaigns", "campaign_runs", "assets",
        "growth_analyses", "knowledge_base", "experiments",
    ]
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM marketing.{t}")
        count = cur.fetchone()[0]
        print(f"  marketing.{t}: {count} rows")
    cur.close()
    db.close_conn(conn)

    print("\n=== Migration complete ===")


if __name__ == "__main__":
    main()
