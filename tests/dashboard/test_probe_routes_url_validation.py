"""POST /api/probe/start — base_url validation (scheme/host/IP)."""
from __future__ import annotations

from ._probe_routes_helpers import _invoke_post


class TestStartRouteUrlValidation:
    def test_returns_400_when_base_url_scheme_not_http(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "ftp://x.com", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "scheme" in body["error"]

    def test_returns_400_when_base_url_has_userinfo(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "https://u:p@x.com", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "userinfo" in body["error"]

    def test_returns_400_when_base_url_missing_host(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "https://", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "missing host" in body["error"]

    def test_returns_400_when_base_url_is_localhost(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://localhost", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "loopback" in body["error"]

    def test_returns_400_when_base_url_is_loopback_ip(self, handler_factory):
        handler_cls, _paths = handler_factory
        for url in ("http://127.0.0.1", "http://[::1]"):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": url, "target_kind": "local_lab"},
            )
            assert status == 400, f"expected 400 for {url}, got {status}"
            assert "private/reserved" in body["error"] or "loopback" in body["error"]

    def test_returns_400_when_base_url_is_imds(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://169.254.169.254", "target_kind": "local_lab"},
        )
        assert status == 400
        assert "private/reserved" in body["error"]

    def test_returns_400_when_base_url_is_private_v4(self, handler_factory):
        handler_cls, _paths = handler_factory
        for ip in ("10.0.0.5", "172.16.0.1", "192.168.1.1"):
            status, body = _invoke_post(
                handler_cls,
                "/api/probe/start",
                {"base_url": f"http://{ip}", "target_kind": "local_lab"},
            )
            assert status == 400, f"expected 400 for {ip}, got {status}"
            assert "private/reserved" in body["error"]

    def test_returns_400_when_base_url_is_unspecified(self, handler_factory):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://0.0.0.0", "target_kind": "local_lab"},
        )
        assert status == 400

    def test_hostname_that_resolves_locally_passes_route_check(
        self, handler_factory,
    ):
        handler_cls, _paths = handler_factory
        status, _body = _invoke_post(
            handler_cls,
            "/api/probe/start",
            {"base_url": "http://target.cocode.dk", "target_kind": "local_lab"},
        )
        assert status == 200
