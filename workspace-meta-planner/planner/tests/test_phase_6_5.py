"""Tests for phases/phase_6_5_crossdoc.py — TASK-030."""

import pytest

from planner.entity_map import EntityMap, EntityEntry
from planner.phases.phase_6_5_crossdoc import (
    Contradiction,
    CrossDocResult,
    validate_entities,
    load_conflict_sections,
    _extract_section_by_heading,
)


def _make_map(doc_name, entries):
    return EntityMap(doc_name, entries)


class TestValidateEntities:
    def test_no_contradictions(self):
        maps = {
            "a.md": _make_map("a.md", [EntityEntry("user_id", "id", "## 1")]),
            "b.md": _make_map("b.md", [EntityEntry("plan_id", "id", "## 2")]),
        }
        result = validate_entities(maps)
        assert result.passed
        assert result.contradiction_count == 0

    def test_detects_type_conflict(self):
        maps = {
            "a.md": _make_map("a.md", [EntityEntry("status", "id", "## 1")]),
            "b.md": _make_map("b.md", [EntityEntry("status", "state", "## 2")]),
        }
        result = validate_entities(maps)
        assert not result.passed
        assert result.contradiction_count >= 1
        c = result.contradictions[0]
        assert "status" in c.entity_name

    def test_detects_detail_conflict(self):
        maps = {
            "a.md": _make_map("a.md", [
                EntityEntry("user_id", "id", "## Users", details="UUID")
            ]),
            "b.md": _make_map("b.md", [
                EntityEntry("user_id", "id", "## Auth", details="integer")
            ]),
        }
        result = validate_entities(maps)
        assert not result.passed
        assert any("user_id" in c.entity_name for c in result.contradictions)

    def test_single_doc_passes(self):
        maps = {"a.md": _make_map("a.md", [EntityEntry("x", "id", "## 1")])}
        result = validate_entities(maps)
        assert result.passed

    def test_empty_maps(self):
        result = validate_entities({})
        assert result.passed

    def test_docs_checked_listed(self):
        maps = {
            "a.md": _make_map("a.md", []),
            "b.md": _make_map("b.md", []),
        }
        result = validate_entities(maps)
        assert "a.md" in result.docs_checked
        assert "b.md" in result.docs_checked

    def test_three_docs(self):
        maps = {
            "a.md": _make_map("a.md", [EntityEntry("x", "id", "## 1", details="UUID")]),
            "b.md": _make_map("b.md", [EntityEntry("x", "id", "## 2", details="integer")]),
            "c.md": _make_map("c.md", [EntityEntry("x", "id", "## 3", details="UUID")]),
        }
        result = validate_entities(maps)
        # a vs b conflicts, a vs c same, b vs c conflicts
        assert result.contradiction_count >= 1

    def test_contradiction_has_headings(self):
        maps = {
            "a.md": _make_map("a.md", [EntityEntry("x", "id", "## Schema > ### Users", details="UUID")]),
            "b.md": _make_map("b.md", [EntityEntry("x", "id", "## Auth > ### Tokens", details="int")]),
        }
        result = validate_entities(maps)
        c = result.contradictions[0]
        assert "Schema" in c.doc_a_heading or "Users" in c.doc_a_heading
        assert "Auth" in c.doc_b_heading or "Tokens" in c.doc_b_heading

    def test_contradiction_has_question(self):
        maps = {
            "a.md": _make_map("a.md", [EntityEntry("status", "id", "## 1")]),
            "b.md": _make_map("b.md", [EntityEntry("status", "state", "## 2")]),
        }
        result = validate_entities(maps)
        assert result.contradictions[0].question


class TestLoadConflictSections:
    def test_loads_sections(self):
        c = Contradiction(
            "user_id", "id",
            "a.md", "UUID", "## 3. Users",
            "b.md", "integer", "## 2. Auth",
            "type mismatch",
        )
        docs = {
            "a.md": "# A\n\n## 3. Users\nuser_id is UUID.\n\n## 4. Other\nStuff.",
            "b.md": "# B\n\n## 2. Auth\nuser_id is integer.\n\n## 3. Next\nMore.",
        }
        sections = load_conflict_sections(c, docs)
        assert "UUID" in sections["a.md"]
        assert "integer" in sections["b.md"]
        # Should NOT contain other sections
        assert "Stuff" not in sections["a.md"]

    def test_missing_doc(self):
        c = Contradiction("x", "id", "a.md", "v1", "## 1", "b.md", "v2", "## 2")
        sections = load_conflict_sections(c, {})
        assert "not available" in sections["a.md"].lower()


class TestExtractSectionByHeading:
    def test_extracts(self):
        content = "# Doc\n\n## Purpose\nThis is the purpose.\n\n## Stack\nPostgreSQL."
        section = _extract_section_by_heading(content, "## Purpose")
        assert "purpose" in section.lower()
        assert "PostgreSQL" not in section

    def test_nested_heading_path(self):
        content = "# Doc\n\n## Data\n\n### Users\nuser_id UUID.\n\n### Orders\norder_id."
        section = _extract_section_by_heading(content, "## Data > ### Users")
        assert "user_id" in section
        assert "order_id" not in section

    def test_not_found(self):
        assert _extract_section_by_heading("# Doc\n## A\nContent.", "## Missing") is None
