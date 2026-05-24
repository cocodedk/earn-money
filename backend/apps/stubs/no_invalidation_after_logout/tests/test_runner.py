"""Tests for stub 3.7 runner — no session invalidation after logout."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs.no_invalidation_after_logout.runner import run

pytestmark = pytest.mark.usefixtures("_bypass_guard")


@pytest.fixture
def _seed(db):
    return seed_target_run(
        stub_slug="3.7", host="app.example.test",
        base_url="https://app.example.test",
    )


@pytest.fixture
def scan_run(_seed):
    scan_run, _ = _seed
    return scan_run


@pytest.fixture
def target_run(_seed):
    _, target_run = _seed
    return target_run


def _make_resp(status: int, set_cookie: str = "") -> httpx.Response:
    headers = []
    if set_cookie:
        headers.append((b"set-cookie", set_cookie.encode()))
    headers.append((b"content-type", b"application/json"))
    return httpx.Response(status, headers=httpx.Headers(headers))


@pytest.mark.django_db
def test_session_survives_logout_creates_finding(scan_run, target_run):
    seed_resp = _make_resp(200, "sid=tok; Path=/; HttpOnly")
    check_pre_resp = _make_resp(200)
    logout_resp = _make_resp(200)
    check_post_resp = _make_resp(200)   # session still valid
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               side_effect=[seed_resp, check_pre_resp, logout_resp, check_post_resp]):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.7")
    assert f.status == "confirmed"
    assert f.data["pre_logout_status"] == 200
    assert f.data["post_logout_status"] == 200


@pytest.mark.django_db
def test_session_invalidated_no_finding(scan_run, target_run):
    seed_resp = _make_resp(200, "sid=tok; Path=/; HttpOnly")
    check_pre_resp = _make_resp(200)
    logout_resp = _make_resp(200)
    check_post_resp = _make_resp(401)   # session properly invalidated
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               side_effect=[seed_resp, check_pre_resp, logout_resp, check_post_resp]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.7").exists()


@pytest.mark.django_db
def test_seed_transport_error_no_finding(scan_run, target_run):
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               return_value=None):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.7").exists()


@pytest.mark.django_db
def test_pre_check_transport_error_no_finding(scan_run, target_run):
    seed_resp = _make_resp(200, "sid=tok; Path=/; HttpOnly")
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               side_effect=[seed_resp, None]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.7").exists()


@pytest.mark.django_db
def test_logout_transport_error_no_finding(scan_run, target_run):
    seed_resp = _make_resp(200, "sid=tok; Path=/; HttpOnly")
    check_pre_resp = _make_resp(200)
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               side_effect=[seed_resp, check_pre_resp, None]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.7").exists()


@pytest.mark.django_db
def test_post_check_transport_error_no_finding(scan_run, target_run):
    seed_resp = _make_resp(200, "sid=tok; Path=/; HttpOnly")
    check_pre_resp = _make_resp(200)
    logout_resp = _make_resp(200)
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               side_effect=[seed_resp, check_pre_resp, logout_resp, None]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.7").exists()


@pytest.mark.django_db
def test_pre_check_not_2xx_no_finding(scan_run, target_run):
    seed_resp = _make_resp(200, "sid=tok; Path=/; HttpOnly")
    check_pre_resp = _make_resp(401)
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               side_effect=[seed_resp, check_pre_resp]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.7").exists()


@pytest.mark.django_db
def test_no_session_cookie_in_seed_no_finding(scan_run, target_run):
    # Seed response with empty-value cookie → partition("=")[2] is "" →
    # _extract_session_cookie skips it and returns "" → covers both branches.
    seed_resp = _make_resp(200, "sid=; Path=/; HttpOnly")
    check_pre_resp = _make_resp(401)
    with patch("apps.stubs.no_invalidation_after_logout.runner.submit_probe",
               side_effect=[seed_resp, check_pre_resp]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.7").exists()
