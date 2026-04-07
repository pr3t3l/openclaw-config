"""Codebase reconciler — scan git diff + file tree, map to original tasks.

See spec.md §10 (Re-Entry Protocol Step 1).
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FileStatus:
    """Status of a single file relative to original tasks."""
    path: str
    status: str  # created, modified, deleted, unchanged
    task_id: Optional[str] = None  # Which task was supposed to create/modify this


@dataclass
class ReconciliationReport:
    """Implementation status report — what exists vs what was planned."""
    files: list[FileStatus] = field(default_factory=list)
    tasks_completed: list[str] = field(default_factory=list)
    tasks_partial: list[str] = field(default_factory=list)
    tasks_not_started: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def total_files(self) -> int:
        return len(self.files)


def scan_codebase(project_root: str) -> dict:
    """Scan current codebase state: git diff and file tree.

    Returns:
        Dict with git_diff, file_tree, and modified_files.
    """
    result = {"git_diff": "", "file_tree": [], "modified_files": []}

    # Git diff
    try:
        diff = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            capture_output=True, text=True, timeout=30,
            cwd=project_root,
        )
        result["git_diff"] = diff.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        result["git_diff"] = "(git not available)"

    # File tree
    root = Path(project_root)
    if root.exists():
        result["file_tree"] = sorted(
            str(f.relative_to(root))
            for f in root.rglob("*")
            if f.is_file()
            and ".git" not in f.parts
            and "__pycache__" not in f.parts
            and ".pytest_cache" not in f.parts
        )

    # Modified files from git status
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=30,
            cwd=project_root,
        )
        for line in status.stdout.strip().split("\n"):
            if line.strip():
                result["modified_files"].append(line.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return result


def map_files_to_tasks(
    file_tree: list[str],
    tasks_content: str,
) -> dict[str, Optional[str]]:
    """Map existing files to the tasks that should have created them.

    Args:
        file_tree: List of file paths in the project.
        tasks_content: Content of tasks.md.

    Returns:
        Dict of file_path → task_id (or None if no task claims the file).
    """
    # Extract files_touched per task
    task_files: dict[str, list[str]] = {}
    current_task = None

    for line in tasks_content.split("\n"):
        task_match = re.match(r"###\s+(TASK-\d+)", line)
        if task_match:
            current_task = task_match.group(1)
            task_files[current_task] = []
        elif current_task and "files touched" in line.lower():
            # Extract file paths from the line
            files_part = line.split(":", 1)[1] if ":" in line else ""
            paths = [p.strip().strip("`") for p in files_part.split(",")]
            task_files[current_task].extend(p for p in paths if p)

    # Map actual files to tasks
    mapping: dict[str, Optional[str]] = {}
    for filepath in file_tree:
        mapped_task = None
        for task_id, expected_files in task_files.items():
            for expected in expected_files:
                if expected in filepath or filepath.endswith(expected):
                    mapped_task = task_id
                    break
            if mapped_task:
                break
        mapping[filepath] = mapped_task

    return mapping


def produce_status(
    file_mapping: dict[str, Optional[str]],
    tasks_content: str,
) -> ReconciliationReport:
    """Produce a reconciliation report.

    Args:
        file_mapping: Dict of file_path → task_id.
        tasks_content: Content of tasks.md.

    Returns:
        ReconciliationReport with task completion status.
    """
    # Get all task IDs
    all_tasks = re.findall(r"(TASK-\d+)", tasks_content)
    all_tasks = sorted(set(all_tasks))

    # Which tasks have files created
    tasks_with_files = set(tid for tid in file_mapping.values() if tid)

    files = [
        FileStatus(path=fp, status="created", task_id=tid)
        for fp, tid in file_mapping.items()
    ]

    # Classify tasks
    completed = sorted(tasks_with_files)
    not_started = sorted(set(all_tasks) - tasks_with_files)

    summary = (
        f"Reconciliation: {len(files)} files mapped, "
        f"{len(completed)} tasks with files, "
        f"{len(not_started)} tasks without files"
    )

    return ReconciliationReport(
        files=files,
        tasks_completed=completed,
        tasks_not_started=not_started,
        summary=summary,
    )
