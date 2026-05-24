"""Tests for stub 3.5 runner — session fixation."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs._test_helpers import make_cookie_resp
from apps.stubs.session_fixation.runner import run

pytestmark = pytest.mark.usefixtures("_bypass_guard")


@pytest.fixture
def _seed(db):
    return seed_target_run(
        stub_slug="3.5", host="app.example.test",
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
def test_fixation_confirmed_creates_finding(scan_run, target_run):
    get_resp = _resp(["sid=secret; Path=/; HttpOnly"])
    post_resp = _resp(["sid=secret; Path=/; HttpOnly"])
    with patch("apps.stubs.session_fixation.runner.submit_probe",
               side_effect=[get_resp, post_resp]):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.5")
    assert f.status == "confirmed"
    assert "sid" in f.data["affected_names"]


@pytest.mark.django_db
def test_rotation_no_finding(scan_run, target_run):
    get_resp = _resp(["sid=old; Path=/; HttpOnly"])
    post_resp = _resp(["sid=new; Path=/; HttpOnly"])
    with patch("apps.stubs.session_fixation.runner.submit_probe",
               side_effect=[get_resp, post_resp]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.5").exists()


@pytest.mark.django_db
def test_no_pre_cookie_no_finding(scan_run, target_run):
    get_resp = _resp([])
    post_resp = _resp(["sid=new; Path=/; HttpOnly"])
    with patch("apps.stubs.session_fixation.runner.submit_probe",
               side_effect=[get_resp, post_resp]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.5").exists()


@pytest.mark.django_db
def test_get_transport_error_skips_post(scan_run, target_run):
    # If GET returns None, POST must NOT be issued at all.
    mock_probe = MagicMock(return_value=None)
    with patch("apps.stubs.session_fixation.runner.submit_probe", mock_probe):
        run(scan_run, target_run)
    mock_probe.assert_called_once()
    assert not Finding.objects.filter(stub_slug="3.5").exists()


@pytest.mark.django_db
def test_post_transport_error_no_finding(scan_run, target_run):
    get_resp = _resp(["sid=x; Path=/; HttpOnly"])
    with patch("apps.stubs.session_fixation.runner.submit_probe",
               side_effect=[get_resp, None]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.5").exists()


@pytest.mark.django_db
def test_no_secret_in_finding(scan_run, target_run):
    get_resp = _resp(["sid=supersecret; Path=/; HttpOnly"])
    post_resp = _resp(["sid=supersecret; Path=/; HttpOnly"])
    with patch("apps.stubs.session_fixation.runner.submit_probe",
               side_effect=[get_resp, post_resp]):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.5")
    assert "supersecret" not in str(f.data)


@pytest.mark.django_db
def test_deduplication_one_finding_only(scan_run, target_run):
    get_resp = _resp(["sid=x; Path=/; HttpOnly"])
    post_resp = _resp(["sid=x; Path=/; HttpOnly"])
    with patch("apps.stubs.session_fixation.runner.submit_probe",
               side_effect=[get_resp, post_resp]):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.5").count() == 1
