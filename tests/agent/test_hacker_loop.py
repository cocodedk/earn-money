"""Tests for HackerLoop — core action dispatch + budget + max-turns.

Hook, prompt, provider, stop-validation and skiplist tests live in the
sibling test_hacker_loop_*.py files.
"""
from ._test_hacker_loop_helpers import _j, _loop


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
            _j(tool="post", category="http_post", args={"path": "/login", "json": {}}),
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
