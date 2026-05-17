"""Tests for HackerLoop."""

import json
from unittest.mock import MagicMock

from earn_money.agent.budget import RequestBudget
from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_loop import HackerLoop
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
from earn_money.agent.scope_policy import ScopePolicy


def _profile(**kwargs: object) -> RoeProfile:
    defaults = dict(
        name="test",
        source_type=RoeSourceType.MANUAL,
        allowed_hosts=["target.example.com"],
        max_requests=100,
        max_posts=20,
        max_turns=10,
        max_runtime_seconds=60,
        max_response_bytes=5000,
        delay_between_requests_ms=0,
        allow_get=True,
        allow_post=True,
        allow_idor_checks=True,
    )
    defaults.update(kwargs)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


def _obs(status: int = 200, body: str = "ok") -> ObservationWrapper:
    return ObservationWrapper.from_response(status, "https://target.example.com/api", {}, body)


def _loop(provider_responses: list[str], **profile_kwargs: object) -> HackerLoop:
    profile = _profile(**profile_kwargs)
    roe_policy = RoePolicy(profile)
    ScopePolicy(profile, "https://target.example.com")
    budget = RequestBudget(profile)
    session = HackerSession()
    verifier = FindingVerifier(profile)

    http_tool = MagicMock(spec=HttpTool)
    http_tool.get.return_value = _obs()
    http_tool.post.return_value = _obs()
    http_tool.budget = budget

    provider = MagicMock()
    responses = iter(provider_responses)
    provider.complete.side_effect = lambda **kw: next(responses)

    return HackerLoop(profile, roe_policy, http_tool, budget, session, verifier, provider)


def _j(**kwargs: object) -> str:
    return json.dumps(kwargs)


