"""Response-format model-skiplist tests.

Some models (notably qwen/qwen3-235b-a22b) emit JSON garbage when
`response_format` is on. The skiplist lets the helper save the wasted
first call entirely; the retry-on-failure path still applies for
every other model.
"""
from unittest.mock import MagicMock

from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
from earn_money.agent.task_router import TaskType

from ._test_hacker_loop_helpers import _j, _loop


class TestResponseFormatSkiplist:
    """Some models (notably qwen/qwen3-235b-a22b) emit JSON garbage when
    `response_format` is on. The skiplist lets the helper save the wasted
    first call entirely; the retry-on-failure path still applies for
    every other model."""

    def test_skiplisted_model_skips_response_format_on_first_call(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "qwen/qwen3-235b-a22b")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is False
        assert len(provider.complete.call_args_list) == 1
        assert "response_format" not in provider.complete.call_args.kwargs

    def test_non_skiplisted_model_still_tries_response_format_first(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "anthropic/claude-3-5-sonnet")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is True
        assert provider.complete.call_args.kwargs.get("response_format") == {"type": "json_object"}

    def test_skiplist_is_env_overridable(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "anthropic/claude-3-5-sonnet")
        monkeypatch.setenv("LLM_DISABLE_RESPONSE_FORMAT_MODELS", "anthropic/claude-3-5-sonnet")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is False

    def test_unconfigured_router_does_not_break_skiplist_check(self, monkeypatch):
        """Most tests use a MagicMock provider with no env-configured model.
        resolve_model() raises RouterUnconfigured; the skiplist check must
        swallow it gracefully and fall through to normal rf-on behavior."""
        monkeypatch.delenv("OPENROUTER_MODEL_AGENT_PLANNING", raising=False)
        monkeypatch.delenv("LLM_DEFAULT_MODEL", raising=False)
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is True

    def test_skiplisted_garbage_returns_invalid_action_no_retry(self, monkeypatch):
        """Integration: model is skiplisted → with_response_format forced
        to False → first call returns garbage → run() sees used_rf=False,
        skips the parse-retry, exits invalid_action. Exactly one provider
        call (not two)."""
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "qwen/qwen3-235b-a22b")
        loop = _loop(["{"])
        result = loop.run()
        assert result.stop_reason == "invalid_action"
        assert len(loop.provider.complete.call_args_list) == 1

    # ── exact-match (no prefix / substring matching) ──────────────────────

    def test_suffix_variant_does_not_match(self, monkeypatch):
        """`qwen/qwen3-235b-a22b:free` is a distinct model ID and must
        NOT be caught by the default skiplist for the unsuffixed version."""
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "qwen/qwen3-235b-a22b:free")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is True

    def test_other_qwen_variant_does_not_match(self, monkeypatch):
        """A different qwen model (qwen-2.5-72b) is not on the skiplist
        and must keep the rf-on first call."""
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "qwen/qwen-2.5-72b-instruct")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is True

    # ── env-var override edge cases ───────────────────────────────────────

    def test_custom_comma_separated_list_works(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "model-b")
        monkeypatch.setenv("LLM_DISABLE_RESPONSE_FORMAT_MODELS", "model-a,model-b,model-c")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is False

    def test_empty_env_var_disables_default_skiplist(self, monkeypatch):
        """Setting the env var to an empty string overrides the built-in
        default (which contains qwen/qwen3-235b-a22b) to an empty skiplist."""
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "qwen/qwen3-235b-a22b")
        monkeypatch.setenv("LLM_DISABLE_RESPONSE_FORMAT_MODELS", "")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is True

    def test_whitespace_in_env_var_is_stripped(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "model-b")
        monkeypatch.setenv(
            "LLM_DISABLE_RESPONSE_FORMAT_MODELS",
            "  model-a  ,\tmodel-b  ,  model-c\n",
        )
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is False

    # ── observability: one log line per skiplist decision ─────────────────

    def test_log_emitted_when_skiplist_disables_rf(self, monkeypatch, caplog):
        """Every time the skiplist forces rf-off, one INFO log line is
        emitted with model + reason. Lets the operator audit why a call
        skipped response_format in production."""
        import logging as _logging
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "qwen/qwen3-235b-a22b")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        with caplog.at_level(_logging.INFO, logger="earn_money.agent.hacker_loop"):
            _call_provider_with_rf_fallback(
                provider, system="s", user="u",
                task=TaskType.AGENT_PLANNING, with_response_format=True,
            )
        msgs = [r.message for r in caplog.records if "response_format=disabled" in r.message]
        assert len(msgs) == 1
        assert "qwen/qwen3-235b-a22b" in msgs[0]
        assert "model_skiplist" in msgs[0]

    def test_no_skiplist_log_for_non_skiplisted_model(self, monkeypatch, caplog):
        import logging as _logging
        monkeypatch.setenv("OPENROUTER_MODEL_AGENT_PLANNING", "anthropic/claude-3-5-sonnet")
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        with caplog.at_level(_logging.INFO, logger="earn_money.agent.hacker_loop"):
            _call_provider_with_rf_fallback(
                provider, system="s", user="u",
                task=TaskType.AGENT_PLANNING, with_response_format=True,
            )
        assert not any("response_format=disabled" in r.message for r in caplog.records)
