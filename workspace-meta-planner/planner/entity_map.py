"""Entity Map generator — extract typed entities from SDD documents.

Extracts: DECISION, CONSTRAINT, COMPONENT, INTERFACE, EXIT_CODE, DEPENDENCY.
Each entry includes heading path for on-demand section loading.
Used by Phase 6.5 cross-doc validation (compares maps, not full docs).
See spec.md §3 (Phase 6 — Entity Map, Phase 6.5 — on-demand loading).

All extraction is deterministic (regex + markdown parsing), $0 cost.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schemas" / "entity_map_schema.json"

# Valid entity types
ENTITY_TYPES = {
    "DECISION", "CONSTRAINT", "COMPONENT", "INTERFACE",
    "EXIT_CODE", "DEPENDENCY",
    # Legacy types kept for backward compat with existing maps
    "id", "api_endpoint", "state", "rule",
}


@dataclass
class EntityEntry:
    """A single entity in the map."""
    name: str
    entity_type: str
    heading_path: str  # e.g., "## 3. Data Model > ### User Schema"
    details: str = ""


@dataclass
class EntityMap:
    """Map of all entities in a document."""
    document_name: str
    entries: list[EntityEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "document_name": self.document_name,
            "entries": [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "heading_path": e.heading_path,
                    "details": e.details,
                }
                for e in self.entries
            ],
        }

    def find_by_name(self, name: str) -> list[EntityEntry]:
        """Find entries by name (case-insensitive)."""
        name_lower = name.lower()
        return [e for e in self.entries if name_lower in e.name.lower()]

    def find_by_type(self, entity_type: str) -> list[EntityEntry]:
        """Find entries by type."""
        return [e for e in self.entries if e.entity_type == entity_type]


# ── Regex patterns ────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

# DECISION: table rows in decision tables (skip header/separator rows)
_DECISION_PROSE_RE = re.compile(
    r"(?:chose|chosen|decided|selected|picked|using)\s+(.{5,80}?)\s+(?:because|over|instead|rather|—|–|-)\s+(.{5,80}?)[.\n]",
    re.IGNORECASE,
)

# CONSTRAINT: "must", "never", "always", "forbidden", "required"
_CONSTRAINT_RE = re.compile(
    r"(?:^|\n)\s*[-*]?\s*(?:must|never|always|forbidden|required|do not|shall not|cannot)\b\s*:?\s*(.{10,120})",
    re.IGNORECASE,
)

# COMPONENT: file paths (.py, .sh, .md, .json, .js, .ts) or module/class names
_FILE_PATH_RE = re.compile(
    r"(?:`([a-zA-Z0-9_/.-]+\.(?:py|sh|md|json|js|ts|yaml|yml|toml))`|"
    r"\b([a-zA-Z_]\w+/[a-zA-Z_]\w+\.(?:py|sh|md|json|js|ts))\b)",
)
_CLASS_RE = re.compile(
    r"(?:class|module|package)\s+`?([A-Z]\w+)`?",
)

# INTERFACE: function signatures, "returns", "accepts", "input:", "output:"
_INTERFACE_RE = re.compile(
    r"(?:`([a-zA-Z_]\w+)\s*\(.*?\)\s*(?:→|->|returns?)\s*(.{3,60}?)`|"
    r"(?:returns?|accepts?|input|output)\s*:?\s*(.{5,80}))",
    re.IGNORECASE,
)

# EXIT_CODE: "exit 0", "exit code 1", "return code"
_EXIT_CODE_RE = re.compile(
    r"exit\s*(?:code\s*)?(\d+)\s*[=:—–-]\s*(.{3,60})",
    re.IGNORECASE,
)

# DEPENDENCY: "depends on", "requires", "uses"
_DEPENDENCY_RE = re.compile(
    r"(?:^|\n)\s*[-*]?\s*`?([A-Za-z]\w+(?:\.\w+)?)`?\s+(?:depends on|requires|uses|imports?)\s+`?([A-Za-z]\w+(?:\.\w+)?)`?",
    re.IGNORECASE,
)

# Legacy patterns (kept for backward compat)
_API_RE = re.compile(
    r"(?:/api/[\w/{}.-]+|(?:GET|POST|PUT|DELETE|PATCH)\s+/[\w/{}.-]+)",
    re.IGNORECASE,
)
_ID_RE = re.compile(
    r"\b(\w+_id|run_id|user_id|project_id|session_id|doc_id)\b",
    re.IGNORECASE,
)


def extract_entities(doc_content: str, document_name: str) -> EntityMap:
    """Extract typed entities from a markdown document.

    Finds: DECISION, CONSTRAINT, COMPONENT, INTERFACE, EXIT_CODE,
    DEPENDENCY, plus legacy types (id, api_endpoint).

    Args:
        doc_content: Full markdown content.
        document_name: Name of the document.

    Returns:
        EntityMap with all extracted entries.
    """
    entity_map = EntityMap(document_name=document_name)
    sections = _build_heading_paths(doc_content)

    for heading_path, section_content in sections:
        _extract_decisions(entity_map, heading_path, section_content)
        _extract_constraints(entity_map, heading_path, section_content)
        _extract_components(entity_map, heading_path, section_content)
        _extract_interfaces(entity_map, heading_path, section_content)
        _extract_exit_codes(entity_map, heading_path, section_content)
        _extract_dependencies(entity_map, heading_path, section_content)
        # Legacy: API endpoints and IDs (for backward compat)
        _extract_api_endpoints(entity_map, heading_path, section_content)
        _extract_ids(entity_map, heading_path, section_content)

    # Deduplicate by (name, type, heading_path)
    seen = set()
    unique = []
    for e in entity_map.entries:
        key = (e.name.lower(), e.entity_type, e.heading_path)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    entity_map.entries = unique

    logger.info(f"Extracted {len(entity_map.entries)} entities from {document_name}")
    return entity_map


def _extract_decisions(em: EntityMap, heading: str, content: str) -> None:
    """Extract DECISION entities from tables and prose."""
    # Parse markdown tables that look like decision tables
    lines = content.split("\n")
    in_table = False
    header_cols: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            header_cols = []
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        # Skip separator rows (|---|---|)
        if all(c.replace("-", "").replace(":", "").strip() == "" for c in cells):
            continue

        if not in_table:
            # This is the header row — check if it looks like a decision table
            header_lower = " ".join(c.lower() for c in cells)
            if any(kw in header_lower for kw in (
                "decision", "choice", "why", "reason", "alternative", "rejected",
            )):
                in_table = True
                header_cols = cells
            continue

        # Data row in a decision table
        if len(cells) >= 2:
            decision = cells[0].strip()
            choice = cells[1].strip()
            if decision and choice and len(decision) > 2 and decision.lower() != "decision":
                em.entries.append(EntityEntry(
                    name=decision[:80],
                    entity_type="DECISION",
                    heading_path=heading,
                    details=choice[:120],
                ))

    # Prose decisions
    for match in _DECISION_PROSE_RE.finditer(content):
        choice = match.group(1).strip()
        rationale = match.group(2).strip()
        if choice and len(choice) > 3:
            em.entries.append(EntityEntry(
                name=choice[:80],
                entity_type="DECISION",
                heading_path=heading,
                details=rationale[:120],
            ))


def _extract_constraints(em: EntityMap, heading: str, content: str) -> None:
    """Extract CONSTRAINT entities."""
    for match in _CONSTRAINT_RE.finditer(content):
        text = match.group(1).strip().rstrip(".")
        if len(text) > 10:
            # Build a short name from first clause
            name = text[:80]
            em.entries.append(EntityEntry(
                name=name,
                entity_type="CONSTRAINT",
                heading_path=heading,
                details=text[:200],
            ))


def _extract_components(em: EntityMap, heading: str, content: str) -> None:
    """Extract COMPONENT entities (file paths, classes, modules)."""
    for match in _FILE_PATH_RE.finditer(content):
        path = match.group(1) or match.group(2)
        if path:
            em.entries.append(EntityEntry(
                name=path,
                entity_type="COMPONENT",
                heading_path=heading,
            ))

    for match in _CLASS_RE.finditer(content):
        class_name = match.group(1)
        if class_name and len(class_name) > 2:
            em.entries.append(EntityEntry(
                name=class_name,
                entity_type="COMPONENT",
                heading_path=heading,
            ))


def _extract_interfaces(em: EntityMap, heading: str, content: str) -> None:
    """Extract INTERFACE entities (function sigs, input/output contracts)."""
    for match in _INTERFACE_RE.finditer(content):
        func_name = match.group(1)
        return_type = match.group(2)
        io_text = match.group(3)

        if func_name and return_type:
            em.entries.append(EntityEntry(
                name=f"{func_name}()",
                entity_type="INTERFACE",
                heading_path=heading,
                details=f"returns {return_type.strip()}",
            ))
        elif io_text:
            text = io_text.strip()
            if len(text) > 5:
                em.entries.append(EntityEntry(
                    name=text[:60],
                    entity_type="INTERFACE",
                    heading_path=heading,
                    details=text[:120],
                ))


def _extract_exit_codes(em: EntityMap, heading: str, content: str) -> None:
    """Extract EXIT_CODE entities."""
    for match in _EXIT_CODE_RE.finditer(content):
        code = match.group(1)
        meaning = match.group(2).strip()
        em.entries.append(EntityEntry(
            name=f"exit {code}",
            entity_type="EXIT_CODE",
            heading_path=heading,
            details=meaning,
        ))


def _extract_dependencies(em: EntityMap, heading: str, content: str) -> None:
    """Extract DEPENDENCY entities."""
    for match in _DEPENDENCY_RE.finditer(content):
        source = match.group(1).strip()
        target = match.group(2).strip()
        if source and target:
            em.entries.append(EntityEntry(
                name=f"{source} → {target}",
                entity_type="DEPENDENCY",
                heading_path=heading,
                details=f"{source} depends on {target}",
            ))


def _extract_api_endpoints(em: EntityMap, heading: str, content: str) -> None:
    """Extract API endpoint entities (legacy type)."""
    for match in _API_RE.finditer(content):
        em.entries.append(EntityEntry(
            name=match.group().strip(),
            entity_type="api_endpoint",
            heading_path=heading,
        ))


def _extract_ids(em: EntityMap, heading: str, content: str) -> None:
    """Extract ID entities (legacy type)."""
    for match in _ID_RE.finditer(content):
        em.entries.append(EntityEntry(
            name=match.group(),
            entity_type="id",
            heading_path=heading,
        ))


def _build_heading_paths(content: str) -> list[tuple[str, str]]:
    """Build (heading_path, section_content) pairs."""
    headings = list(_HEADING_RE.finditer(content))
    if not headings:
        return [("(root)", content)]

    sections = []
    heading_stack: list[tuple[int, str]] = []

    for i, match in enumerate(headings):
        level = len(match.group(1))
        title = match.group(2).strip()

        # Update stack
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, f"{'#' * level} {title}"))

        # Build path
        path = " > ".join(h[1] for h in heading_stack)

        # Get content until next heading
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
        section_content = content[start:end].strip()

        sections.append((path, section_content))

    return sections


def save_entity_map(entity_map: EntityMap, run_dir: str) -> str:
    """Save entity map to run directory."""
    output_dir = Path(run_dir) / "entity_maps"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = entity_map.document_name.replace(".", "_").replace("/", "_")
    path = output_dir / f"{safe_name}.json"
    path.write_text(json.dumps(entity_map.to_dict(), indent=2))
    return str(path)