class TestHackerLoop:
    def test_loop_stops_on_stop(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        result = loop.run()
        assert result.stop_reason == "done"
        assert result.turns == 1

    def test_loop_calls_http_for_get(self):
        loop = _loop([
            _j(tool="get", category="http_get", args={"path": "/api/users"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ])
        loop.run()
        loop.http_tool.get.assert_called_once_with("/api/users", None)

    def test_loop_calls_http_for_post_when_roe_allows(self):
        loop = _loop([
            _j(tool="post", category="http_post",
               args={"path": "/login", "json": {"email": "a@b.com"}}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ])
        loop.run()
        loop.http_tool.post.assert_called_once()

    def test_loop_denies_post_when_roe_forbids(self):
        loop = _loop([
            _j(tool="post", category="http_post", args={"path": "/login", "json": {}}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ], allow_post=False)
        result = loop.run()
        assert any("POST" in d for d in result.policy_denials)

    def test_loop_sets_header(self):
        loop = _loop([
            _j(tool="set_header", category="auth",
               args={"name": "Authorization", "value": "Bearer tok"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ], allow_authenticated_testing=True)
        loop.run()
        loop.http_tool.set_header.assert_called_once_with("Authorization", "Bearer tok")

    def test_loop_stores_token(self):
        loop = _loop([
            _j(tool="store", category="store_memory",
               args={"kind": "token", "key": "access", "value": "tok"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ])
        loop.run()
        assert loop.session.get_token("access") == "tok"

    def test_loop_stores_id(self):
        loop = _loop([
            _j(tool="store", category="store_memory",
               args={"kind": "id", "key": "user_id", "value": "42"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ])
        loop.run()
        assert loop.session.ids["user_id"] == "42"

    def test_loop_reports_candidate(self):
        loop = _loop([
            _j(tool="report_candidate", category="report_candidate",
               args={"signal_type": "idor", "target": "/api/users/999",
                     "evidence": "got data", "confidence": "medium"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ])
        result = loop.run()
        assert len(result.candidate_findings) >= 1

    def test_loop_fails_closed_on_invalid_json(self):
        # Two garbage responses: the loop retries once without
        # response_format on parse failure, so both calls must return
        # garbage to drive the fail-closed path.
        loop = _loop(["{not valid json", "{still not valid"])
        result = loop.run()
        assert result.stop_reason == "invalid_action"

    def test_loop_fails_closed_on_unknown_action(self):
        bad = _j(tool="launch_missiles", category="bad", args={})
        loop = _loop([bad, bad])
        result = loop.run()
        assert result.stop_reason == "invalid_action"

    def test_loop_logs_turns(self):
        loop = _loop([
            _j(tool="get", category="http_get", args={"path": "/api"}),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ])
        loop.run()
        assert len(loop.session.turn_log) >= 1

    def test_loop_stores_policy_denials(self):
        loop = _loop([
            _j(tool="post", category="http_post", args={"path": "/login", "json": {}}),
            _j(tool="post", category="http_post", args={"path": "/login", "json": {}}),
            _j(tool="post", category="http_post", args={"path": "/login", "json": {}}),
        ], allow_post=False)
        result = loop.run()
        assert len(result.policy_denials) >= 1

    def test_loop_stops_at_max_turns(self):
        responses = [_j(tool="get", category="http_get", args={"path": "/api"})] * 20
        loop = _loop(responses, max_turns=3)
        result = loop.run()
        assert result.stop_reason == "max_turns"
        assert result.turns <= 3

    def test_loop_stops_after_three_repeated_denied_actions(self):
        denied_actions = [
            _j(tool="post", category="http_post", args={"path": "/login", "json": {}})
        ] * 5
        loop = _loop(denied_actions, allow_post=False)
        result = loop.run()
        assert result.stop_reason == "repeated_denials"

    def test_loop_includes_roe_summary_in_prompt(self):
        captured: list[str] = []
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])

        def capture(**kw: object) -> str:
            captured.append(str(kw.get("user", "")))
            return next(iter([_j(tool="stop", category="stop", args={"reason": "done"})]))
        loop.provider.complete.side_effect = capture

        loop.run()
        assert captured
        assert "RoE Profile" in captured[0]


class TestHooks:
    def test_on_action_parsed_fires_after_parsing(self):
        from earn_money.agent.probe_actions import StopAction
        # Reuse the existing _loop fixture defined at module scope.
        loop = _loop([json.dumps(
            {"tool": "stop", "category": "stop", "args": {"reason": "done"}}
        )])
        seen: list[tuple[int, object, bool]] = []
        loop._on_action_parsed = (  # type: ignore[method-assign]
            lambda turn, action, parse_recovered, **_k: seen.append(
                (turn, action.__class__, parse_recovered)
            )
        )
        loop.run()
        assert seen and seen[0][1] is StopAction
        assert seen[0][2] is False

    def test_hook_ordering_pending_then_parsed_then_policy(self):
        loop = _loop([json.dumps(
            {"tool": "get", "category": "http_get", "args": {"path": "/api/users"}}
        ), json.dumps(
            {"tool": "stop", "category": "stop", "args": {"reason": "done"}}
        )])
        sequence: list[str] = []
        loop._on_llm_response    = lambda *_a, **_k: sequence.append("llm")        # type: ignore[method-assign]
        loop._on_action_parsed   = lambda *_a, **_k: sequence.append("parsed")     # type: ignore[method-assign]
        loop._on_policy_decision = lambda *_a, **_k: sequence.append("policy")     # type: ignore[method-assign]
        loop._on_observation     = lambda *_a, **_k: sequence.append("obs")        # type: ignore[method-assign]
        loop._on_turn_complete   = lambda *_a, **_k: sequence.append("complete")   # type: ignore[method-assign]
        loop.run()
        assert sequence[:5] == ["llm", "parsed", "policy", "obs", "complete"]


class TestResponseFormatPassthrough:
    def test_passes_json_object_response_format_to_provider(self):
        loop = _loop([json.dumps(
            {"tool": "stop", "category": "stop", "args": {"reason": "done"}}
        )])
        loop.run()
        kwargs = loop.provider.complete.call_args.kwargs
        assert kwargs.get("response_format") == {"type": "json_object"}

    def test_retries_without_response_format_when_first_provider_call_fails(self):
        # First provider.complete raises (model rejects response_format);
        # second call must omit response_format and succeed.
        loop = _loop([])  # _loop wires provider.complete.side_effect manually
        loop.provider.complete.side_effect = [
            RuntimeError("response_format unsupported"),
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
            RuntimeError("response_format unsupported"),
            "{still garbage",
        ]
        result = loop.run()
        assert result.stop_reason == "invalid_action"
        assert len(loop.provider.complete.call_args_list) == 2


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
        assert kw["system"].startswith("You are assisting with authorized security testing.")

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
            RuntimeError("response_format unsupported"),
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


class TestProviderHelper:
    def test_returns_used_response_format_true_when_rf_succeeds(self):
        from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
        from earn_money.agent.task_router import TaskType
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
        from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
        from earn_money.agent.task_router import TaskType
        provider = MagicMock()
        provider.complete.return_value = _j(tool="stop", category="stop", args={})
        _raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=False,
        )
        assert used_rf is False
        assert "response_format" not in provider.complete.call_args.kwargs

    def test_returns_used_response_format_false_when_rf_call_raises(self):
        from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
        from earn_money.agent.task_router import TaskType
        provider = MagicMock()
        provider.complete.side_effect = [
            RuntimeError("response_format unsupported"),
            _j(tool="stop", category="stop", args={}),
        ]
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is False
        assert raw is not None
