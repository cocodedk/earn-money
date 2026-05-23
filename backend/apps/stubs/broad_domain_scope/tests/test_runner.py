"""Tests for stub 3.4 runner — broad domain scope."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs._test_helpers import make_cookie_resp
from apps.stubs.broad_domain_scope.runner import run


@pytest.fixture(autouse=True)
def _bypass_guard():
    with patch("apps.stubs.runners.resolve_and_guard", return_value=MagicMock()):
        yield


@pytest.fixture
def _seed(db):
    return seed_target_run(
        stub_slug="3.4", host="app.example.test",
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
def test_parent_domain_creates_confirmed_finding(scan_run, target_run):
    resp = _resp(["sid=x; Domain=example.test; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.4")
    assert f.data["scope_issue"] == "parent_domain"
    assert f.status == "confirmed"


@pytest.mark.django_db
def test_exact_host_domain_attribute_creates_candidate(db):
    scan_run, target_run = seed_target_run(
        stub_slug="3.4", host="app.example.test",
        base_url="https://app.example.test",
    )
    resp = _resp(["sid=x; Domain=app.example.test; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.4")
    assert f.data["scope_issue"] == "exact_host_domain_attribute"
    assert f.confidence == "low"


@pytest.mark.django_db
def test_host_only_no_finding(scan_run, target_run):
    resp = _resp(["sid=x; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.4").exists()


@pytest.mark.django_db
def test_preference_cookie_no_finding(scan_run, target_run):
    resp = _resp(["theme=dark; Domain=example.test; Path=/"])
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.4").exists()


@pytest.mark.django_db
def test_sso_role_header_skips_cookie(scan_run, target_run):
    raw = [
        (b"set-cookie", b"sso_state=val; Domain=example.test; Path=/; Secure; HttpOnly"),
        (b"x-cookie-role", b"sso"),
        (b"content-type", b"application/json"),
    ]
    resp = httpx.Response(200, headers=httpx.Headers(raw))
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert not Finding.objects.filter(stub_slug="3.4").exists()


@pytest.mark.django_db
def test_deduplication_across_probe_paths(scan_run, target_run):
    resp = _resp(["sid=x; Domain=example.test; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    assert Finding.objects.filter(stub_slug="3.4").count() == 1


@pytest.mark.django_db
def test_no_crash_on_empty_response(scan_run, target_run):
    resp = _resp([])
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)


@pytest.mark.django_db
def test_no_crash_on_transport_error(scan_run, target_run):
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=None):
        run(scan_run, target_run)


@pytest.mark.django_db
def test_finding_cookie_value_redacted(scan_run, target_run):
    resp = _resp(["sid=supersecret123; Domain=example.test; Path=/; Secure; HttpOnly"])
    with patch("apps.stubs.broad_domain_scope.runner.submit_probe", return_value=resp):
        run(scan_run, target_run)
    f = Finding.objects.get(stub_slug="3.4")
    assert "supersecret123" not in str(f.data)
