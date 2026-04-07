"""Tests for cost_tracker.py — TASK-004."""

import pytest

from planner import cost_tracker


@pytest.fixture
def empty_state():
    return {
        "cost": {
            "total_usd": 0.0,
            "by_model": {},
            "by_phase": {},
            "by_document": {},
        }
    }


class TestComputeCost:
    def test_opus_cost(self):
        # 1000 tokens in ($5/M) + 500 tokens out ($25/M)
        cost = cost_tracker.compute_cost("claude-opus-4-6", 1000, 500)
        expected = (1000 / 1e6) * 5.0 + (500 / 1e6) * 25.0
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_gpt_cost(self):
        cost = cost_tracker.compute_cost("gpt-5.4", 10000, 5000)
        expected = (10000 / 1e6) * 2.0 + (5000 / 1e6) * 10.0
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_gemini_cost(self):
        cost = cost_tracker.compute_cost("gemini-3.1-pro", 10000, 5000)
        expected = (10000 / 1e6) * 2.0 + (5000 / 1e6) * 12.0
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="No pricing for model"):
            cost_tracker.compute_cost("unknown-model", 100, 100)

    def test_zero_tokens(self):
        assert cost_tracker.compute_cost("claude-opus-4-6", 0, 0) == 0.0


class TestLogCall:
    def test_basic_log(self, empty_state):
        record = cost_tracker.log_call(
            empty_state, "claude-opus-4-6", 1000, 500, 2.5, "1", "CONSTITUTION.md"
        )
        assert record["model"] == "claude-opus-4-6"
        assert record["tokens_in"] == 1000
        assert record["tokens_out"] == 500
        assert record["cost_usd"] > 0
        assert record["duration_seconds"] == 2.5
        assert record["phase"] == "1"
        assert record["document"] == "CONSTITUTION.md"

    def test_accumulates_total(self, empty_state):
        cost_tracker.log_call(empty_state, "claude-opus-4-6", 1000, 500, 1.0, "1")
        cost_tracker.log_call(empty_state, "claude-opus-4-6", 1000, 500, 1.0, "1")
        assert empty_state["cost"]["total_usd"] > 0
        single_cost = cost_tracker.compute_cost("claude-opus-4-6", 1000, 500)
        assert empty_state["cost"]["total_usd"] == pytest.approx(single_cost * 2)

    def test_accumulates_by_model(self, empty_state):
        cost_tracker.log_call(empty_state, "claude-opus-4-6", 1000, 500, 1.0, "1")
        cost_tracker.log_call(empty_state, "gpt-5.4", 1000, 500, 1.0, "3")
        assert "claude-opus-4-6" in empty_state["cost"]["by_model"]
        assert "gpt-5.4" in empty_state["cost"]["by_model"]

    def test_accumulates_by_phase(self, empty_state):
        cost_tracker.log_call(empty_state, "claude-opus-4-6", 1000, 500, 1.0, "1")
        cost_tracker.log_call(empty_state, "claude-opus-4-6", 1000, 500, 1.0, "3")
        assert "1" in empty_state["cost"]["by_phase"]
        assert "3" in empty_state["cost"]["by_phase"]

    def test_accumulates_by_document(self, empty_state):
        cost_tracker.log_call(
            empty_state, "claude-opus-4-6", 1000, 500, 1.0, "1", "DOC_A.md"
        )
        cost_tracker.log_call(
            empty_state, "claude-opus-4-6", 1000, 500, 1.0, "1", "DOC_A.md"
        )
        single = cost_tracker.compute_cost("claude-opus-4-6", 1000, 500)
        assert empty_state["cost"]["by_document"]["DOC_A.md"] == pytest.approx(single * 2)

    def test_no_document(self, empty_state):
        cost_tracker.log_call(empty_state, "claude-opus-4-6", 1000, 500, 1.0, "0")
        assert empty_state["cost"]["by_document"] == {}


class TestGetSummary:
    def test_summary_structure(self, empty_state):
        summary = cost_tracker.get_summary(empty_state)
        assert "total_usd" in summary
        assert "by_model" in summary
        assert "by_phase" in summary
        assert "by_document" in summary
        assert "alerts" in summary

    def test_no_alerts_under_threshold(self, empty_state):
        summary = cost_tracker.get_summary(empty_state)
        assert summary["alerts"] == []

    def test_alert_at_threshold(self, empty_state):
        empty_state["cost"]["total_usd"] = 30.0
        summary = cost_tracker.get_summary(empty_state)
        assert len(summary["alerts"]) == 1
        assert "ALERT" in summary["alerts"][0]

    def test_hard_limit_alert(self, empty_state):
        empty_state["cost"]["total_usd"] = 50.0
        summary = cost_tracker.get_summary(empty_state)
        assert len(summary["alerts"]) == 1
        assert "HARD LIMIT" in summary["alerts"][0]


class TestAlertChecks:
    def test_should_alert(self, empty_state):
        assert not cost_tracker.should_alert(empty_state)
        empty_state["cost"]["total_usd"] = 30.0
        assert cost_tracker.should_alert(empty_state)

    def test_should_hard_stop(self, empty_state):
        assert not cost_tracker.should_hard_stop(empty_state)
        empty_state["cost"]["total_usd"] = 50.0
        assert cost_tracker.should_hard_stop(empty_state)


class TestPricingConfig:
    def test_pricing_loadable(self):
        pricing = cost_tracker._load_pricing()
        assert "models" in pricing
        assert "alert_threshold_usd" in pricing
        assert "hard_limit_usd" in pricing

    def test_all_models_have_pricing(self):
        pricing = cost_tracker._load_pricing()
        for model, data in pricing["models"].items():
            assert "input_per_million" in data
            assert "output_per_million" in data
            assert "provider" in data
