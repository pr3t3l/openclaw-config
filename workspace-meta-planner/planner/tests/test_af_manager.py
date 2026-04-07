"""Tests for af_manager.py — TASK-028."""

import pytest

from planner.af_manager import (
    AFEntry,
    approve,
    archive,
    classify,
    dedupe,
    deprecate,
    flag_stale,
    propose,
    _next_af_id,
)


def _make_entry(af_id="AF-001", status="ACTIVE", pattern="missing error handling"):
    return AFEntry(af_id=af_id, title="Test", status=status, af_class="safe_autofix",
                   confidence="HIGH", pattern=pattern, fix="add error handling")


class TestPropose:
    def test_creates_entry(self):
        entry = propose("Missing validation", "Add input validation")
        assert entry is not None
        assert entry.status == "PROPOSED"
        assert entry.af_id == "AF-001"

    def test_increments_id(self):
        existing = [_make_entry("AF-001"), _make_entry("AF-002")]
        entry = propose("New finding", "Fix it", existing_entries=existing)
        assert entry.af_id == "AF-003"

    def test_deduplicates(self):
        existing = [_make_entry(pattern="missing error handling in data flow")]
        entry = propose("missing error handling in data flow specs", "fix", existing_entries=existing)
        assert entry is None  # Duplicate

    def test_custom_class(self):
        entry = propose("Finding", "Fix", af_class="safe_autofix", confidence="HIGH")
        assert entry.af_class == "safe_autofix"
        assert entry.confidence == "HIGH"

    def test_run_id_stored(self):
        entry = propose("Finding", "Fix", run_id="RUN-20260406-001")
        assert entry.first_found == "RUN-20260406-001"


class TestDedupe:
    def test_detects_duplicate(self):
        existing = [_make_entry(pattern="missing error handling in data flow")]
        assert dedupe("missing error handling in data flow specs", existing)

    def test_allows_different(self):
        existing = [_make_entry(pattern="missing error handling")]
        assert not dedupe("database migration rollback strategy", existing)

    def test_empty_existing(self):
        assert not dedupe("anything", [])


class TestApprove:
    def test_proposed_to_active(self):
        entry = _make_entry(status="PROPOSED")
        result = approve(entry)
        assert result.status == "ACTIVE"

    def test_already_active(self):
        entry = _make_entry(status="DEPRECATED")
        result = approve(entry)
        assert result.status == "DEPRECATED"  # Can't approve deprecated


class TestDeprecate:
    def test_deprecates(self):
        entry = _make_entry(status="ACTIVE")
        result = deprecate(entry)
        assert result.status == "DEPRECATED"


class TestArchive:
    def test_archives(self):
        entry = _make_entry(status="DEPRECATED")
        result = archive(entry)
        assert result.status == "ARCHIVED"


class TestClassify:
    def test_safe_autofix(self):
        assert classify("Missing section header in spec") == "safe_autofix"
        assert classify("Formatting issue in table") == "safe_autofix"

    def test_requires_review(self):
        assert classify("Authentication flow has security gap") == "requires_review"
        assert classify("Cost tracking is incomplete") == "requires_review"


class TestFlagStale:
    def test_flags_untriggered(self):
        entries = [
            _make_entry("AF-001", "ACTIVE"),
            _make_entry("AF-002", "ACTIVE"),
        ]
        entries[0].last_triggered = ""
        entries[1].last_triggered = "RUN-20260410-001"
        stale = flag_stale(entries)
        assert len(stale) == 1
        assert stale[0].af_id == "AF-001"

    def test_no_stale(self):
        entries = [_make_entry()]
        entries[0].last_triggered = "RUN-20260410-001"
        assert flag_stale(entries) == []


class TestNextAFId:
    def test_first_id(self):
        assert _next_af_id([]) == "AF-001"

    def test_increments(self):
        existing = [_make_entry("AF-005")]
        assert _next_af_id(existing) == "AF-006"
