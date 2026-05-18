"""POST /api/probe/start — happy paths + flags/freeze + 409/500/clear.

URL-validation, field-validation, stream, dispatch, and current-route
tests live in the sibling test_probe_routes_*.py files.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from earn_money import config, flags

from ._probe_routes_helpers import (
    _BASE,
    _FakeRunner,
    _invoke_post,
    _invoke_post_raw,
)


class TestStartRoute:
    def test_returns_200_with_run_id_on_success(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 200
        assert body == {"run_id": "fakerun123"}

    def test_returns_400_when_base_url_missing(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls, "/api/probe/start", {"target_kind": "local_lab"},
        )
        assert status == 400
        assert "base_url required" in body["error"]

    def test_returns_400_when_body_is_invalid_json(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post_raw(
            handler_cls, "/api/probe/start", b"{not-json",
        )
        assert status == 400
        assert "invalid JSON body" in body["error"]

    def test_returns_400_when_roe_profile_path_does_not_exist(
        self, handler_factory,
    ):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "roe_profile": "/nope.yaml"},
        )
        assert status == 400
        assert "RoE profile not found" in body["error"]

    def test_empty_string_roe_profile_treated_as_null(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab", "roe_profile": ""},
        )
        assert status == 200

    def test_relative_roe_path_resolved_against_root(
        self, handler_factory, tmp_root: Path,
    ):
        handler_cls, _paths = handler_factory
        roe_dir = tmp_root / "roe"
        roe_dir.mkdir()
        (roe_dir / "test.yaml").write_text("# dummy roe", encoding="utf-8")
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {
                "base_url": _BASE,
                "target_kind": "local_lab",
                "roe_profile": "roe/test.yaml",
            },
        )
        assert status == 200

    def test_returns_403_when_recon_enabled_absent(
        self, tmp_path: Path,
    ):
        from earn_money.dashboard import server
        paths = config.Paths.from_root(tmp_path)  # no RECON_ENABLED created
        with patch.object(server, "ProbeRunner", _FakeRunner, create=True):
            handler_cls = server._make_handler(
                paths, b"<!doctype html>", {},
            )
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 403
        assert "RECON_ENABLED" in body["error"]

    def test_returns_403_when_registered_program_frozen(
        self, handler_factory, tmp_root: Path,
    ):
        handler_cls, paths = handler_factory
        flags.freeze_program(paths, "local", "frozen-prog", reason="test")
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {
                "base_url": _BASE,
                "target_kind": "registered_program",
                "program": "frozen-prog",
            },
        )
        assert status == 403
        assert "frozen" in body["error"].lower()

    def test_does_not_check_frozen_for_local_lab(
        self, handler_factory, tmp_root: Path,
    ):
        handler_cls, paths = handler_factory
        flags.freeze_program(paths, "local", "frozen-prog", reason="test")
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {
                "base_url": _BASE,
                "target_kind": "local_lab",
                "program": "frozen-prog",
            },
        )
        assert status == 200

    def test_returns_409_when_another_probe_is_running(self, handler_factory):
        handler_cls, _paths = handler_factory
        _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert status == 409
        assert body["error"] == "another probe is running"

    def test_409_payload_includes_existing_run_id(self, handler_factory):
        handler_cls, _paths = handler_factory
        _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        _status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert body["run_id"] == "fakerun123"

    def test_returns_500_when_runner_construction_raises(
        self, handler_factory,
    ):
        from earn_money.dashboard import server

        handler_cls, _paths = handler_factory

        def raising_factory(*_args, **_kwargs):
            raise RuntimeError("boom")

        with patch.object(server, "ProbeRunner", raising_factory):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": _BASE, "target_kind": "local_lab"},
            )
        assert status == 500
        assert "runner init failed" in body["error"]

    def test_clear_probe_slot_clears_matching_finished_runner_when_called_directly(
        self, handler_factory,
    ):
        from earn_money.dashboard import server

        handler_cls, _paths = handler_factory
        _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": _BASE, "target_kind": "local_lab"},
        )
        assert server._PROBE_SLOT is not None
        run_id = server._PROBE_SLOT.run_id()
        server._clear_probe_slot(run_id)
        assert server._PROBE_SLOT is None
