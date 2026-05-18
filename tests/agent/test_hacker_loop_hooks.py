"""HackerLoop observation-hook tests — pending/parsed/attempt-id/prompt."""
import json

from ._test_hacker_loop_helpers import _j, _loop, _provider_error


class TestHooks:
    def test_on_action_parsed_fires_after_parsing(self):
        from earn_money.agent.probe_actions import StopAction
        # Reuse the existing _loop fixture defined at module scope.
        loop = _loop([json.dumps(
            {"tool": "stop", "category": "stop", "args": {"reason": "done"}},
        )])
        seen: list[tuple[int, object, bool]] = []
        loop._on_action_parsed = (  # type: ignore[method-assign]
            lambda turn, action, parse_recovered, **_k: seen.append(
                (turn, action.__class__, parse_recovered),
            )
        )
        loop.run()
        assert seen and seen[0][1] is StopAction
        assert seen[0][2] is False

    def test_hook_ordering_pending_then_parsed_then_policy(self):
        loop = _loop([json.dumps(
            {"tool": "get", "category": "http_get", "args": {"path": "/api/users"}},
        ), json.dumps(
            {"tool": "stop", "category": "stop", "args": {"reason": "done"}},
        )])
        sequence: list[str] = []
        loop._on_llm_response    = lambda *_a, **_k: sequence.append("llm")        # type: ignore[method-assign]
        loop._on_action_parsed   = lambda *_a, **_k: sequence.append("parsed")     # type: ignore[method-assign]
        loop._on_policy_decision = lambda *_a, **_k: sequence.append("policy")     # type: ignore[method-assign]
        loop._on_observation     = lambda *_a, **_k: sequence.append("obs")        # type: ignore[method-assign]
        loop._on_turn_complete   = lambda *_a, **_k: sequence.append("complete")   # type: ignore[method-assign]
        loop.run()
        assert sequence[:5] == ["llm", "parsed", "policy", "obs", "complete"]


class TestAttemptIdentity:
    def test_action_parsed_carries_attempt_1_when_first_call_parses(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        seen: list[int] = []
        loop._on_action_parsed = (  # type: ignore[method-assign]
            lambda turn, action, parse_recovered, **kw: seen.append(kw["attempt"])
        )
        loop.run()
        assert seen == [1]

    def test_action_parsed_carries_attempt_2_when_retry_recovers(self):
        loop = _loop([])
        loop.provider.complete.side_effect = [
            "{",
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        seen: list[int] = []
        loop._on_action_parsed = (  # type: ignore[method-assign]
            lambda turn, action, parse_recovered, **kw: seen.append(kw["attempt"])
        )
        loop.run()
        assert seen == [2]

    def test_on_action_parse_failed_called_with_attempt_1_when_first_attempt_fails(self):
        loop = _loop([])
        loop.provider.complete.side_effect = [
            "{",
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        seen: list[tuple[int, str]] = []
        loop._on_action_parse_failed = (  # type: ignore[method-assign]
            lambda turn, attempt, error: seen.append((attempt, error))
        )
        loop.run()
        assert len(seen) == 1
        assert seen[0][0] == 1
        assert seen[0][1]

    def test_on_action_parse_failed_called_twice_when_both_attempts_fail(self):
        loop = _loop([])
        loop.provider.complete.side_effect = ["{", "still garbage"]
        seen: list[int] = []
        loop._on_action_parse_failed = (  # type: ignore[method-assign]
            lambda turn, attempt, error: seen.append(attempt)
        )
        loop.run()
        assert seen == [1, 2]

    def test_no_action_parse_failed_on_happy_path(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        seen: list[int] = []
        loop._on_action_parse_failed = (  # type: ignore[method-assign]
            lambda turn, attempt, error: seen.append(attempt)
        )
        loop.run()
        assert seen == []


class TestPromptHook:
    def test_called_with_prompt_and_system_on_first_call(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        seen: list[dict] = []
        loop._on_llm_response = (  # type: ignore[method-assign]
            lambda turn, raw, model_id, **kw: seen.append(kw)
        )
        loop.run()
        assert len(seen) == 1
        kw = seen[0]
        assert kw["attempt"] == 1
        assert kw["used_response_format"] is True
        assert "=== Rules of Engagement ===" in kw["prompt"]
        assert kw["system"].startswith("You are an authorized vulnerability scanning agent.")

    def test_called_twice_on_parse_retry(self):
        loop = _loop([])
        loop.provider.complete.side_effect = [
            "{",
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        seen: list[dict] = []
        loop._on_llm_response = (  # type: ignore[method-assign]
            lambda turn, raw, model_id, **kw: seen.append(kw)
        )
        loop.run()
        assert [s["attempt"] for s in seen] == [1, 2]
        assert [s["used_response_format"] for s in seen] == [True, False]
        assert seen[0]["prompt"] == seen[1]["prompt"]
        assert seen[0]["system"] == seen[1]["system"]

    def test_attempt_2_only_when_retry_fires(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        seen: list[dict] = []
        loop._on_llm_response = (  # type: ignore[method-assign]
            lambda turn, raw, model_id, **kw: seen.append(kw)
        )
        loop.run()
        assert [s["attempt"] for s in seen] == [1]

    def test_attempt_1_used_response_format_false_when_provider_rejects_rf(self):
        loop = _loop([])
        loop.provider.complete.side_effect = [
            _provider_error("response_format unsupported", status=400),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        seen: list[dict] = []
        loop._on_llm_response = (  # type: ignore[method-assign]
            lambda turn, raw, model_id, **kw: seen.append(kw)
        )
        loop.run()
        assert len(seen) == 1
        assert seen[0]["attempt"] == 1
        assert seen[0]["used_response_format"] is False

    def test_llm_error_when_first_call_returns_none(self):
        # 400 triggers retry; both helper calls raise → helper returns
        # (None, False) → run() exits with llm_error.
        loop = _loop([])
        loop.provider.complete.side_effect = [
            _provider_error("a", status=400),
            _provider_error("b", status=400),
        ]
        result = loop.run()
        assert result.stop_reason == "llm_error"

    def test_llm_error_when_retry_call_returns_none(self):
        # First call: garbage triggers parse-retry. Retry call (rf off) raises
        # → helper returns (None, False) → run() exits with llm_error from the
        # second `if raw is None` branch.
        loop = _loop([])
        loop.provider.complete.side_effect = ["{", RuntimeError("retry failed")]
        result = loop.run()
        assert result.stop_reason == "llm_error"
