"""Tests for entity_map.py — TASK-026."""

import json
import pytest
from pathlib import Path

from planner.entity_map import (
    EntityMap,
    EntityEntry,
    extract_entities,
    save_entity_map,
)


SAMPLE_DOC = """# WORKFLOW_SPEC — Planner

## 1. Purpose
Build a planner with run_id tracking.

## 2. API Endpoints
The system exposes POST /api/plans and GET /api/plans/{plan_id}.

## 3. Rules
- Rule: Never retry with identical parameters
- Constraint: Max 2 retries per agent
- Must always save state before exit

## 4. States
Run status: active, paused, completed, failed.
"""


class TestExtractEntities:
    def test_finds_api_endpoints(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        apis = em.find_by_type("api_endpoint")
        names = [e.name for e in apis]
        assert any("/api/plans" in n for n in names)

    def test_finds_ids(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        ids = em.find_by_type("id")
        names = [e.name for e in ids]
        assert any("run_id" in n for n in names)

    def test_finds_states(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        states = em.find_by_type("state")
        names = [e.name for e in states]
        assert "active" in names
        assert "completed" in names

    def test_finds_rules(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        rules = em.find_by_type("rule")
        assert len(rules) >= 1

    def test_heading_paths(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        apis = em.find_by_type("api_endpoint")
        if apis:
            assert "API Endpoints" in apis[0].heading_path or "2." in apis[0].heading_path

    def test_document_name(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        assert em.document_name == "spec.md"

    def test_deduplication(self):
        doc = "# Doc\n## Section\nrun_id and run_id again and run_id third time."
        em = extract_entities(doc, "doc.md")
        run_ids = [e for e in em.entries if e.name == "run_id"]
        assert len(run_ids) == 1  # Deduped within same section


class TestEntityMap:
    def test_to_dict(self):
        em = EntityMap("doc.md", [
            EntityEntry("user_id", "id", "## 1. Schema"),
        ])
        d = em.to_dict()
        assert d["document_name"] == "doc.md"
        assert len(d["entries"]) == 1
        assert d["entries"][0]["name"] == "user_id"

    def test_find_by_name(self):
        em = EntityMap("doc.md", [
            EntityEntry("user_id", "id", "## 1"),
            EntityEntry("POST /api/users", "api_endpoint", "## 2"),
        ])
        found = em.find_by_name("user")
        assert len(found) == 2

    def test_find_by_type(self):
        em = EntityMap("doc.md", [
            EntityEntry("user_id", "id", "## 1"),
            EntityEntry("active", "state", "## 2"),
        ])
        assert len(em.find_by_type("id")) == 1
        assert len(em.find_by_type("state")) == 1

    def test_empty_map(self):
        em = EntityMap("doc.md")
        assert em.to_dict()["entries"] == []
        assert em.find_by_name("x") == []


class TestSaveEntityMap:
    def test_saves_to_disk(self, tmp_path):
        em = EntityMap("spec.md", [
            EntityEntry("run_id", "id", "## 1. Purpose"),
        ])
        path = save_entity_map(em, str(tmp_path))
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert data["document_name"] == "spec.md"

    def test_creates_directory(self, tmp_path):
        em = EntityMap("doc.md")
        save_entity_map(em, str(tmp_path))
        assert (tmp_path / "entity_maps").exists()


class TestEdgeCases:
    def test_empty_document(self):
        em = extract_entities("", "empty.md")
        assert len(em.entries) == 0

    def test_no_headings(self):
        em = extract_entities("Just plain text with run_id.", "flat.md")
        assert len(em.entries) >= 1

    def test_nested_headings(self):
        doc = "# Top\n## Section\n### Subsection\nrun_id here."
        em = extract_entities(doc, "nested.md")
        ids = em.find_by_type("id")
        if ids:
            assert "Subsection" in ids[0].heading_path
