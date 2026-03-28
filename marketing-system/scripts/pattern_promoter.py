#!/usr/bin/env python3
"""Pattern Promoter — deterministic script (NO LLM).

Evaluates promotion rules for KB patterns. PROPOSES changes, NEVER applies automatically.

Rules:
  tentative → confirmed: evidence_runs >= 3 AND sample_met AND contradictions < 20%
  confirmed → deprecated: contradictions > confirmations in last 3 weeks OR new strategy version

Usage:
  python3 pattern_promoter.py <product_id>
"""

import json
import sys
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")


def evaluate_promotions(product_id: str) -> dict:
    """Evaluate all patterns for promotion/deprecation candidates."""
    product_dir = PRODUCTS_DIR / product_id
    kb_path = product_dir / "knowledge_base_marketing.json"

    if not kb_path.exists():
        return {"promote_candidates": [], "deprecate_candidates": []}

    kb = json.loads(kb_path.read_text())
    promote_candidates = []
    deprecate_candidates = []

    # Check winning patterns for promotion tentative → confirmed
    for pattern in kb.get("tactical_learnings", {}).get("winning_patterns", []):
        if pattern.get("status") == "tentative":
            eligible, reason = _check_promote_eligible(pattern)
            if eligible:
                promote_candidates.append({
                    "pattern_id": pattern["pattern_id"],
                    "pattern": pattern["pattern"],
                    "evidence_runs": pattern.get("evidence_runs_count", 0),
                    "sample_met": pattern.get("minimum_sample_met", False),
                    "contradictions": len(pattern.get("contradictions", [])),
                    "reason": reason,
                })

    # Check confirmed patterns for deprecation
    for pattern in kb.get("tactical_learnings", {}).get("winning_patterns", []):
        if pattern.get("status") == "confirmed":
            should_deprecate, reason = _check_deprecate_eligible(pattern)
            if should_deprecate:
                deprecate_candidates.append({
                    "pattern_id": pattern["pattern_id"],
                    "pattern": pattern["pattern"],
                    "reason": reason,
                })

    # Same for losing patterns
    for pattern in kb.get("tactical_learnings", {}).get("losing_patterns", []):
        if pattern.get("status") == "tentative":
            eligible, reason = _check_promote_eligible(pattern)
            if eligible:
                promote_candidates.append({
                    "pattern_id": pattern["pattern_id"],
                    "pattern": pattern["pattern"],
                    "evidence_runs": pattern.get("evidence_runs_count", 0),
                    "reason": reason,
                })

    result = {
        "promote_candidates": promote_candidates,
        "deprecate_candidates": deprecate_candidates,
    }

    if promote_candidates or deprecate_candidates:
        print(f"📊 Pattern promotion: {len(promote_candidates)} promote, {len(deprecate_candidates)} deprecate candidates")
    else:
        print("📊 No pattern promotion candidates")

    return result


def apply_promotion(product_id: str, pattern_id: str, new_status: str) -> bool:
    """Apply a status change to a pattern (after human approval)."""
    product_dir = PRODUCTS_DIR / product_id
    kb_path = product_dir / "knowledge_base_marketing.json"
    kb = json.loads(kb_path.read_text())

    for category in ["winning_patterns", "losing_patterns"]:
        for pattern in kb.get("tactical_learnings", {}).get(category, []):
            if pattern.get("pattern_id") == pattern_id:
                old_status = pattern["status"]
                pattern["status"] = new_status
                pattern["last_confirmed_at"] = pattern.get("last_confirmed_at")
                kb_path.write_text(json.dumps(kb, indent=2, ensure_ascii=False))
                print(f"✅ {pattern_id}: {old_status} → {new_status}")
                return True

    print(f"❌ Pattern {pattern_id} not found")
    return False


def _check_promote_eligible(pattern: dict) -> tuple[bool, str]:
    """Check if a tentative pattern meets all promotion criteria."""
    runs = pattern.get("evidence_runs_count", 0)
    sample_met = pattern.get("minimum_sample_met", False)
    contradictions = len(pattern.get("contradictions", []))
    confirmations = runs  # approximation

    if runs < 3:
        return False, f"evidence_runs={runs} < 3"
    if not sample_met:
        return False, "minimum_sample not met"
    if confirmations > 0 and contradictions / max(confirmations, 1) >= 0.2:
        return False, f"contradictions ({contradictions}) >= 20% of confirmations ({confirmations})"

    return True, f"All criteria met: runs={runs}, sample_met={sample_met}, contradictions={contradictions}"


def _check_deprecate_eligible(pattern: dict) -> tuple[bool, str]:
    """Check if a confirmed pattern should be deprecated."""
    contradictions = len(pattern.get("contradictions", []))
    runs = pattern.get("evidence_runs_count", 0)

    # Contradictions > confirmations in recent data
    if contradictions > 0 and contradictions > runs * 0.5:
        return True, f"High contradiction rate: {contradictions} contradictions vs {runs} evidence runs"

    return False, "No deprecation criteria met"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pattern_promoter.py <product_id>")
        sys.exit(1)
    result = evaluate_promotions(sys.argv[1])
    print(json.dumps(result, indent=2))
