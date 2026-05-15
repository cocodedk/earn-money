"""Tests for auth_bypass_tool — admin path probe and JWT alg:none."""

from __future__ import annotations

import httpx

from earn_money.recon import auth_bypass_tool


def test_probe_service_detects_open_admin_path() -> None:
    body = '[{"id":1,"email":"admin@juice-sh.op","role":"admin","isActive":true}]'

    def _handler(req: httpx.Request) -> httpx.Response:
        if "/api/Users" in str(req.url) and "Authorization" not in req.headers:
            return httpx.Response(
                200, text=body, headers={"content-type": "application/json"},
            )
        return httpx.Response(404, text="not found")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
        )
    open_paths = [s for s in sigs if s.signal_type == "auth_bypass_candidate"]
    assert any("admin_path_open" in s.signature for s in open_paths)


def test_probe_service_detects_jwt_alg_none() -> None:
    def _handler(req: httpx.Request) -> httpx.Response:
        if "/api/Users" in str(req.url) and "Authorization" in req.headers:
            return httpx.Response(
                200, text='[{"id":1,"email":"admin@juice-sh.op"}]',
                headers={"content-type": "application/json"},
            )
        return httpx.Response(401, text="unauthorized")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
            auth_testing_authorized=True,
        )
    jwt_sigs = [s for s in sigs if "jwt_alg_none" in s.signature and "write" not in s.signature]
    assert len(jwt_sigs) >= 1
    assert jwt_sigs[0].tool == "auth-bypass-probe"


def test_probe_service_skips_login_redirects() -> None:
    responses = {"/admin": (302, ""), "/api/Users": (302, "")}

    def _handler(req: httpx.Request) -> httpx.Response:
        for path, (status, body) in responses.items():
            if path in str(req.url):
                return httpx.Response(status, headers={"location": "/login"}, text=body)
        return httpx.Response(404, text="")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_make_alg_none_jwt_produces_unsigned_token() -> None:
    token = auth_bypass_tool._make_alg_none_jwt()
    parts = token.split(".")
    assert len(parts) == 3
    assert parts[2] == ""  # empty signature


def test_probe_service_swallows_http_error() -> None:
    def _fail(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with httpx.Client(transport=httpx.MockTransport(_fail)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
        )
    assert sigs == []


def test_write_probe_detects_bypass_when_both_flags_set() -> None:
    def _handler(req: httpx.Request) -> httpx.Response:
        if req.method == "PUT":
            # Baseline (no JWT): endpoint requires auth
            if "Authorization" not in req.headers:
                return httpx.Response(401, text="Unauthorized")
            # With JWT: auth bypassed, resource absent
            return httpx.Response(404, text='{"message":"Not Found"}')
        return httpx.Response(404, text="not found")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
            auth_testing_authorized=True,
            mutation_testing_authorized=True,
        )
    write_sigs = [s for s in sigs if "jwt_alg_none_write" in s.signature]
    assert len(write_sigs) >= 1
    assert all("status=404" in s.payload for s in write_sigs)


def test_write_probe_skipped_when_auth_testing_not_authorized() -> None:
    def _handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and "/api/Users" in str(req.url):
            return httpx.Response(200, text='[{"id":1}]')
        return httpx.Response(404, text="not found")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
            auth_testing_authorized=False,
        )
    write_sigs = [s for s in sigs if "jwt_alg_none_write" in s.signature]
    assert write_sigs == []


def test_write_probe_skipped_without_mutation_authorized() -> None:
    def _handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
            auth_testing_authorized=True,
            mutation_testing_authorized=False,
        )
    write_sigs = [s for s in sigs if "jwt_alg_none_write" in s.signature]
    assert write_sigs == []


def test_write_probe_no_signal_when_baseline_not_auth_gated() -> None:
    """404 from unauthenticated PUT means route doesn't require auth — not a bypass."""
    def _handler(req: httpx.Request) -> httpx.Response:
        if req.method == "PUT":
            return httpx.Response(404, text="not found")
        return httpx.Response(404, text="not found")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
            auth_testing_authorized=True,
            mutation_testing_authorized=True,
        )
    write_sigs = [s for s in sigs if "jwt_alg_none_write" in s.signature]
    assert write_sigs == []


def test_write_probe_no_signal_when_jwt_returns_401() -> None:
    def _handler(req: httpx.Request) -> httpx.Response:
        if req.method == "PUT":
            return httpx.Response(401, text="Unauthorized")
        return httpx.Response(404, text="not found")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
            auth_testing_authorized=True,
            mutation_testing_authorized=True,
        )
    write_sigs = [s for s in sigs if "jwt_alg_none_write" in s.signature]
    assert write_sigs == []


def test_write_probe_no_signal_for_405_method_not_allowed() -> None:
    """405 on baseline = route doesn't support method, not auth-gated."""
    def _handler(req: httpx.Request) -> httpx.Response:
        if req.method == "PUT":
            return httpx.Response(405, text="Method Not Allowed")
        return httpx.Response(404, text="not found")

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        sigs = auth_bypass_tool.probe_service(
            "https://target.cocode.dk",
            client=client, run_id="r1", observed_at="t",
            auth_testing_authorized=True,
            mutation_testing_authorized=True,
        )
    write_sigs = [s for s in sigs if "jwt_alg_none_write" in s.signature]
    assert write_sigs == []
