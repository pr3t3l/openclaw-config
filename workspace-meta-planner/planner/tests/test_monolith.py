"""Tests for monolith/ — TASK-034 and TASK-035."""

import pytest

from planner.monolith.parser import parse_document, ContentBlock
from planner.monolith.mapper import map_blocks, BlockMapping, TEMPLATE_KEYWORDS
from planner.monolith.confidence import score_mapping, score_all, get_review_needed, ConfidenceResult
from planner.monolith.reviewer import (
    audit_low_confidence, present_mapping, format_mapping_for_telegram,
)


MONOLITH_DOC = """# My Project Bible

## Vision and Purpose
We're building a finance tracker to manage expenses and Airbnb deductions.
The tech stack includes PostgreSQL, Python, and React.

## Database Schema
Users table with user_id (UUID), email, created_at.
Transactions table with tx_id, amount, category, date.
Foreign key from transactions to users.

## API Endpoints
POST /api/transactions — create new transaction
GET /api/transactions — list transactions
Integration with Stripe for payments.

## Rules and Constraints
Never retry with identical parameters.
Always validate input before processing.
Must track cost per API call.

## Lessons from V1
Bug: Python requests fails in WSL for long calls. Fix: use streaming.
Mistake: batch-ran untested changes, lost $6.
"""


class TestParser:
    def test_parses_blocks(self):
        blocks = parse_document(MONOLITH_DOC)
        assert len(blocks) >= 5
        assert all(isinstance(b, ContentBlock) for b in blocks)

    def test_block_headings(self):
        blocks = parse_document(MONOLITH_DOC)
        headings = [b.heading for b in blocks]
        assert "Vision and Purpose" in headings
        assert "Database Schema" in headings

    def test_block_content(self):
        blocks = parse_document(MONOLITH_DOC)
        db_block = next(b for b in blocks if "Database" in b.heading)
        assert "user_id" in db_block.content
        assert db_block.word_count > 5

    def test_block_ids_sequential(self):
        blocks = parse_document(MONOLITH_DOC)
        ids = [b.block_id for b in blocks]
        assert ids == list(range(1, len(blocks) + 1))

    def test_empty_document(self):
        assert parse_document("") == []

    def test_no_headings(self):
        blocks = parse_document("Just plain text here.")
        assert len(blocks) == 1
        assert blocks[0].heading == "(no heading)"

    def test_line_numbers(self):
        blocks = parse_document(MONOLITH_DOC)
        assert blocks[0].source_line >= 1


class TestMapper:
    def test_maps_blocks(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        assert len(mappings) == len(blocks)

    def test_db_maps_to_data_model(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        db_mapping = next(m for m in mappings if "Database" in m.block.heading)
        assert "DATA_MODEL" in db_mapping.targets

    def test_api_maps_to_integrations(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        api_mapping = next(m for m in mappings if "API" in m.block.heading)
        assert "INTEGRATIONS" in api_mapping.targets

    def test_rules_maps_to_constitution(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        rules_mapping = next(m for m in mappings if "Rules" in m.block.heading)
        assert "CONSTITUTION" in rules_mapping.targets

    def test_lessons_maps_correctly(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        lessons_mapping = next(m for m in mappings if "Lessons" in m.block.heading)
        assert "LESSONS_LEARNED" in lessons_mapping.targets

    def test_multi_tagging(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        # Vision block should map to PROJECT_FOUNDATION and possibly others
        vision_mapping = next(m for m in mappings if "Vision" in m.block.heading)
        assert len(vision_mapping.targets) >= 1

    def test_scores_present(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        for m in mappings:
            if m.targets:
                assert all(m.scores[t] > 0 for t in m.targets)


class TestConfidence:
    def test_high_confidence(self):
        block = ContentBlock(1, "DB Schema", "table column field entity schema database model index foreign key migration postgresql")
        mapping = BlockMapping(block=block, targets=["DATA_MODEL"], scores={"DATA_MODEL": 0.85})
        result = score_mapping(mapping)
        assert result.confidence == "HIGH"
        assert not result.needs_review

    def test_low_confidence(self):
        block = ContentBlock(1, "Random", "something vague")
        mapping = BlockMapping(block=block, targets=["DATA_MODEL"], scores={"DATA_MODEL": 0.1})
        result = score_mapping(mapping)
        assert result.confidence == "LOW"
        assert result.needs_review

    def test_medium_confidence(self):
        mapping = BlockMapping(
            block=ContentBlock(1, "X", "content"),
            targets=["INTEGRATIONS"], scores={"INTEGRATIONS": 0.6},
        )
        result = score_mapping(mapping)
        assert result.confidence == "MEDIUM"
        assert result.needs_review

    def test_no_targets(self):
        mapping = BlockMapping(block=ContentBlock(1, "X", "y"), targets=[], scores={})
        result = score_mapping(mapping)
        assert result.confidence == "LOW"
        assert result.needs_review

    def test_score_all(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        results = score_all(mappings)
        assert len(results) == len(mappings)

    def test_get_review_needed(self):
        blocks = parse_document(MONOLITH_DOC)
        mappings = map_blocks(blocks)
        results = score_all(mappings)
        review = get_review_needed(results)
        assert all(r.needs_review for r in review)


class TestReviewer:
    def _mock_gateway(self):
        class MockGW:
            def __init__(self):
                self.calls = []
            def call_model(self, role, prompt, phase="0", document=None, **kw):
                self.calls.append(role)
                return {"content": "TARGETS: DATA_MODEL, INTEGRATIONS\nREASON: Contains schema and API refs", "tokens_in": 200, "tokens_out": 100}
        return MockGW()

    def test_audits_low_confidence(self):
        block = ContentBlock(1, "Mixed", "schema and api endpoint stuff")
        mapping = BlockMapping(block=block, targets=["DATA_MODEL"], scores={"DATA_MODEL": 0.3})
        cr = ConfidenceResult(mapping=mapping, confidence="LOW", top_score=0.3, needs_review=True)

        gw = self._mock_gateway()
        results = audit_low_confidence([cr], gw)
        assert len(results) == 1
        assert "DATA_MODEL" in results[0].auditor_targets
        assert "auditor_gpt" in gw.calls

    def test_empty_input(self):
        gw = self._mock_gateway()
        assert audit_low_confidence([], gw) == []
        assert len(gw.calls) == 0

    def test_present_mapping(self):
        block = ContentBlock(1, "Schema", "tables and columns")
        mapping = BlockMapping(block=block, targets=["DATA_MODEL"], scores={"DATA_MODEL": 0.9})
        cr = ConfidenceResult(mapping=mapping, confidence="HIGH", top_score=0.9, needs_review=False)
        presentations = present_mapping([cr])
        assert len(presentations) >= 1
        assert presentations[0].template == "DATA_MODEL"

    def test_format_for_telegram(self):
        block = ContentBlock(1, "Schema", "content here", word_count=50)
        mapping = BlockMapping(block=block, targets=["DATA_MODEL"], scores={"DATA_MODEL": 0.9})
        cr = ConfidenceResult(mapping=mapping, confidence="HIGH", top_score=0.9, needs_review=False)
        presentations = present_mapping([cr])
        text = format_mapping_for_telegram(presentations)
        assert "DATA_MODEL" in text
        assert "Schema" in text
        assert "Approve" in text
