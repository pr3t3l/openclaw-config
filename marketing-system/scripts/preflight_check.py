#!/usr/bin/env python3
"""Preflight checks before running any marketing system workflow.

Usage:
  python3 preflight_check.py <product_id> [--require-strategy]

Exit codes:
  0 = all checks pass
  1 = critical failure (cannot proceed)
  2 = warning (can proceed with caution)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")
LITELLM_URL = "http://127.0.0.1:4000"

REQUIRED_PRODUCT_FILES = [
    "product_brief.json",
]

STRATEGY_FILES = [
    "market_analysis.json",
    "buyer_persona.json",
    "brand_strategy.json",
    "seo_architecture.json",
    "channel_strategy.json",
    "strategy_manifest.json",
]


def check_product_dir(product_id: str) -> list[str]:
    """Check product directory exists with required files."""
    errors = []
    product_dir = PRODUCTS_DIR / product_id

    if not product_dir.exists():
        errors.append(f"Product directory not found: {product_dir}")
        return errors

    for f in REQUIRED_PRODUCT_FILES:
        path = product_dir / f
        if not path.exists():
            errors.append(f"Missing required file: {f}")
            continue
        # Validate JSON
        try:
            data = json.loads(path.read_text())
            if f == "product_brief.json":
                for field in ["product_id", "product_name", "price", "language"]:
                    if field not in data:
                        errors.append(f"product_brief.json missing field: {field}")
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in {f}: {e}")

    # Check writable
    if not os.access(str(product_dir), os.W_OK):
        errors.append(f"No write permission: {product_dir}")

    return errors


def check_strategy(product_id: str) -> list[str]:
    """Check that a valid, approved strategy exists."""
    errors = []
    product_dir = PRODUCTS_DIR / product_id
    manifest_path = product_dir / "product_manifest.json"

    if not manifest_path.exists():
        errors.append("No product_manifest.json — no strategy has been generated yet")
        return errors

    manifest = json.loads(manifest_path.read_text())
    status = manifest.get("strategy_status")
    validity = manifest.get("strategy_validity")
    version = manifest.get("active_strategy_version")

    if status != "approved":
        errors.append(f"Strategy not approved (status: {status})")

    if validity == "hard_invalid":
        errors.append("Strategy is hard_invalid — must re-generate before marketing can run")
    elif validity == "soft_invalid":
        errors.append("WARNING: Strategy is soft_invalid — consider re-generating")

    if not version:
        errors.append("No active_strategy_version set in product_manifest")
        return errors

    # Check all strategy files exist
    strategy_dir = product_dir / "strategies" / version
    if not strategy_dir.exists():
        errors.append(f"Strategy directory not found: strategies/{version}/")
        return errors

    for f in STRATEGY_FILES:
        if not (strategy_dir / f).exists():
            errors.append(f"Missing strategy file: strategies/{version}/{f}")

    return errors


def check_litellm() -> list[str]:
    """Check LiteLLM proxy is accessible."""
    errors = []
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5", f"{LITELLM_URL}/health"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            errors.append("LiteLLM proxy unreachable")
    except Exception as e:
        errors.append(f"LiteLLM check failed: {e}")
    return errors


def check_telegram() -> list[str]:
    """Check Telegram bot is accessible."""
    errors = []
    try:
        from telegram_sender import _load_bot_token
        token = _load_bot_token()
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5",
             f"https://api.telegram.org/bot{token}/getMe"],
            capture_output=True, text=True, timeout=10
        )
        resp = json.loads(result.stdout)
        if not resp.get("ok"):
            errors.append("Telegram bot token invalid or bot unreachable")
    except Exception as e:
        errors.append(f"Telegram check failed: {e}")
    return errors


def check_subdirs(product_id: str) -> list[str]:
    """Check required subdirectories exist."""
    errors = []
    product_dir = PRODUCTS_DIR / product_id
    for subdir in ["strategies", "weekly_runs", "runtime"]:
        if not (product_dir / subdir).exists():
            errors.append(f"Missing subdirectory: {subdir}/")
    return errors


def run_preflight(product_id: str, require_strategy: bool = False) -> dict:
    """Run all preflight checks. Returns {passed, errors, warnings}."""
    all_errors = []
    all_warnings = []

    # 1. Product directory
    errs = check_product_dir(product_id)
    all_errors.extend(errs)

    # 2. Subdirectories
    errs = check_subdirs(product_id)
    all_errors.extend(errs)

    # 3. LiteLLM
    errs = check_litellm()
    all_errors.extend(errs)

    # 4. Telegram
    errs = check_telegram()
    all_warnings.extend(errs)  # Telegram failure is non-blocking

    # 5. Strategy (only if required)
    if require_strategy:
        errs = check_strategy(product_id)
        # Separate hard errors from warnings
        for e in errs:
            if e.startswith("WARNING:"):
                all_warnings.append(e)
            else:
                all_errors.append(e)

    passed = len(all_errors) == 0

    return {
        "passed": passed,
        "product_id": product_id,
        "require_strategy": require_strategy,
        "errors": all_errors,
        "warnings": all_warnings,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 preflight_check.py <product_id> [--require-strategy]")
        sys.exit(1)

    product_id = sys.argv[1]
    require_strategy = "--require-strategy" in sys.argv

    # Add scripts dir to path for imports
    sys.path.insert(0, str(Path(__file__).parent))

    result = run_preflight(product_id, require_strategy)

    # Print results
    print(f"\n{'='*50}")
    print(f"PREFLIGHT CHECK — {product_id}")
    print(f"{'='*50}")

    if result["errors"]:
        print(f"\n❌ ERRORS ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"  - {e}")

    if result["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"  - {w}")

    if result["passed"]:
        print(f"\n✅ All checks passed. Ready to proceed.")
    else:
        print(f"\n🛑 Preflight FAILED. Fix errors before proceeding.")

    # Also output JSON for programmatic use
    print(f"\n{json.dumps(result, indent=2)}")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
