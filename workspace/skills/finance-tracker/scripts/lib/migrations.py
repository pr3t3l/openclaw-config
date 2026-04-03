"""Version migration system for Finance Tracker v2.

Reads VERSION file, runs sequential migrations, tracks in config.
Each migration is idempotent (safe to run twice).
"""

import importlib.util
from pathlib import Path

from . import config as C


MIGRATIONS_DIR = C.INSTALL_DIR / "migrations"


def get_current_version() -> str:
    """Read version from VERSION file."""
    version_file = C.SRC_DIR / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


def get_applied_migrations() -> list[str]:
    """Get list of applied migration names from config."""
    cfg = C._load_tracker_config()
    return cfg.get("migrations_applied", [])


def _discover_migrations() -> list[Path]:
    """Find all migration files in order."""
    if not MIGRATIONS_DIR.exists():
        return []
    files = sorted(MIGRATIONS_DIR.glob("*.py"))
    return [f for f in files if f.name != "__init__.py"]


def run_pending_migrations() -> dict:
    """Run any migrations not yet applied. Returns results."""
    applied = set(get_applied_migrations())
    all_migrations = _discover_migrations()
    pending = [m for m in all_migrations if m.stem not in applied]

    if not pending:
        return {"pending": 0, "applied": len(applied), "results": []}

    results = []
    newly_applied = list(applied)

    for mig_path in pending:
        name = mig_path.stem
        try:
            spec = importlib.util.spec_from_file_location(name, mig_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if hasattr(mod, "migrate"):
                mod.migrate()

            newly_applied.append(name)
            results.append({"migration": name, "status": "ok"})
        except Exception as e:
            results.append({"migration": name, "status": "error", "error": str(e)})
            break  # Stop on first failure

    # Save applied list
    cfg = C._load_tracker_config()
    cfg["migrations_applied"] = newly_applied
    C.save_tracker_config(cfg)

    return {
        "pending": len(pending),
        "applied": len(newly_applied),
        "ran": len(results),
        "results": results,
        "version": get_current_version(),
    }


def check_migrations() -> dict:
    """Check migration status without running them."""
    applied = get_applied_migrations()
    all_migrations = _discover_migrations()
    pending = [m.stem for m in all_migrations if m.stem not in set(applied)]

    return {
        "version": get_current_version(),
        "total_migrations": len(all_migrations),
        "applied": len(applied),
        "pending": pending,
        "needs_migration": len(pending) > 0,
    }
