"""POST /api/probe/start — max_turns / platform / program / target_kind validation."""
from __future__ import annotations

from ._probe_routes_helpers import _BASE, _invoke_post


class TestStartRouteFieldValidation:
    def test_returns_400_when_max_turns_out_of_range(self, handler_factory):
        handler_cls, _paths = handler_factory
        for bad in (0, 10001):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": _BASE, "target_kind": "local_lab", "max_turns": bad},
            )
            assert status == 400, f"expected 400 for max_turns={bad}"
            assert "max_turns" in body["error"]

    def test_returns_400_when_max_turns_is_true(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": True},
        )
        assert status == 400

    def test_returns_400_when_max_turns_is_false(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": False},
        )
        assert status == 400

    def test_returns_400_when_max_turns_is_string(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": "10"},
        )
        assert status == 400

    def test_returns_400_when_max_turns_is_float(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "max_turns": 10.5},
        )
        assert status == 400

    def test_empty_platform_defaults_to_local(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": ""},
        )
        assert status == 200

    def test_null_platform_defaults_to_local(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": None},
        )
        assert status == 200

    def test_empty_program_treated_as_none(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "program": ""},
        )
        assert status == 200

    def test_returns_400_when_platform_is_false(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": False},
        )
        assert status == 400
        assert "platform must be a string" in body["error"]

    def test_returns_400_when_platform_is_zero(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": 0},
        )
        assert status == 400
        assert "platform must be a string" in body["error"]

    def test_returns_400_when_platform_is_list(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "platform": []},
        )
        assert status == 400
        assert "platform must be a string" in body["error"]

    def test_returns_400_when_program_is_list(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "program": []},
        )
        assert status == 400
        assert "program must be a string" in body["error"]

    def test_returns_400_when_program_is_false(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "program": False},
        )
        assert status == 400
        assert "program must be a string" in body["error"]

    def test_requires_target_kind(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE},
        )
        assert status == 400
        assert "target_kind" in body["error"]

    def test_returns_400_when_target_kind_invalid(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "production"},
        )
        assert status == 400
        assert "target_kind" in body["error"]

    def test_allows_missing_program_for_local_lab(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 200

    def test_requires_program_for_registered_program(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "registered_program"},
        )
        assert status == 400
        assert "program required" in body["error"]
