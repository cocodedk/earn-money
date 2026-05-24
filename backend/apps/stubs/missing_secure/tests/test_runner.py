"""Tests for stub 3.2 runner — missing Secure."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs._test_helpers import make_cookie_resp
from apps.stubs.missing_secure.runner import run


@pytest.fixture(autouse=True)
def _bypass_guard():
    with patch("apps.stubs.runners.resolve_and_guard", return_value=MagicMock()):
        yield


@pytest.fixture
def _seed(db):
    return seed_target_run(stub_slug="3.2", host="fixture.test")


@pytest.fixture
def scan_run(_seed):
    scan_run, _ = _seed
    return scan_run


@pytest.fixture
def target_run(_seed):
    _, target_run = _seed
    return target_run


@pytest.fixture
def _seed_http(db):
    return seed_target_run(
        stub_slug="3.2", host="fixture.test",
        base_url="http://fixture.test:3000",
    )


@pytest.fixture
def scan_run_http(_seed_http):
    scan_run, _ = _seed_http
    return scan_run


@pytest.fixture
def target_run_http(_seed_http):
    _, target_run = _seed_http
    return target_run


_resp = make_cookie_resp


@pytest.mark.django_db
def test_finding_for_missing_secure_session_cookie(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; HttpOnly; SameSite=Lax"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.2").exists()


@pytest.mark.django_db
def test_finding_for_missing_secure_framework_cookie(scan_run, target_run):
    resp = _resp(["PHPSESSID=x; Path=/; HttpOnly"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.2").exists()


@pytest.mark.django_db
def test_finding_samesite_none_without_secure(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; HttpOnly; SameSite=None"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.2").exists()


@pytest.mark.django_db
def test_candidate_on_http_scheme(scan_run_http, target_run_http):
    resp = _resp(["sid=x; Path=/; HttpOnly"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run_http, target_run_http)
    f = Finding.objects.get(stub_slug="3.2")
    assert f.confidence == "medium"


@pytest.mark.django_db
def test_no_finding_when_secure_present(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly; SameSite=Lax"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.2").exists()


@pytest.mark.django_db
def test_no_finding_for_preference_cookie(scan_run, target_run):
    resp = _resp(["theme=dark; Path=/"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.2").exists()


@pytest.mark.django_db
def test_deduplication_across_probe_paths(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; HttpOnly"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.2").count() == 1


@pytest.mark.django_db
def test_no_crash_on_empty_response(scan_run, target_run):
    resp = _resp([])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)


@pytest.mark.django_db
def test_no_crash_on_transport_error(scan_run, target_run):
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=None):
        run(scan_run, target_run)


@pytest.mark.django_db
def test_finding_cookie_value_redacted(scan_run, target_run):
    resp = _resp(["PHPSESSID=supersecret123; Path=/; HttpOnly"])
    with patch("apps.stubs.missing_secure.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.2")
    assert "supersecret123" not in str(f.data)


@pytest.mark.django_db
def test_same_cookie_different_paths_both_reported(scan_run, target_run):
    """Cookie missing Secure on two distinct paths → two findings."""
    root_resp = _resp(["sid=x; Path=/; HttpOnly"])
    login_resp = _resp(["sid=x; Path=/login; HttpOnly"])
    responses = iter([root_resp, login_resp])
    with patch("apps.stubs.missing_secure.runner.submit_probe", side_effect=responses):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.2").count() == 2
