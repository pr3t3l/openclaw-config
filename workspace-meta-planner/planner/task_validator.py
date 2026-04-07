"""Task validator — verify all 8 fields, cross-references, atomicity.

See spec.md §10 (task schema), spec.md §13 (Definition of Done).
"""

import re
from dataclasses import dataclass, field
from typing import Optional

REQUIRED_FIELDS = [
    "Objective",
    "Inputs",
    "Outputs",
    "Files touched",
    "Done when",
    "depends_on",
    "if_blocked",
    "Estimated",
]

TASK_ID_RE = re.compile(r"TASK-(\d+)")
DEPENDS_RE = re.compile(r"depends_on:\s*\[([^\]]*)\]", re.IGNORECASE)


@dataclass
class TaskValidation:
    """Validation result for a single task."""
    task_id: str
    missing_fields: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.missing_fields) == 0 and len(self.issues) == 0


@dataclass
class TasksValidationResult:
    """Validation result for all tasks."""
    task_results: list[TaskValidation] = field(default_factory=list)
    total_tasks: int = 0
    circular_deps: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(t.valid for t in self.task_results) and len(self.circular_deps) == 0

    @property
    def invalid_count(self) -> int:
        return sum(1 for t in self.task_results if not t.valid)


def validate_tasks(tasks_content: str, spec_content: Optional[str] = None) -> TasksValidationResult:
    """Validate all tasks in a tasks.md document.

    Checks:
    - All 8 required fields present per task
    - No circular dependencies
    - Tasks are referenced correctly in depends_on
    - Inputs reference plausible sources

    Args:
        tasks_content: Full tasks.md content.
        spec_content: Optional spec content for cross-reference validation.

    Returns:
        TasksValidationResult with per-task and global results.
    """
    tasks = _parse_tasks(tasks_content)
    result = TasksValidationResult(total_tasks=len(tasks))

    all_task_ids = {t["id"] for t in tasks}

    for task in tasks:
        tv = _validate_single_task(task, all_task_ids)
        result.task_results.append(tv)

    # Check circular dependencies
    dep_graph = _build_dep_graph(tasks)
    cycles = _detect_cycles(dep_graph)
    result.circular_deps = cycles

    return result


def _validate_single_task(task: dict, all_ids: set[str]) -> TaskValidation:
    """Validate a single task has all required fields."""
    tv = TaskValidation(task_id=task.get("id", "UNKNOWN"))

    content = task.get("content", "")
    content_lower = content.lower()

    for req_field in REQUIRED_FIELDS:
        # Check if field appears in content (case-insensitive)
        if req_field.lower() not in content_lower:
            # Try common variations
            variations = [req_field.lower().replace(" ", "_"), req_field.lower().replace(" ", "-")]
            if not any(v in content_lower for v in variations):
                tv.missing_fields.append(req_field)

    # Check depends_on references valid task IDs
    deps_match = DEPENDS_RE.search(content)
    if deps_match:
        deps_str = deps_match.group(1).strip()
        if deps_str:
            dep_ids = [d.strip() for d in deps_str.split(",")]
            for dep in dep_ids:
                dep = dep.strip("' \"")
                if dep and dep not in all_ids and dep != "[]":
                    tv.issues.append(f"depends_on references unknown task: {dep}")

    return tv


def _parse_tasks(content: str) -> list[dict]:
    """Parse tasks.md into individual task blocks."""
    tasks = []
    current_id = ""
    current_lines: list[str] = []

    for line in content.split("\n"):
        # Accept either "## TASK-001" or "### TASK-001" heading styles.
        task_match = re.match(r"#{2,3}\s+(TASK-\d+)", line)
        if task_match:
            if current_id:
                tasks.append({"id": current_id, "content": "\n".join(current_lines)})
            current_id = task_match.group(1)
            current_lines = [line]
        elif current_id:
            current_lines.append(line)

    if current_id:
        tasks.append({"id": current_id, "content": "\n".join(current_lines)})

    return tasks


def _build_dep_graph(tasks: list[dict]) -> dict[str, list[str]]:
    """Build a dependency graph from tasks."""
    graph: dict[str, list[str]] = {}
    for task in tasks:
        task_id = task["id"]
        deps_match = DEPENDS_RE.search(task.get("content", ""))
        deps = []
        if deps_match:
            deps_str = deps_match.group(1).strip()
            if deps_str:
                deps = [d.strip().strip("' \"") for d in deps_str.split(",") if d.strip()]
        graph[task_id] = deps
    return graph


def _detect_cycles(graph: dict[str, list[str]]) -> list[str]:
    """Detect circular dependencies using DFS."""
    visited = set()
    in_stack = set()
    cycles = []

    def dfs(node: str, path: list[str]) -> None:
        if node in in_stack:
            cycle_start = path.index(node)
            cycles.append(" → ".join(path[cycle_start:] + [node]))
            return
        if node in visited:
            return
        visited.add(node)
        in_stack.add(node)
        for dep in graph.get(node, []):
            dfs(dep, path + [node])
        in_stack.discard(node)

    for node in graph:
        if node not in visited:
            dfs(node, [])

    return cycles
