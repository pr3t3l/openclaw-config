"""Tests for model_gateway.py — TASK-005."""

import pytest

from planner.model_gateway import (
    DegradedModeError,
    ModelCallError,
    ModelGateway,
    ProviderError,
    RateLimitError,
)


def _make_state():
    return {
        "cost": {
            "total_usd": 0.0,
            "by_model": {},
            "by_phase": {},
            "by_document": {},
        }
    }


def _mock_call_fn(model, messages, max_tokens, temperature):
    """Simple mock that returns a valid response."""
    return {
        "content": f"Response from {model}",
        "tokens_in": 100,
        "tokens_out": 50,
    }


class TestCallModel:
    def test_successful_call(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        result = gw.call_model("primary", "Hello", phase="1")
        assert result["content"] == "Response from claude-opus-4-6"
        assert result["model"] == "claude-opus-4-6"
        assert result["tokens_in"] == 100
        assert result["tokens_out"] == 50
        assert result["cost_usd"] > 0
        assert result["duration"] > 0

    def test_cost_tracked_in_state(self):
        state = _make_state()
        gw = ModelGateway(state, call_fn=_mock_call_fn)
        gw.call_model("primary", "Hello", phase="1", document="DOC.md")
        assert state["cost"]["total_usd"] > 0
        assert "claude-opus-4-6" in state["cost"]["by_model"]
        assert "1" in state["cost"]["by_phase"]
        assert "DOC.md" in state["cost"]["by_document"]

    def test_model_override(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        result = gw.call_model(
            "primary", "Hello", phase="1", model="gpt-5.4", provider="openai"
        )
        assert result["model"] == "gpt-5.4"

    def test_context_included(self):
        calls = []
        def capture_fn(model, messages, max_tokens, temperature):
            calls.append(messages)
            return {"content": "ok", "tokens_in": 10, "tokens_out": 5}

        gw = ModelGateway(_make_state(), call_fn=capture_fn)
        gw.call_model("primary", "Question", context="System context", phase="1")
        assert len(calls[0]) == 2
        assert calls[0][0]["role"] == "system"
        assert calls[0][1]["role"] == "user"


class TestRoleResolution:
    def test_primary_resolves_to_opus(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        result = gw.call_model("primary", "Hello", phase="1")
        assert result["model"] == "claude-opus-4-6"

    def test_auditor_gpt_resolves(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        result = gw.call_model("auditor_gpt", "Audit this", phase="3")
        assert result["model"] == "gpt-5.4"

    def test_auditor_gemini_resolves(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        result = gw.call_model("auditor_gemini", "Audit this", phase="3")
        assert result["model"] == "gemini-3.1-pro"

    def test_unknown_role_defaults_to_primary(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        result = gw.call_model("unknown_role", "Hello", phase="1")
        assert result["model"] == "claude-opus-4-6"


class TestDegradedMode:
    def test_provider_error_raises_degraded(self):
        call_count = 0
        def failing_fn(model, messages, max_tokens, temperature):
            nonlocal call_count
            call_count += 1
            raise ProviderError("503 Service Unavailable")

        gw = ModelGateway(_make_state(), call_fn=failing_fn)
        with pytest.raises(DegradedModeError):
            gw.call_model("primary", "Hello", phase="1")

    def test_degraded_mode_switches_model(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        gw.enable_degraded_mode()
        result = gw.call_model("primary", "Hello", phase="1")
        assert result["model"] == "gpt-5.4"

    def test_disable_degraded_restores_primary(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        gw.enable_degraded_mode()
        gw.disable_degraded_mode()
        result = gw.call_model("primary", "Hello", phase="1")
        assert result["model"] == "claude-opus-4-6"

    def test_degraded_only_affects_primary(self):
        gw = ModelGateway(_make_state(), call_fn=_mock_call_fn)
        gw.enable_degraded_mode()
        # Auditors should NOT switch
        result = gw.call_model("auditor_gemini", "Audit", phase="3")
        assert result["model"] == "gemini-3.1-pro"


class TestRetries:
    def test_retries_on_generic_error(self):
        call_count = 0
        def flaky_fn(model, messages, max_tokens, temperature):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return {"content": "ok", "tokens_in": 10, "tokens_out": 5}

        gw = ModelGateway(_make_state(), call_fn=flaky_fn)
        result = gw.call_model("auditor_gpt", "Hello", phase="1")
        assert result["content"] == "ok"
        assert call_count == 3

    def test_max_retries_exhausted(self):
        def always_fail(model, messages, max_tokens, temperature):
            raise Exception("Always fails")

        gw = ModelGateway(_make_state(), call_fn=always_fail)
        with pytest.raises(ModelCallError) as exc_info:
            gw.call_model("auditor_gpt", "Hello", phase="1")
        assert exc_info.value.retries == 3  # MAX_RETRIES + 1

    def test_rate_limit_backoff(self):
        call_count = 0
        def rate_limited(model, messages, max_tokens, temperature):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("429")
            return {"content": "ok", "tokens_in": 10, "tokens_out": 5}

        gw = ModelGateway(_make_state(), call_fn=rate_limited)
        result = gw.call_model("auditor_gpt", "Hello", phase="1")
        assert result["content"] == "ok"


class TestJitteredBackoff:
    def test_backoff_increases(self):
        from planner.model_gateway import _jittered_backoff
        delays = [_jittered_backoff(i) for i in range(5)]
        # Should generally increase (with jitter)
        assert delays[-1] > delays[0] or delays[-1] >= 1.0

    def test_backoff_capped(self):
        from planner.model_gateway import _jittered_backoff
        delay = _jittered_backoff(100, max_delay=10.0)
        assert delay <= 10.0
