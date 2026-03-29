#!/usr/bin/env python3
"""Verify parity between JSON files and PostgreSQL data.

Usage:
    python3 verify_db_parity.py <product_id>
    python3 verify_db_parity.py misterio-semanal
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")


def verify(product_id: str):
    product_dir = PRODUCTS_DIR / product_id
    issues = []
    checks = 0

    print(f"\n{'='*60}")
    print(f"PARITY CHECK — {product_id}")
    print(f"{'='*60}")

    # 1. Project
    checks += 1
    brief_path = product_dir / "product_brief.json"
    project = db.get_project(product_id)
    if brief_path.exists() and not project:
        issues.append("Project exists in JSON but NOT in DB")
    elif project:
        print(f"  [OK] Project: {project['project_name']}")
    else:
        print(f"  [SKIP] No project brief")

    # 2. Strategy versions
    strategies_dir = product_dir / "strategies"
    if strategies_dir.exists():
        json_versions = sorted([d.name for d in strategies_dir.iterdir()
                               if d.is_dir() and not d.name.startswith("_")])
        archived = sorted([d.name for d in strategies_dir.iterdir()
                          if d.is_dir() and d.name.startswith("_")])

        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT version, status FROM marketing.strategy_versions WHERE project_id = %s ORDER BY version",
                    (product_id,))
        db_versions = cur.fetchall()
        cur.close()
        db.close_conn(conn)

        checks += 1
        total_json = len(json_versions) + len(archived)
        total_db = len(db_versions)
        if total_json != total_db:
            issues.append(f"Strategy versions: {total_json} in JSON, {total_db} in DB")
        print(f"  [{'OK' if total_json == total_db else 'MISMATCH'}] Strategy versions: JSON={total_json}, DB={total_db}")

    # 3. Strategy outputs
    checks += 1
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM marketing.strategy_outputs WHERE project_id = %s", (product_id,))
    db_outputs = cur.fetchone()[0]
    cur.close()
    db.close_conn(conn)

    json_outputs = 0
    if strategies_dir.exists():
        for d in strategies_dir.iterdir():
            if not d.is_dir():
                continue
            for f in ["market_analysis.json", "buyer_persona.json", "brand_strategy.json",
                      "seo_architecture.json", "channel_strategy.json"]:
                if (d / f).exists():
                    json_outputs += 1
    if json_outputs != db_outputs:
        issues.append(f"Strategy outputs: {json_outputs} in JSON, {db_outputs} in DB")
    print(f"  [{'OK' if json_outputs == db_outputs else 'MISMATCH'}] Strategy outputs: JSON={json_outputs}, DB={db_outputs}")

    # 4. Buyer segments
    checks += 1
    db_segments = db.get_buyer_segments(product_id)
    json_segments = 0
    if strategies_dir.exists():
        for d in strategies_dir.iterdir():
            bp = d / "buyer_persona.json"
            if bp.exists():
                try:
                    data = json.loads(bp.read_text())
                    json_segments = max(json_segments, len(data.get("segments", [])))
                except (json.JSONDecodeError, KeyError):
                    pass
    if json_segments != len(db_segments):
        issues.append(f"Buyer segments: {json_segments} in latest JSON, {len(db_segments)} in DB")
    print(f"  [{'OK' if json_segments == len(db_segments) else 'MISMATCH'}] Buyer segments: JSON={json_segments}, DB={len(db_segments)}")

    # 5. Assets per week
    checks += 1
    runs_dir = product_dir / "weekly_runs"
    json_assets = 0
    if runs_dir.exists():
        for week_dir in runs_dir.iterdir():
            drafts = week_dir / "drafts"
            if drafts.exists():
                json_assets += sum(1 for f in drafts.iterdir()
                                  if f.suffix == ".json" and "debug" not in f.name
                                  and "quality_report" not in f.name and "image_manifest" not in f.name)

    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM marketing.assets WHERE project_id = %s", (product_id,))
    db_assets = cur.fetchone()[0]
    cur.close()
    db.close_conn(conn)
    # Note: DB may have more assets (individual scripts/ads) vs JSON (bundled files)
    print(f"  [INFO] Assets: JSON files={json_assets}, DB rows={db_assets} (DB stores individual assets)")

    # 6. Knowledge base
    checks += 1
    db_kb = db.get_kb(product_id)
    kb_path = product_dir / "knowledge_base_marketing.json"
    json_kb = 0
    if kb_path.exists():
        try:
            kb_data = json.loads(kb_path.read_text())
            for cat in ["winning_patterns", "losing_patterns"]:
                json_kb += len(kb_data.get("tactical_learnings", {}).get(cat, []))
        except (json.JSONDecodeError, KeyError):
            pass
    if json_kb != len(db_kb):
        issues.append(f"KB entries: {json_kb} in JSON, {len(db_kb)} in DB")
    print(f"  [{'OK' if json_kb == len(db_kb) else 'MISMATCH'}] KB entries: JSON={json_kb}, DB={len(db_kb)}")

    # 7. Experiments
    checks += 1
    db_exps = db.get_experiments(product_id)
    exp_path = product_dir / "experiments_log.json"
    json_exps = 0
    if exp_path.exists():
        try:
            json_exps = len(json.loads(exp_path.read_text()).get("experiments", []))
        except (json.JSONDecodeError, KeyError):
            pass
    if json_exps != len(db_exps):
        issues.append(f"Experiments: {json_exps} in JSON, {len(db_exps)} in DB")
    print(f"  [{'OK' if json_exps == len(db_exps) else 'MISMATCH'}] Experiments: JSON={json_exps}, DB={len(db_exps)}")

    # Summary
    print(f"\n{'='*60}")
    if issues:
        print(f"RESULT: {len(issues)} parity issues found ({checks} checks)")
        for i in issues:
            print(f"  - {i}")
    else:
        print(f"RESULT: All {checks} checks passed")
    print(f"{'='*60}")

    return len(issues) == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 verify_db_parity.py <product_id>")
        sys.exit(1)
    ok = verify(sys.argv[1])
    sys.exit(0 if ok else 1)
