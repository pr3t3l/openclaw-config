"""Tests for template_loader.py — TASK-015."""

import pytest
from pathlib import Path

from planner.template_loader import (
    TEMPLATE_FILES,
    extract_sections,
    get_section_titles,
    init_audit_findings,
    load_template,
)


@pytest.fixture
def template_dir(tmp_path):
    """Create a mock template directory with sample templates."""
    for doc_type, filename in TEMPLATE_FILES.items():
        content = f"# {filename} — [Name]\n\n## 1. Purpose\n\nDescribe purpose.\n\n## 2. Scope\n\nDescribe scope.\n\n## 3. Details\n\nDetails here.\n"
        (tmp_path / filename).write_text(content)
    return str(tmp_path)


SAMPLE_MD = """# Test Document

## 1. Purpose

This is the purpose.

## 2. Stack

| Layer | Tech |
|-------|------|
| DB | PostgreSQL |

## 3. Notes

### 3.1 Sub-notes

Some sub-notes.

## 4. Empty Section
"""


class TestLoadTemplate:
    def test_loads_workflow_spec(self, template_dir):
        sections = load_template("WORKFLOW_SPEC", template_dir)
        assert len(sections) >= 3
        assert sections[0].title.endswith("[Name]") or "1. Purpose" in sections[0].title

    def test_loads_module_spec(self, template_dir):
        sections = load_template("MODULE_SPEC", template_dir)
        assert len(sections) >= 3

    def test_loads_all_types(self, template_dir):
        for doc_type in TEMPLATE_FILES:
            sections = load_template(doc_type, template_dir)
            assert len(sections) > 0

    def test_unknown_type_raises(self, template_dir):
        with pytest.raises(ValueError, match="Unknown template type"):
            load_template("NONEXISTENT", template_dir)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_template("WORKFLOW_SPEC", str(tmp_path))


class TestExtractSections:
    def test_extracts_top_level(self):
        sections = extract_sections(SAMPLE_MD)
        titles = [s.title for s in sections]
        assert "Test Document" in titles
        assert "1. Purpose" in titles
        assert "2. Stack" in titles

    def test_section_levels(self):
        sections = extract_sections(SAMPLE_MD)
        title_map = {s.title: s.level for s in sections}
        assert title_map["Test Document"] == 1
        assert title_map["1. Purpose"] == 2
        assert title_map["3.1 Sub-notes"] == 3

    def test_section_content(self):
        sections = extract_sections(SAMPLE_MD)
        purpose = next(s for s in sections if "Purpose" in s.title)
        assert "purpose" in purpose.content.lower()

    def test_empty_section(self):
        sections = extract_sections(SAMPLE_MD)
        empty = next(s for s in sections if "Empty" in s.title)
        assert empty.content == ""

    def test_empty_document(self):
        assert extract_sections("") == []


class TestGetSectionTitles:
    def test_returns_titles(self, template_dir):
        titles = get_section_titles("WORKFLOW_SPEC", template_dir)
        assert isinstance(titles, list)
        assert len(titles) > 0
        assert all(isinstance(t, str) for t in titles)


class TestInitAuditFindings:
    def test_creates_file(self, tmp_path):
        path = init_audit_findings(str(tmp_path))
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "AUDIT_FINDINGS" in content
        assert "Active Patterns" in content

    def test_does_not_overwrite(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        af = docs_dir / "AUDIT_FINDINGS.md"
        af.write_text("# Custom content")
        init_audit_findings(str(tmp_path))
        assert af.read_text() == "# Custom content"

    def test_creates_docs_dir(self, tmp_path):
        path = init_audit_findings(str(tmp_path))
        assert (tmp_path / "docs").exists()
