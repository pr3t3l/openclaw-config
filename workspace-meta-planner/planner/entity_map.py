"""Entity Map generator — extract entities/IDs/APIs/rules/states from docs.

Each entry includes heading path for on-demand section loading.
Used by Phase 6.5 cross-doc validation (compares maps, not full docs).
See spec.md §3 (Phase 6 — Entity Map, Phase 6.5 — on-demand loading).
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schemas" / "entity_map_schema.json"


@dataclass
class EntityEntry:
    """A single entity in the map."""
    name: str
    entity_type: str  # entity, id, api_endpoint, rule, state, transition
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


# Patterns for extracting entities from markdown
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_API_RE = re.compile(r"(?:/api/[\w/{}.-]+|(?:GET|POST|PUT|DELETE|PATCH)\s+/[\w/{}.-]+)", re.IGNORECASE)
_ID_RE = re.compile(r"\b(\w+_id|run_id|user_id|project_id|session_id|doc_id)\b", re.IGNORECASE)
_STATE_RE = re.compile(r"\b(active|paused|completed|failed|degraded|pending|draft|approved|archived)\b", re.IGNORECASE)
_RULE_RE = re.compile(r"(?:rule|constraint|must|never|always|forbidden|required)\s*:?\s*(.{10,80})", re.IGNORECASE)


def extract_entities(doc_content: str, document_name: str) -> EntityMap:
    """Extract entities from a markdown document.

    Finds: entities (tables/schemas), IDs, API endpoints, rules,
    states, and transitions.

    Args:
        doc_content: Full markdown content.
        document_name: Name of the document.

    Returns:
        EntityMap with all extracted entries.
    """
    entity_map = EntityMap(document_name=document_name)
    sections = _build_heading_paths(doc_content)

    for heading_path, section_content in sections:
        # API endpoints
        for match in _API_RE.finditer(section_content):
            entity_map.entries.append(EntityEntry(
                name=match.group().strip(),
                entity_type="api_endpoint",
                heading_path=heading_path,
            ))

        # IDs
        for match in _ID_RE.finditer(section_content):
            name = match.group()
            if not any(e.name == name and e.heading_path == heading_path for e in entity_map.entries):
                entity_map.entries.append(EntityEntry(
                    name=name,
                    entity_type="id",
                    heading_path=heading_path,
                ))

        # States
        states_found = set()
        for match in _STATE_RE.finditer(section_content):
            state = match.group().lower()
            if state not in states_found:
                states_found.add(state)
                entity_map.entries.append(EntityEntry(
                    name=state,
                    entity_type="state",
                    heading_path=heading_path,
                ))

        # Rules/constraints
        for match in _RULE_RE.finditer(section_content):
            rule_text = match.group().strip()
            if len(rule_text) > 15:
                entity_map.entries.append(EntityEntry(
                    name=rule_text[:80],
                    entity_type="rule",
                    heading_path=heading_path,
                ))

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
