"""Tests for stub 3.11 JWT missing-expiry runner."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.stubs._shared.auth.jwt_utils import build_hs_token
from apps.stubs._test_factories import seed_target_run
from apps.stubs.jwt_missing_expiry.runner import run

_SECRET = b"test"
_HEADER = {"alg": "HS256", "typ": "JWT"}

_ACCESS_TOKEN = build_hs_token(_HEADER, {"sub": "u1"}, _SECRET, "HS256")  # no exp
_VALID_TOKEN = build_hs_token(_HEADER, {"sub": "u1", "exp": 9999999999}, _SECRET, "HS256")


@pytest.fixture(autouse=True)
def _bypass_guard():
    with patch("apps.stubs.runners.resolve_and_guard", return_value=MagicMock()):
        yield


@pytest.fixture
def _seed(db):
    return seed_target_run(
        stub_slug="3.11-jwt-missing-expiry",
        host="jwt-lab.invalid",
        base_url="http://jwt-lab.invalid",
    )


@pytest.fixture
def scan_run(_seed):
    return _seed[0]


@pytest.fixture
def target_run(_seed):
    return _seed[1]


def _resp(headers=None, body=None):
    r = MagicMock()
    r.status_code = 200
    r.headers = headers or {}
    r.text = ""
    r.json.return_value = body or {}
    return r


_PATCH = "apps.stubs.jwt_missing_expiry.runner.submit_probe"


@pytest.mark.django_db
def test_missing_exp_bearer_creates_finding(scan_run, target_run):
    with patch(
        _PATCH,
        return_value=_resp(headers={"Authorization": f"Bearer {_ACCESS_TOKEN}"}),
    ):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_valid_exp_no_finding(scan_run, target_run):
    with patch(
        _PATCH,
        return_value=_resp(headers={"Authorization": f"Bearer {_VALID_TOKEN}"}),
    ):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_no_jwt_in_response_no_finding(scan_run, target_run):
    with patch(_PATCH, return_value=_resp()):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_probe_failure_no_finding(scan_run, target_run):
    with patch(_PATCH, return_value=None):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_jwt_in_response_body_no_exp_creates_finding(scan_run, target_run):
    with patch(_PATCH, return_value=_resp(body={"access_token": _ACCESS_TOKEN})):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_invalid_jwt_in_bearer_skipped(scan_run, target_run):
    r = _resp(headers={"Authorization": "Bearer not.a.jwt.at.all"})
    with patch(_PATCH, return_value=r):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_json_parse_error_no_finding(scan_run, target_run):
    r = MagicMock()
    r.status_code = 200
    r.headers = {}
    r.text = ""
    r.json.side_effect = ValueError("bad json")
    with patch(_PATCH, return_value=r):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_body_non_dict_no_finding(scan_run, target_run):
    r = MagicMock()
    r.status_code = 200
    r.headers = {}
    r.text = ""
    r.json.return_value = [_ACCESS_TOKEN]
    with patch(_PATCH, return_value=r):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").exists()


@pytest.mark.django_db
def test_same_token_in_header_and_body_creates_one_finding(scan_run, target_run):
    r = _resp(
        headers={"Authorization": f"Bearer {_ACCESS_TOKEN}"},
        body={"access_token": _ACCESS_TOKEN},
    )
    with patch(_PATCH, return_value=r):
        run(scan_run, target_run)

    from apps.findings.models import Finding
    assert Finding.objects.filter(stub_slug="3.11-jwt-missing-expiry").count() == 1
