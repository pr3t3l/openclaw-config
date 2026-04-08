"""Phase 6.5: Cross-document validation via Entity Maps.

Validates consistency using Entity Maps (NOT full docs).
On conflict: loads ONLY specific sections via heading paths.
See spec.md §3 (Phase 6.5).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from planner.entity_map import EntityMap, EntityEntry

logger = logging.getLogger(__name__)


@dataclass
class Contradiction:
    """A contradiction found between documents."""
    entity_name: str
    entity_type: str
    doc_a: str
    doc_a_value: str
    doc_a_heading: str
    doc_b: str
    doc_b_value: str
    doc_b_heading: str
    description: str = ""
    question: str = ""


@dataclass
class CrossDocResult:
    """Result of cross-document validation."""
    contradictions: list[Contradiction] = field(default_factory=list)
    docs_checked: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.contradictions) == 0

    @property
    def contradiction_count(self) -> int:
        return len(self.contradictions)


def validate_entities(entity_maps: dict[str, EntityMap]) -> CrossDocResult:
    """Validate consistency across all Entity Maps.

    Checks:
    - Entity name conflicts (same name, different details)
    - API endpoint conflicts
    - ID type conflicts
    - State machine conflicts
    - Rule contradictions

    Args:
        entity_maps: Dict of document_name → EntityMap.

    Returns:
        CrossDocResult with contradictions found.
    """
    result = CrossDocResult(docs_checked=list(entity_maps.keys()))

    if len(entity_maps) < 2:
        return result

    docs = list(entity_maps.items())

    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            name_a, map_a = docs[i]
            name_b, map_b = docs[j]
            contradictions = _compare_maps(name_a, map_a, name_b, map_b)
            result.contradictions.extend(contradictions)

    if result.contradictions:
        logger.warning(f"Cross-doc: {result.contradiction_count} contradictions found")
    else:
        logger.info(f"Cross-doc: 0 contradictions across {len(entity_maps)} docs")

    return result


def load_conflict_sections(
    contradiction: Contradiction,
    doc_contents: dict[str, str],
) -> dict[str, str]:
    """Load ONLY the specific sections involved in a conflict.

    Uses heading paths from Entity Map entries to extract targeted content.

    Args:
        contradiction: The contradiction to resolve.
        doc_contents: Dict of document_name → full content.

    Returns:
        Dict of {doc_name: relevant_section_content}.
    """
    sections = {}

    for doc_name, heading in [
        (contradiction.doc_a, contradiction.doc_a_heading),
        (contradiction.doc_b, contradiction.doc_b_heading),
    ]:
        content = doc_contents.get(doc_name, "")
        if content and heading:
            section = _extract_section_by_heading(content, heading)
            sections[doc_name] = section or f"(Section not found: {heading})"
        else:
            sections[doc_name] = "(Content not available)"

    return sections


def _compare_maps(
    name_a: str, map_a: EntityMap,
    name_b: str, map_b: EntityMap,
) -> list[Contradiction]:
    """Compare two Entity Maps for contradictions."""
    contradictions = []

    # Group entries by type for targeted comparison
    for entity_type in (
        "id", "api_endpoint", "state",  # legacy
        "DECISION", "CONSTRAINT", "COMPONENT", "INTERFACE", "EXIT_CODE", "DEPENDENCY",
    ):
        entries_a = {e.name.lower(): e for e in map_a.find_by_type(entity_type)}
        entries_b = {e.name.lower(): e for e in map_b.find_by_type(entity_type)}

        # Find same-name entities that appear in both docs
        common = set(entries_a.keys()) & set(entries_b.keys())
        for name in common:
            ea = entries_a[name]
            eb = entries_b[name]
            # Check for detail conflicts (if details differ)
            if ea.details and eb.details and ea.details.lower() != eb.details.lower():
                contradictions.append(Contradiction(
                    entity_name=ea.name,
                    entity_type=entity_type,
                    doc_a=name_a,
                    doc_a_value=ea.details,
                    doc_a_heading=ea.heading_path,
                    doc_b=name_b,
                    doc_b_value=eb.details,
                    doc_b_heading=eb.heading_path,
                    description=f"{entity_type} '{ea.name}' has conflicting details",
                    question=f"Which definition of '{ea.name}' is correct?",
                ))

    # Check for naming conflicts across types
    all_a = {e.name.lower(): e for e in map_a.entries}
    all_b = {e.name.lower(): e for e in map_b.entries}
    common_names = set(all_a.keys()) & set(all_b.keys())

    for name in common_names:
        ea = all_a[name]
        eb = all_b[name]
        if ea.entity_type != eb.entity_type:
            contradictions.append(Contradiction(
                entity_name=ea.name,
                entity_type="naming_conflict",
                doc_a=name_a,
                doc_a_value=f"type={ea.entity_type}",
                doc_a_heading=ea.heading_path,
                doc_b=name_b,
                doc_b_value=f"type={eb.entity_type}",
                doc_b_heading=eb.heading_path,
                description=f"'{ea.name}' is '{ea.entity_type}' in {name_a} but '{eb.entity_type}' in {name_b}",
                question=f"What is '{ea.name}' — {ea.entity_type} or {eb.entity_type}?",
            ))

    return contradictions


def _extract_section_by_heading(content: str, heading_path: str) -> Optional[str]:
    """Extract a section from content using the deepest heading in the path."""
    import re
    # Get the last heading in the path
    parts = heading_path.split(" > ")
    target = parts[-1].strip() if parts else heading_path

    # Remove the # prefix for matching
    target_text = re.sub(r"^#+\s*", "", target).strip()

    # Search all headings in content, find best match by substring
    heading_re = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
    best_match = None
    target_lower = target_text.lower()

    for m in heading_re.finditer(content):
        heading_text = m.group(2).strip().lower()
        if target_lower in heading_text or heading_text in target_lower:
            best_match = m
            break
        # Fallback: check key words overlap
        target_words = set(w for w in target_lower.split() if len(w) > 2)
        heading_words = set(w for w in heading_text.split() if len(w) > 2)
        if target_words and heading_words and len(target_words & heading_words) >= len(target_words) * 0.5:
            best_match = m
            break

    if not best_match:
        return None

    level = len(best_match.group(1))
    start = best_match.end()

    # Find end: next heading of same or higher level
    next_heading = re.compile(rf"^#{{{1},{level}}}\s+", re.MULTILINE)
    end_match = next_heading.search(content[start:])
    end = start + end_match.start() if end_match else len(content)

    return content[best_match.start():end].strip()
