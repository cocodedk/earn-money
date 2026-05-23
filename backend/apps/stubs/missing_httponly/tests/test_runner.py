"""Tests for stub 3.1 runner — missing HttpOnly."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs.missing_httponly.runner import run


@pytest.fixture(autouse=True)
def _bypass_guard():
    with patch("apps.stubs.runners.resolve_and_guard", return_value=MagicMock()):
        yield


@pytest.fixture
def scan_run_and_target(db):
    scan_run, target_run = seed_target_run(stub_slug="3.1", host="fixture.test")
    return scan_run, target_run


@pytest.fixture
def scan_run(scan_run_and_target):
    return scan_run_and_target[0]


@pytest.fixture
def target_run(scan_run_and_target):
    return scan_run_and_target[1]


def _resp(cookies: list[str], status: int = 200) -> httpx.Response:
    headers = {}
    if cookies:
        headers["Set-Cookie"] = cookies[0]
    r = httpx.Response(status, headers=headers)
    if len(cookies) > 1:
        # httpx stores multi-value headers; build raw response with multiple Set-Cookie
        raw_headers = [(b"set-cookie", c.encode()) for c in cookies]
        raw_headers.append((b"content-type", b"application/json"))
        r = httpx.Response(status, headers=httpx.Headers(raw_headers))
    return r


@pytest.mark.django_db
def test_finding_for_missing_httponly_session_cookie(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; SameSite=Lax"])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_finding_for_missing_httponly_framework_cookie(scan_run, target_run):
    resp = _resp(["PHPSESSID=x; Path=/"])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_no_finding_when_httponly_present(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; HttpOnly; Secure; SameSite=Lax"])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_no_finding_for_preference_cookie(scan_run, target_run):
    resp = _resp(["theme=dark; Path=/"])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_no_finding_for_csrf_cookie(scan_run, target_run):
    resp = _resp(["csrf_token=t; Path=/; SameSite=Lax"])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_mixed_cookies_only_vulnerable_flagged(scan_run, target_run):
    resp = _resp([
        "sid=s4; Path=/; Secure",
        "track=t2; Path=/",
        "session=s5; Path=/; HttpOnly; Secure",
    ])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    findings = Finding.objects.filter(stub_slug="3.1")
    assert findings.count() == 1
    assert findings.first().data["cookie_name"] == "sid"


@pytest.mark.django_db
def test_no_crash_on_empty_response(scan_run, target_run):
    resp = _resp([])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)  # must not raise


@pytest.mark.django_db
def test_no_crash_on_transport_error(scan_run, target_run):
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=None):
        run(scan_run, target_run)  # must not raise


@pytest.mark.django_db
def test_finding_cookie_value_redacted(scan_run, target_run):
    resp = _resp(["PHPSESSID=supersecret123; Path=/"])
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.1")
    assert "supersecret123" not in str(f.data)
