"""Tests for stub 3.3 runner — weak SameSite."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs._test_helpers import make_cookie_resp
from apps.stubs.weak_samesite.runner import run


@pytest.fixture(autouse=True)
def _bypass_guard():
    with patch("apps.stubs.runners.resolve_and_guard", return_value=MagicMock()):
        yield


@pytest.fixture
def _seed(db):
    return seed_target_run(stub_slug="3.3", host="fixture.test")


@pytest.fixture
def scan_run(_seed):
    scan_run, _ = _seed
    return scan_run


@pytest.fixture
def target_run(_seed):
    _, target_run = _seed
    return target_run


_resp = make_cookie_resp


@pytest.mark.django_db
def test_missing_samesite_creates_finding(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.3")
    assert f.data["weakness_kind"] == "missing_samesite"


@pytest.mark.django_db
def test_explicit_none_creates_finding(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly; SameSite=None"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.3")
    assert f.data["weakness_kind"] == "explicit_none"
    assert f.confidence == "high"


@pytest.mark.django_db
def test_none_without_secure_creates_confirmed_finding(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; HttpOnly; SameSite=None"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.3")
    assert f.data["weakness_kind"] == "none_without_secure"
    assert f.status == "confirmed"


@pytest.mark.django_db
def test_invalid_samesite_creates_confirmed_finding(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly; SameSite=Loose"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.3")
    assert f.data["weakness_kind"] == "invalid_samesite"


@pytest.mark.django_db
def test_lax_no_finding(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly; SameSite=Lax"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.3").exists()


@pytest.mark.django_db
def test_preference_cookie_no_finding(scan_run, target_run):
    resp = _resp(["theme=dark; Path=/"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.3").exists()


@pytest.mark.django_db
def test_sso_role_header_skips_cookie(scan_run, target_run):
    # Build response with X-Cookie-Role: sso and a SameSite=None cookie
    raw = [
        (b"set-cookie", b"sso_state=val; Path=/; Secure; HttpOnly; SameSite=None"),
        (b"x-cookie-role", b"sso"),
        (b"content-type", b"application/json"),
    ]
    resp = httpx.Response(200, headers=httpx.Headers(raw))
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.3").exists()


@pytest.mark.django_db
def test_deduplication_across_probe_paths(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.3").count() == 1


@pytest.mark.django_db
def test_no_crash_on_empty_response(scan_run, target_run):
    resp = _resp([])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)


@pytest.mark.django_db
def test_no_crash_on_transport_error(scan_run, target_run):
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=None):
        run(scan_run, target_run)


@pytest.mark.django_db
def test_finding_cookie_value_redacted(scan_run, target_run):
    resp = _resp(["PHPSESSID=supersecret123; Path=/; HttpOnly"])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.3")
    assert "supersecret123" not in str(f.data)


@pytest.mark.django_db
def test_confirmed_beats_candidate_in_dedup(scan_run, target_run):
    """CONFIRMED finding must win even if a CANDIDATE was seen first."""
    # First path: SameSite=None+Secure → CANDIDATE (explicit_none)
    candidate_resp = _resp(["sid=x; Path=/; Secure; HttpOnly; SameSite=None"])
    # Second path: SameSite=None without Secure → CONFIRMED (none_without_secure)
    confirmed_resp = _resp(["sid=x; Path=/; HttpOnly; SameSite=None"])
    responses = iter([candidate_resp, confirmed_resp])
    with patch("apps.stubs.weak_samesite.runner.submit_probe", side_effect=responses):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.3")
    assert f.status == "confirmed"
    assert f.data["weakness_kind"] == "none_without_secure"
