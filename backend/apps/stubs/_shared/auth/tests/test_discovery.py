"""Unit tests for `_shared/auth/discovery.fetch_for_discovery`.

Covers the bounded scope-aware redirect-following behaviour added in
response to codex review finding P1.2 (commit cb336c6 / aac1efb).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.discovery import fetch_for_discovery
from apps.stubs._shared.scope_check import _reset_emit_cache_for_tests
from apps.stubs._test_factories import seed_target_run


_BODY = "<html><body>ok</body></html>"


def _program(in_scope: list[str]) -> Program:
    return Program(
        platform="local", slug="x",
        scope=Scope(
            platform="local", slug="x", policy="rate-limited-OK",
            in_scope=in_scope, out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=10),
    )


def _resp(
    *, status: int = 200, body: str = _BODY,
    headers: dict | None = None, url: str = "https://x.example/",
) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.headers = headers or {"content-type": "text/html"}
    r.url = url
    return r


def _patch_get(responses: list):
    """Patch Client so each `client.get(url)` pops the next response
    from the shared queue."""
    class _FakeClient:
        def __init__(self, **_kw: object) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def get(self, url: str):  # type: ignore[no-untyped-def]
            r = responses.pop(0)
            if isinstance(r, BaseException):
                raise r
            return r

    return patch("apps.stubs._shared.auth.discovery.Client", _FakeClient)


@pytest.fixture(autouse=True)
def _clear_scope_emit_cache() -> None:
    _reset_emit_cache_for_tests()


@pytest.mark.django_db
def test_single_200_returns_outcome() -> None:
    """No redirects, single 200 → ok outcome with body + content_type."""
    _, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    queue = [_resp(status=200)]
    with _patch_get(queue):
        outcome = fetch_for_discovery(
            "https://x.example/",
            target=target_run.target, program=_program(["x.example"]),
        )
    assert outcome.ok is True
    assert outcome.status == 200
    assert outcome.body == _BODY
    assert outcome.content_type == "text/html"
    assert outcome.error is None


@pytest.mark.django_db
def test_same_host_302_followed() -> None:
    """In-scope redirect to /login → follow + return the final 200."""
    _, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    queue = [
        _resp(status=302, headers={"location": "/login"}, body=""),
        _resp(status=200, body=_BODY, url="https://x.example/login"),
    ]
    with _patch_get(queue):
        outcome = fetch_for_discovery(
            "https://x.example/",
            target=target_run.target, program=_program(["x.example"]),
        )
    assert outcome.ok is True
    assert outcome.status == 200
    assert outcome.body == _BODY


@pytest.mark.django_db
def test_off_scope_redirect_refused() -> None:
    """3xx pointing at an off-scope host → no second GET, returns
    redirect_off_scope outcome, OUT_OF_SCOPE_REJECTED emitted once."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    queue = [
        _resp(
            status=302,
            headers={"location": "https://attacker.example/landed"},
            body="",
        ),
    ]
    with _patch_get(queue):
        outcome = fetch_for_discovery(
            "https://x.example/",
            target=target_run.target, program=_program(["x.example"]),
            scan_run=scan_run, stub_id="2.1",
        )
    assert outcome.ok is False
    assert outcome.error == "redirect_off_scope"
    assert len(queue) == 0  # only one GET issued
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
    ).exists()


@pytest.mark.django_db
def test_too_many_redirects_returns_outcome() -> None:
    """A redirect chain longer than max_redirects → returns
    too_many_redirects outcome."""
    _, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    queue = [
        _resp(status=302, headers={"location": "/a"}),
        _resp(status=302, headers={"location": "/b"}),
        _resp(status=302, headers={"location": "/c"}),
        _resp(status=302, headers={"location": "/d"}),
    ]
    with _patch_get(queue):
        outcome = fetch_for_discovery(
            "https://x.example/",
            target=target_run.target, program=_program(["x.example"]),
            max_redirects=2,
        )
    assert outcome.ok is False
    assert outcome.error == "too_many_redirects"


@pytest.mark.django_db
def test_transport_error_returns_outcome() -> None:
    """httpx.ConnectError on the first GET → outcome with error
    named after the exception class."""
    _, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    queue: list = [httpx.ConnectError("boom")]
    with _patch_get(queue):
        outcome = fetch_for_discovery(
            "https://x.example/",
            target=target_run.target, program=_program(["x.example"]),
        )
    assert outcome.ok is False
    assert outcome.error == "ConnectError"


@pytest.mark.django_db
def test_single_client_reused_across_hops() -> None:
    """Codex re-review found that per-hop `httpx.Client(...)` calls
    dropped the cookie jar between redirects. The fetcher must build
    ONE Client and reuse it across all hops so set-cookie on a 30x
    replays on the next GET. Structural assertion via patch.call_count."""
    _, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    queue = [
        _resp(status=302, headers={"location": "/login"}, body=""),
        _resp(status=302, headers={"location": "/login/step2"}, body=""),
        _resp(status=200, body=_BODY, url="https://x.example/login/step2"),
    ]
    with patch("apps.stubs._shared.auth.discovery.Client") as client_cls:
        instance = MagicMock()
        instance.__enter__ = MagicMock(return_value=instance)
        instance.__exit__ = MagicMock(return_value=None)
        instance.get = MagicMock(side_effect=queue)
        client_cls.return_value = instance
        outcome = fetch_for_discovery(
            "https://x.example/",
            target=target_run.target, program=_program(["x.example"]),
        )
    assert outcome.ok is True
    assert outcome.status == 200
    assert client_cls.call_count == 1
    assert instance.get.call_count == 3  # all three hops on one client


@pytest.mark.django_db
def test_3xx_without_location_treated_as_final() -> None:
    """Response is 302 but has no Location header → treated as the
    final outcome (no infinite-loop bug)."""
    _, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    queue = [_resp(status=302, headers={}, body="")]
    with _patch_get(queue):
        outcome = fetch_for_discovery(
            "https://x.example/",
            target=target_run.target, program=_program(["x.example"]),
        )
    assert outcome.ok is True
    assert outcome.status == 302
