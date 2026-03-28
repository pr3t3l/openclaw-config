"""Rollback executor — atomic staging and rollback for artifacts."""

import json
import shutil
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")


def stage_backup(product_id: str, files_to_backup: list[Path], run_id: str = "") -> Path:
    """Copy current state to staging before writing new artifacts."""
    staging_dir = PRODUCTS_DIR / product_id / "runtime" / "staging" / (run_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    staging_dir.mkdir(parents=True, exist_ok=True)

    for f in files_to_backup:
        if f.exists():
            dest = staging_dir / f.name
            shutil.copy2(f, dest)

    # Write staging metadata
    meta = {
        "staged_at": datetime.now().isoformat(),
        "product_id": product_id,
        "run_id": run_id,
        "files": [str(f) for f in files_to_backup if f.exists()],
    }
    (staging_dir / "_staging_meta.json").write_text(json.dumps(meta, indent=2))

    return staging_dir


def rollback(product_id: str, staging_dir: Path) -> list[str]:
    """Restore files from staging. Returns list of restored files."""
    restored = []
    meta_path = staging_dir / "_staging_meta.json"
    if not meta_path.exists():
        return restored

    meta = json.loads(meta_path.read_text())
    for original_path_str in meta.get("files", []):
        original_path = Path(original_path_str)
        backup_path = staging_dir / original_path.name
        if backup_path.exists():
            shutil.copy2(backup_path, original_path)
            restored.append(str(original_path))

    # Log rollback
    log_path = PRODUCTS_DIR / product_id / "runtime" / "invalidation_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    log.append({
        "type": "rollback",
        "timestamp": datetime.now().isoformat(),
        "staging_dir": str(staging_dir),
        "files_restored": restored,
    })
    log_path.write_text(json.dumps(log, indent=2))

    return restored


def cleanup_staging(staging_dir: Path):
    """Remove staging directory after successful run."""
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
