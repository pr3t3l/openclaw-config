"""Tests for phases/phase_0_setup.py — TASK-013."""

import pytest
from pathlib import Path

from planner.phases.phase_0_setup import (
    detect_mode,
    determine_doc_list,
    load_context,
    run_phase_0,
    FOUNDATION_DOCS,
    NEW_PROJECT_DOC_ORDER,
)


@pytest.fixture
def empty_project(tmp_path):
    return str(tmp_path)


@pytest.fixture
def existing_project(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    for doc in FOUNDATION_DOCS:
        (docs_dir / doc).write_text(f"# {doc}\nContent here.")
    return str(tmp_path)


@pytest.fixture
def partial_project(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "PROJECT_FOUNDATION.md").write_text("# PF\nContent.")
    return str(tmp_path)


class TestDetectMode:
    def test_new_project_no_docs_dir(self, empty_project):
        assert detect_mode(empty_project) == "new_project"

    def test_existing_project(self, existing_project):
        assert detect_mode(existing_project) == "existing_project"

    def test_partial_project_is_new(self, partial_project):
        # Only 1 foundation doc — not enough
        assert detect_mode(partial_project) == "new_project"

    def test_monolith_with_attachments(self, empty_project):
        assert detect_mode(empty_project, has_attachments=True) == "monolith"

    def test_monolith_overrides_existing(self, existing_project):
        # Attachments override existing project detection
        assert detect_mode(existing_project, has_attachments=True) == "monolith"


class TestLoadContext:
    def test_no_docs_dir(self, empty_project):
        assert load_context(empty_project) == {}

    def test_loads_existing_docs(self, existing_project):
        ctx = load_context(existing_project)
        assert len(ctx) == len(FOUNDATION_DOCS)
        for doc in FOUNDATION_DOCS:
            assert doc in ctx
            assert len(ctx[doc]) > 0

    def test_skips_empty_docs(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "PROJECT_FOUNDATION.md").write_text("")
        (docs_dir / "CONSTITUTION.md").write_text("# Real content")
        ctx = load_context(str(tmp_path))
        assert "PROJECT_FOUNDATION.md" not in ctx
        assert "CONSTITUTION.md" in ctx

    def test_loads_audit_findings(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "AUDIT_FINDINGS.md").write_text("# AF\nContent.")
        ctx = load_context(str(tmp_path))
        assert "AUDIT_FINDINGS.md" in ctx


class TestDetermineDocList:
    def test_new_project_full_list(self):
        docs = determine_doc_list("new_project", "WORKFLOW_SPEC", {})
        assert docs[0] == "PROJECT_FOUNDATION.md"
        assert docs[1] == "CONSTITUTION.md"
        assert "WORKFLOW_SPEC.md" in docs
        assert len(docs) == len(NEW_PROJECT_DOC_ORDER) + 1

    def test_existing_project_spec_only(self):
        docs = determine_doc_list("existing_project", "MODULE_SPEC", {})
        assert docs == ["MODULE_SPEC.md"]

    def test_monolith_skips_existing(self):
        context = {"PROJECT_FOUNDATION.md": "content", "CONSTITUTION.md": "content"}
        docs = determine_doc_list("monolith", "WORKFLOW_SPEC", context)
        assert "PROJECT_FOUNDATION.md" not in docs
        assert "CONSTITUTION.md" not in docs
        assert "DATA_MODEL.md" in docs
        assert "WORKFLOW_SPEC.md" in docs


class TestRunPhase0:
    def test_new_project(self, empty_project):
        result = run_phase_0(empty_project, doc_type="WORKFLOW_SPEC")
        assert result.mode == "new_project"
        assert result.doc_type == "WORKFLOW_SPEC"
        assert len(result.documents_pending) > 0
        assert result.context_loaded == {}

    def test_existing_project(self, existing_project):
        result = run_phase_0(existing_project, doc_type="MODULE_SPEC")
        assert result.mode == "existing_project"
        assert len(result.context_loaded) == len(FOUNDATION_DOCS)
        assert result.documents_pending == ["MODULE_SPEC.md"]

    def test_monolith(self, empty_project):
        result = run_phase_0(empty_project, has_attachments=True, doc_type="WORKFLOW_SPEC")
        assert result.mode == "monolith"
        assert result.has_attachments is True

    def test_no_doc_type_yet(self, empty_project):
        result = run_phase_0(empty_project)
        assert result.doc_type is None
        assert result.documents_pending == []

    def test_monolith_routes_correctly(self, empty_project):
        result = run_phase_0(empty_project, has_attachments=True)
        assert result.mode == "monolith"
