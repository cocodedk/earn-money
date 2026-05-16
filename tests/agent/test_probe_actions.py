"""Tests for typed LLM action schema."""

import json

import pytest

from earn_money.agent.probe_actions import (
    ActionParseError,
    GetAction,
    PostAction,
    ReportCandidateAction,
    SetHeaderAction,
    StopAction,
    StoreAction,
    parse_action,
)


def _j(**kwargs: object) -> str:
    return json.dumps(kwargs)


class TestParseAction:
    def test_valid_get(self):
        raw = _j(tool="get", category="http_get", args={"path": "/api/users"})
        action = parse_action(raw)
        assert isinstance(action, GetAction)
        assert action.args.path == "/api/users"

    def test_valid_post(self):
        raw = _j(
            tool="post", category="http_post",
            args={"path": "/login", "json": {"email": "a@b.com"}},
        )
        action = parse_action(raw)
        assert isinstance(action, PostAction)

    def test_valid_set_header(self):
        raw = _j(
            tool="set_header", category="auth",
            args={"name": "Authorization", "value": "Bearer tok"},
        )
        action = parse_action(raw)
        assert isinstance(action, SetHeaderAction)
        assert action.args.name == "Authorization"

    def test_valid_store(self):
        raw = _j(
            tool="store", category="store_memory",
            args={"kind": "token", "key": "access", "value": "abc"},
        )
        action = parse_action(raw)
        assert isinstance(action, StoreAction)

    def test_valid_report_candidate(self):
        raw = _j(
            tool="report_candidate",
            category="report_candidate",
            args={
                "signal_type": "idor", "target": "/api/users/999",
                "evidence": "...", "confidence": "medium",
            },
        )
        action = parse_action(raw)
        assert isinstance(action, ReportCandidateAction)

    def test_valid_stop(self):
        raw = _j(tool="stop", category="stop", args={"reason": "done"})
        action = parse_action(raw)
        assert isinstance(action, StopAction)

    def test_invalid_json_fails(self):
        with pytest.raises(ActionParseError, match="Invalid JSON"):
            parse_action("{not valid json")

    def test_unknown_tool_fails(self):
        with pytest.raises(ActionParseError, match="Unknown tool"):
            parse_action(_j(tool="launch_missiles", category="bad", args={}))

    def test_unknown_category_fails(self):
        # Wrong category for the tool causes validation error
        with pytest.raises(ActionParseError):
            parse_action(_j(tool="get", category="http_post", args={"path": "/foo"}))

    def test_extra_field_fails(self):
        with pytest.raises(ActionParseError):
            parse_action(
                _j(tool="get", category="http_get", args={"path": "/foo"}, secret="leaked")
            )

    def test_shell_command_fails(self):
        # shell commands are not a valid tool
        with pytest.raises(ActionParseError, match="Unknown tool"):
            parse_action(_j(tool="shell", category="exec", args={"cmd": "rm -rf /"}))

    def test_base_url_override_fails(self):
        # Trying to set base_url in args should fail (extra field)
        with pytest.raises(ActionParseError):
            parse_action(_j(tool="get", category="http_get", args={"path": "/foo", "base_url": "http://evil.com"}))

    def test_get_params_accepted(self):
        raw = _j(tool="get", category="http_get", args={"path": "/search", "params": {"q": "test"}})
        action = parse_action(raw)
        assert isinstance(action, GetAction)
        assert action.args.params == {"q": "test"}
