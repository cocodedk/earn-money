"""Tests for stub 3.8 runner — long-lived sessions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs._test_helpers import make_cookie_resp
from apps.stubs.long_lived_sessions.runner import run

pytestmark = pytest.mark.usefixtures("_bypass_guard")


@pytest.fixture
def _seed(db):
    return seed_target_run(
        stub_slug="3.8", host="app.example.test",
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


_resp = make_cookie_resp


@pytest.mark.django_db
def test_long_max_age_creates_confirmed_finding(scan_run, target_run):
    resp = _resp(["sid=x; Max-Age=2592000; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.8")
    assert f.status == "confirmed"
    assert f.data["observed_max_age"] == 2592000
    assert f.data["cookie_name"] == "sid"


@pytest.mark.django_db
def test_short_max_age_no_finding(scan_run, target_run):
    resp = _resp(["sid=x; Max-Age=1800; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.8").exists()


@pytest.mark.django_db
def test_browser_session_cookie_no_finding(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.8").exists()


@pytest.mark.django_db
def test_preference_cookie_no_finding(scan_run, target_run):
    resp = _resp(["theme=dark; Max-Age=2592000; Path=/"])
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.8").exists()


@pytest.mark.django_db
def test_transport_error_no_finding(scan_run, target_run):
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=None):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.8").exists()


@pytest.mark.django_db
def test_no_cookies_no_finding(scan_run, target_run):
    resp = _resp([])
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.8").exists()


@pytest.mark.django_db
def test_deduplication_one_finding_per_cookie(scan_run, target_run):
    # Same cookie seen twice is deduplicated to one finding.
    resp = _resp(["sid=x; Max-Age=2592000; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.8").count() == 1


@pytest.mark.django_db
def test_no_secret_in_finding(scan_run, target_run):
    resp = _resp(["sid=supersecret; Max-Age=2592000; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.long_lived_sessions.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.8")
    assert "supersecret" not in str(f.data)
