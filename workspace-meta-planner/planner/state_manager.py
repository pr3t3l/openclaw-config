"""State manager for SDD Planner runs.

Handles create/load/save/validate of planner_state.json.
State is persisted per-run in planner_runs/{run_id}/.
See spec.md §5 (State Persistence).
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jsonschema

SCHEMA_VERSION = "1.0.0"
PLANNER_RUNS_DIR = "planner_runs"
DEFAULT_LOCK_TTL_SECONDS = 300  # 5 minutes


class RunLockedException(Exception):
    """Raised when a run is already locked by another process."""

    def __init__(self, run_id: str, locked_by: str, locked_until: str) -> None:
        self.run_id = run_id
        self.locked_by = locked_by
        self.locked_until = locked_until
        super().__init__(
            f"Run {run_id} is locked by '{locked_by}' until {locked_until}"
        )


class ProjectAdmissionError(Exception):
    """Raised when a project already has an active run."""

    def __init__(self, project_id: str, existing_run_id: str) -> None:
        self.project_id = project_id
        self.existing_run_id = existing_run_id
        super().__init__(
            f"Project '{project_id}' already has an active run: {existing_run_id}"
        )

_schema_path = Path(__file__).parent / "schemas" / "planner_state_schema.json"
_schema_cache: Optional[dict] = None


def _load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        with open(_schema_path) as f:
            _schema_cache = json.load(f)
    return _schema_cache


def _state_path(project_root: str, run_id: str) -> Path:
    return Path(project_root) / PLANNER_RUNS_DIR / run_id / "planner_state.json"


def _ensure_run_dirs(project_root: str, run_id: str) -> Path:
    """Create run directory structure: planner_runs/{run_id}/{subdirs}."""
    run_dir = Path(project_root) / PLANNER_RUNS_DIR / run_id
    for subdir in ["drafts", "audits", "decision_logs", "history_archive", "output"]:
        (run_dir / subdir).mkdir(parents=True, exist_ok=True)
    return run_dir


def _next_run_id(project_root: str) -> str:
    """Generate next run ID: RUN-YYYYMMDD-NNN."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    runs_dir = Path(project_root) / PLANNER_RUNS_DIR
    if not runs_dir.exists():
        return f"RUN-{today}-001"
    existing = [
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and d.name.startswith(f"RUN-{today}-")
    ]
    if not existing:
        return f"RUN-{today}-001"
    max_seq = max(int(name.split("-")[-1]) for name in existing)
    return f"RUN-{today}-{max_seq + 1:03d}"


def validate(state: dict) -> list[str]:
    """Validate state against JSON schema. Returns list of errors (empty = valid)."""
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(state)]


def create_run(
    project_root: str,
    project_id: str,
    documents_pending: list[str],
    run_id: Optional[str] = None,
) -> dict:
    """Create a new planner run. Returns the initial state dict.

    Args:
        project_root: Absolute path to the project root.
        project_id: Project identifier for admission control.
        documents_pending: List of document names to produce.
        run_id: Optional explicit run ID; auto-generated if None.

    Returns:
        The initial planner state dict (already saved to disk).
    """
    check_project_admission(project_root, project_id)

    if run_id is None:
        run_id = _next_run_id(project_root)

    now = datetime.now(timezone.utc).isoformat()
    state = {
        "run_id": run_id,
        "project_id": project_id,
        "run_status": "active",
        "locked_by": None,
        "locked_until": None,
        "state_version": 1,
        "schema_version": SCHEMA_VERSION,
        "current_phase": "0",
        "current_document": None,
        "last_checkpoint": "Run created",
        "documents_completed": [],
        "documents_pending": documents_pending,
        "decision_logs": {},
        "entity_maps": {},
        "cost": {
            "total_usd": 0.0,
            "by_model": {},
            "by_phase": {},
            "by_document": {},
        },
        "created_at": now,
        "updated_at": now,
    }

    errors = validate(state)
    if errors:
        raise ValueError(f"Invalid initial state: {errors}")

    _ensure_run_dirs(project_root, run_id)
    _write_state(project_root, run_id, state)
    return state


