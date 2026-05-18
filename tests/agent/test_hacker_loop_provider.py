"""Tests for HackerLoop ↔ provider helper (response_format fallback)."""
import json
from unittest.mock import MagicMock

from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
from earn_money.agent.task_router import TaskType

from ._test_hacker_loop_helpers import _j, _loop, _provider_error


class TestResponseFormatPassthrough:
    def test_passes_json_object_response_format_to_provider(self):
        loop = _loop([json.dumps(
            {"tool": "stop", "category": "stop", "args": {"reason": "done"}},
        )])
        loop.run()
        kwargs = loop.provider.complete.call_args.kwargs
        assert kwargs.get("response_format") == {"type": "json_object"}

    def test_retries_without_response_format_when_first_provider_call_fails(self):
        # First provider.complete raises (model rejects response_format);
        # second call must omit response_format and succeed.
        loop = _loop([])  # _loop wires provider.complete.side_effect manually
        loop.provider.complete.side_effect = [
            _provider_error("response_format unsupported", status=400),
            json.dumps({"tool": "stop", "category": "stop", "args": {"reason": "done"}}),
        ]
        result = loop.run()
        assert result.stop_reason == "done"
        calls = loop.provider.complete.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs.get("response_format") == {"type": "json_object"}
        assert "response_format" not in calls[1].kwargs

    def test_retries_without_response_format_when_first_parse_fails(self):
        # First provider call succeeds but returns garbage (e.g. model
        # returns half-JSON when response_format is on). Loop must retry
        # ONCE without response_format and accept a valid action.
        loop = _loop([])
        loop.provider.complete.side_effect = [
            "{",  # parses_action_with_recovery raises ActionParseError
            json.dumps({"tool": "stop", "category": "stop", "args": {"reason": "done"}}),
        ]
        result = loop.run()
        assert result.stop_reason == "done"
        calls = loop.provider.complete.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs.get("response_format") == {"type": "json_object"}
        assert "response_format" not in calls[1].kwargs

    def test_invalid_action_after_retry_also_fails(self):
        # First parse fails, retry-without-response_format also returns
        # garbage. No third call; loop exits with invalid_action.
        loop = _loop([])
        loop.provider.complete.side_effect = [
            "{",
            "encoding/json",
        ]
        result = loop.run()
        assert result.stop_reason == "invalid_action"
        assert len(loop.provider.complete.call_args_list) == 2

    def test_no_parse_retry_when_response_format_was_already_off(self):
        # If the first provider call raises and the in-method fallback
        # (without response_format) returns garbage, the parse-retry
        # path MUST skip — retrying with the same kwargs would just
        # repeat the garbage. Exactly two calls.
        loop = _loop([])
        loop.provider.complete.side_effect = [
            _provider_error("response_format unsupported", status=400),
            "{still garbage",
        ]
        result = loop.run()
        assert result.stop_reason == "invalid_action"
        assert len(loop.provider.complete.call_args_list) == 2


class TestProviderHelper:
    def test_returns_used_response_format_true_when_rf_succeeds(self):
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert raw.startswith("{")
        assert used_rf is True
        assert provider.complete.call_args.kwargs.get("response_format") == {"type": "json_object"}

    def test_returns_used_response_format_false_when_caller_passes_false(self):
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=False,
        )
        assert used_rf is False
        assert "response_format" not in provider.complete.call_args.kwargs

    def test_returns_used_response_format_false_when_rf_call_raises(self):
        """HTTP 400 from the model adapter means it rejected `response_format`.
        Helper retries without the kwarg and the second call succeeds."""
        provider = MagicMock()
        rf_reject = _provider_error("response_format unsupported", status=400)
        provider.complete.side_effect = [
            rf_reject,
            _j(tool="stop", category="stop", args={}),
        ]
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is False
        assert raw is not None
        assert len(provider.complete.call_args_list) == 2

    def test_402_does_not_trigger_retry(self, caplog):
        """HTTP 402 (out of credit on OpenRouter) is not fixable by dropping
        response_format. Helper must NOT retry — return (None, False) so the
        loop fails cleanly instead of burning a second doomed call."""
        import logging as _logging
        provider = MagicMock()
        provider.complete.side_effect = _provider_error(
            "402 - requires more credits", status=402,
        )
        with caplog.at_level(_logging.ERROR, logger="earn_money.agent.hacker_loop"):
            raw, used_rf = _call_provider_with_rf_fallback(
                provider, system="s", user="u",
                task=TaskType.AGENT_PLANNING, with_response_format=True,
            )
        assert raw is None
        assert used_rf is False
        assert len(provider.complete.call_args_list) == 1
        assert any("status=402" in r.message for r in caplog.records)

    def test_401_does_not_trigger_retry(self):
        provider = MagicMock()
        provider.complete.side_effect = _provider_error("unauthorized", status=401)
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert raw is None and used_rf is False
        assert len(provider.complete.call_args_list) == 1

    def test_429_does_not_trigger_retry(self):
        provider = MagicMock()
        provider.complete.side_effect = _provider_error("rate limit", status=429)
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert raw is None and used_rf is False
        assert len(provider.complete.call_args_list) == 1

    def test_unknown_status_does_not_trigger_retry(self):
        """An exception with no `status_code` attribute (transport blip,
        timeout, non-HTTP error) is treated conservatively: don't retry."""
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("connection reset")
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert raw is None and used_rf is False
        assert len(provider.complete.call_args_list) == 1
