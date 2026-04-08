"""Tests for entity_map.py — typed entity extraction."""

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
- Must always save state before exit
- Never use eval() on user input
- Required: all API calls must be authenticated

## 4. States
Run status: active, paused, completed, failed.

## 5. Key Decisions

| Decision | Choice | Why | Alternatives Rejected |
|----------|--------|-----|----------------------|
| Parser | Recursive descent | Fully auditable | eval(), pyparsing |
| Database | SQLite | No server needed | PostgreSQL |

We chose Python 3.12 because it has the best type hint support.

## 6. Components
The main modules are:
- `calculator/parser.py`
- `calculator/tokenizer.py`
- `scripts/run_tests.sh`

class Evaluator handles expression evaluation.
class TokenStream manages the token buffer.

## 7. Interfaces
`tokenize(input) → list[Token]`
`parse(tokens) → AST`
Input: raw math expression string
Output: evaluated numeric result

## 8. Exit Codes
exit 0 = success
exit 1 = parse error
exit 2 = runtime error

## 9. Dependencies
- `Parser` depends on `Tokenizer`
- `Evaluator` requires `Parser`
"""


class TestExtractDecisions:
    def test_finds_table_decisions(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        decisions = em.find_by_type("DECISION")
        names = [e.name for e in decisions]
        assert any("Parser" in n or "Recursive" in n for n in names)

    def test_decision_has_details(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        decisions = em.find_by_type("DECISION")
        with_details = [e for e in decisions if e.details]
        assert len(with_details) > 0

    def test_finds_prose_decisions(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        decisions = em.find_by_type("DECISION")
        names_and_details = [f"{e.name} {e.details}" for e in decisions]
        assert any("Python" in nd or "3.12" in nd for nd in names_and_details)


class TestExtractConstraints:
    def test_finds_must_constraints(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        constraints = em.find_by_type("CONSTRAINT")
        texts = [e.name for e in constraints]
        assert any("save state" in t.lower() for t in texts)

    def test_finds_never_constraints(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        constraints = em.find_by_type("CONSTRAINT")
        texts = [e.name for e in constraints]
        assert any("eval" in t.lower() for t in texts)

    def test_constraint_has_heading_path(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        constraints = em.find_by_type("CONSTRAINT")
        assert all(e.heading_path for e in constraints)


class TestExtractComponents:
    def test_finds_file_paths(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        components = em.find_by_type("COMPONENT")
        names = [e.name for e in components]
        assert "calculator/parser.py" in names
        assert "calculator/tokenizer.py" in names
        assert "scripts/run_tests.sh" in names

    def test_finds_classes(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        components = em.find_by_type("COMPONENT")
        names = [e.name for e in components]
        assert "Evaluator" in names
        assert "TokenStream" in names


class TestExtractInterfaces:
    def test_finds_function_signatures(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        interfaces = em.find_by_type("INTERFACE")
        names = [e.name for e in interfaces]
        assert any("tokenize" in n for n in names)

    def test_finds_io_contracts(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        interfaces = em.find_by_type("INTERFACE")
        all_text = " ".join(f"{e.name} {e.details}" for e in interfaces)
        assert "raw math expression" in all_text.lower() or "numeric result" in all_text.lower()


class TestExtractExitCodes:
    def test_finds_exit_codes(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        codes = em.find_by_type("EXIT_CODE")
        names = [e.name for e in codes]
        assert "exit 0" in names
        assert "exit 1" in names
        assert "exit 2" in names

    def test_exit_code_has_meaning(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        codes = em.find_by_type("EXIT_CODE")
        code_0 = next((e for e in codes if e.name == "exit 0"), None)
        assert code_0 is not None
        assert "success" in code_0.details.lower()


class TestExtractDependencies:
    def test_finds_dependencies(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        deps = em.find_by_type("DEPENDENCY")
        names = [e.name for e in deps]
        assert any("Parser" in n and "Tokenizer" in n for n in names)

    def test_dependency_has_details(self):
        em = extract_entities(SAMPLE_DOC, "spec.md")
        deps = em.find_by_type("DEPENDENCY")
        assert all(e.details for e in deps)


class TestLegacyTypes:
    """Ensure backward-compatible legacy types still work."""

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
            EntityEntry("active", "EXIT_CODE", "## 2"),
        ])
        assert len(em.find_by_type("id")) == 1
        assert len(em.find_by_type("EXIT_CODE")) == 1

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

    def test_deduplication(self):
        doc = "# Doc\n## Section\nrun_id and run_id again and run_id third time."
        em = extract_entities(doc, "doc.md")
        run_ids = [e for e in em.entries if e.name == "run_id"]
        assert len(run_ids) == 1

    def test_no_garbage_rules(self):
        """The old extractor produced junk like 'rules; fully auditable in ~120 lines |'."""
        doc = """# Doc
## Tech Stack
| Layer | Tech | Why |
|-------|------|-----|
| Language | Python | Simple rules; fully auditable in ~120 lines |
"""
        em = extract_entities(doc, "doc.md")
        constraints = em.find_by_type("CONSTRAINT")
        # Should NOT extract table cell fragments as constraints
        for c in constraints:
            assert "rules; fully auditable" not in c.name
