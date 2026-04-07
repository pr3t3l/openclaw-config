"""Impact analyzer — compute impact radius from blocker using task dependency graph.

See spec.md §10 (Re-Entry Step 2).
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskImpact:
    """Impact classification for a single task."""
    task_id: str
    status: str  # VALID, NEEDS_REVIEW, VOID
    reason: str = ""
    dependency_path: list[str] = field(default_factory=list)


@dataclass
class ImpactReport:
    """Full impact analysis report."""
    blocker_task: str
    impacts: list[TaskImpact] = field(default_factory=list)

    @property
    def valid_tasks(self) -> list[str]:
        return [t.task_id for t in self.impacts if t.status == "VALID"]

    @property
    def needs_review_tasks(self) -> list[str]:
        return [t.task_id for t in self.impacts if t.status == "NEEDS_REVIEW"]

    @property
    def void_tasks(self) -> list[str]:
        return [t.task_id for t in self.impacts if t.status == "VOID"]


def build_graph(tasks_content: str) -> dict[str, list[str]]:
    """Build a directed dependency graph from tasks.md.

    Returns:
        Dict of task_id → list of tasks it depends on.
    """
    graph: dict[str, list[str]] = {}
    current_task = None

    for line in tasks_content.split("\n"):
        task_match = re.match(r"###\s+(TASK-\d+)", line)
        if task_match:
            current_task = task_match.group(1)
            graph[current_task] = []
        elif current_task and "depends_on" in line.lower():
            deps_match = re.search(r"\[([^\]]*)\]", line)
            if deps_match:
                deps_str = deps_match.group(1).strip()
                if deps_str:
                    deps = [d.strip().strip("'\" ") for d in deps_str.split(",") if d.strip()]
                    graph[current_task] = [d for d in deps if d.startswith("TASK-")]

    return graph


def compute_impact(
    graph: dict[str, list[str]],
    blocker_task: str,
) -> ImpactReport:
    """Compute impact radius from a blocker task.

    - VOID: directly depends on blocker task's output
    - NEEDS_REVIEW: indirectly depends (transitive)
    - VALID: no path from blocker

    Args:
        graph: Dependency graph (task → deps).
        blocker_task: The task that is blocked.

    Returns:
        ImpactReport with per-task classification.
    """
    # Build reverse graph: task → list of tasks that depend on it
    dependents: dict[str, list[str]] = {t: [] for t in graph}
    for task, deps in graph.items():
        for dep in deps:
            if dep in dependents:
                dependents[dep].append(task)

    # BFS from blocker to find all affected tasks
    direct = set(dependents.get(blocker_task, []))
    indirect = set()

    visited = set()
    queue = list(direct)
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for dependent in dependents.get(current, []):
            if dependent not in direct:
                indirect.add(dependent)
            queue.append(dependent)

    # Build impact report
    report = ImpactReport(blocker_task=blocker_task)

    for task_id in sorted(graph.keys()):
        if task_id == blocker_task:
            continue

        if task_id in direct:
            path = _find_path(graph, task_id, blocker_task)
            report.impacts.append(TaskImpact(
                task_id=task_id,
                status="VOID",
                reason=f"Directly depends on {blocker_task}",
                dependency_path=path,
            ))
        elif task_id in indirect:
            path = _find_path(graph, task_id, blocker_task)
            report.impacts.append(TaskImpact(
                task_id=task_id,
                status="NEEDS_REVIEW",
                reason=f"Indirectly depends on {blocker_task} via chain",
                dependency_path=path,
            ))
        else:
            report.impacts.append(TaskImpact(
                task_id=task_id,
                status="VALID",
                reason="No dependency on blocker",
            ))

    return report


def mark_tasks(
    tasks_content: str,
    report: ImpactReport,
) -> str:
    """Annotate tasks.md with impact status markers.

    Adds [VOID], [NEEDS_REVIEW], or [VALID] after each task heading.
    """
    result = tasks_content
    impact_map = {t.task_id: t.status for t in report.impacts}

    for task_id, status in impact_map.items():
        pattern = re.compile(rf"(###\s+{re.escape(task_id)}:)", re.MULTILINE)
        result = pattern.sub(rf"\1 [{status}]", result)

    return result


def _find_path(
    graph: dict[str, list[str]],
    from_task: str,
    to_task: str,
) -> list[str]:
    """Find the dependency path from from_task back to to_task."""
    visited = set()
    queue = [(from_task, [from_task])]

    while queue:
        current, path = queue.pop(0)
        if current == to_task:
            return path
        if current in visited:
            continue
        visited.add(current)
        for dep in graph.get(current, []):
            queue.append((dep, path + [dep]))

    return [from_task, "...", to_task]