def load(project_root: str, run_id: str) -> dict:
    """Load and validate planner_state.json for a run.

    Raises:
        FileNotFoundError: If state file doesn't exist.
        ValueError: If state fails schema validation.
    """
    path = _state_path(project_root, run_id)
    if not path.exists():
        raise FileNotFoundError(f"No state file at {path}")

    with open(path) as f:
        state = json.load(f)

    errors = validate(state)
    if errors:
        raise ValueError(f"State validation failed for {run_id}: {errors}")

    return state


def save(project_root: str, state: dict) -> dict:
    """Save state with incremented state_version.

    Args:
        project_root: Absolute path to the project root.
        state: Current state dict (will be mutated with new version + timestamp).

    Returns:
        The updated state dict.

    Raises:
        ValueError: If state fails validation after update.
    """
    state["state_version"] += 1
    state["updated_at"] = datetime.now(timezone.utc).isoformat()

    errors = validate(state)
    if errors:
        raise ValueError(f"State validation failed before save: {errors}")

    _write_state(project_root, state["run_id"], state)
    return state


def _write_state(project_root: str, run_id: str, state: dict) -> None:
    """Write state to disk atomically (write to temp, then rename)."""
    path = _state_path(project_root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)


def check_project_admission(project_root: str, project_id: str) -> None:
    """Raise ProjectAdmissionError if project already has an active run.

    Per spec §4: one active Planner run at a time per project.
    """
    existing = find_active_run(project_root, project_id)
    if existing is not None:
        raise ProjectAdmissionError(project_id, existing)


def acquire_lock(
    project_root: str,
    state: dict,
    locked_by: str = "planner_orchestrator",
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
) -> dict:
    """Acquire an exclusive lock on a run.

    Args:
        project_root: Project root path.
        state: Current state dict.
        locked_by: Identifier of the process acquiring the lock.
        ttl_seconds: Lock time-to-live in seconds.

    Returns:
        Updated state with lock acquired.

    Raises:
        RunLockedException: If the run is already locked by another process
            and the lock has not expired.
    """
    now = datetime.now(timezone.utc)

    if state["locked_by"] is not None:
        lock_until = datetime.fromisoformat(state["locked_until"])
        if lock_until > now and state["locked_by"] != locked_by:
            raise RunLockedException(
                state["run_id"], state["locked_by"], state["locked_until"]
            )
        # Lock expired or same owner — reclaim

    state["locked_by"] = locked_by
    state["locked_until"] = (now + timedelta(seconds=ttl_seconds)).isoformat()
    return save(project_root, state)


def release_lock(project_root: str, state: dict) -> dict:
    """Release the lock on a run."""
    state["locked_by"] = None
    state["locked_until"] = None
    return save(project_root, state)


def renew_lock(
    project_root: str,
    state: dict,
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
) -> dict:
    """Renew an existing lock for long operations.

    Raises:
        RunLockedException: If the lock is held by a different process.
    """
    if state["locked_by"] is None:
        raise RunLockedException(state["run_id"], "none", "none")

    now = datetime.now(timezone.utc)
    state["locked_until"] = (now + timedelta(seconds=ttl_seconds)).isoformat()
    return save(project_root, state)


def list_runs(project_root: str) -> list[dict]:
    """List all runs with basic info (run_id, status, project_id)."""
    runs_dir = Path(project_root) / PLANNER_RUNS_DIR
    if not runs_dir.exists():
        return []
    results = []
    for d in sorted(runs_dir.iterdir()):
        state_file = d / "planner_state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
            results.append({
                "run_id": state.get("run_id"),
                "run_status": state.get("run_status"),
                "project_id": state.get("project_id"),
                "current_phase": state.get("current_phase"),
                "cost_total": state.get("cost", {}).get("total_usd", 0),
            })
    return results


def find_active_run(project_root: str, project_id: str) -> Optional[str]:
    """Find an active run for a given project. Returns run_id or None."""
    for run in list_runs(project_root):
        if run["project_id"] == project_id and run["run_status"] in ("active", "paused", "degraded"):
            return run["run_id"]
    return None
