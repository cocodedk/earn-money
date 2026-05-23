"""Tests for stub 3.1 missing-httponly classification."""
from __future__ import annotations

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs.missing_httponly.classify import (
    HttpOnlyResult,
    HttpOnlyStatus,
    classify_cookie,
)


def _c(header: str):
    return parse_set_cookie(header)


def test_high_sensitivity_missing_httponly_confirmed_authenticated():
    r = classify_cookie(_c("sid=x; Path=/; Secure; SameSite=Lax"), authenticated=True)
    assert r.status == HttpOnlyStatus.CONFIRMED
    assert r.confidence == "high"


def test_framework_cookie_missing_httponly_confirmed_unauthenticated():
    r = classify_cookie(_c("PHPSESSID=x; Path=/"), authenticated=False)
    assert r.status == HttpOnlyStatus.CONFIRMED
    assert r.confidence == "high"


def test_connect_sid_framework_confirmed_no_auth():
    # connect.sid is a known framework session cookie → CONFIRMED even without auth context
    r = classify_cookie(_c("connect.sid=x; Path=/; Secure; SameSite=Lax"), authenticated=False)
    assert r.status == HttpOnlyStatus.CONFIRMED
    assert r.confidence == "high"


def test_medium_sensitivity_no_auth_is_candidate_auth_looking():
    r = classify_cookie(_c("my_auth_token=x; Path=/; Secure"), authenticated=False)
    assert r.status == HttpOnlyStatus.CANDIDATE


def test_httponly_present_rejected():
    r = classify_cookie(
        _c("sid=x; Path=/; HttpOnly; Secure; SameSite=Lax"), authenticated=True
    )
    assert r.status == HttpOnlyStatus.REJECTED
    assert r.confidence == "high"


def test_httponly_case_insensitive_rejected():
    for attr in ("httponly", "HTTPONLY", "HttpOnly"):
        r = classify_cookie(_c(f"sid=x; Path=/; {attr}"), authenticated=False)
        assert r.status == HttpOnlyStatus.REJECTED, f"failed for: {attr}"


def test_preference_cookie_not_applicable():
    r = classify_cookie(_c("theme=dark; Path=/"), authenticated=False)
    assert r.status == HttpOnlyStatus.NOT_APPLICABLE


def test_csrf_token_not_applicable_by_default():
    r = classify_cookie(_c("csrf_token=t; Path=/; SameSite=Lax"), authenticated=False)
    assert r.status == HttpOnlyStatus.NOT_APPLICABLE


def test_medium_sensitivity_no_auth_is_candidate():
    r = classify_cookie(_c("my_session=x; Path=/; Secure"), authenticated=False)
    assert r.status == HttpOnlyStatus.CANDIDATE
    assert r.confidence == "medium"


def test_sid_missing_httponly_unauthenticated_confirmed():
    # sid is HIGH sensitivity regardless of auth context
    r = classify_cookie(_c("sid=x; Path=/; Secure"), authenticated=False)
    assert r.status == HttpOnlyStatus.CONFIRMED
    assert r.confidence == "high"


def test_raw_value_not_in_result():
    r = classify_cookie(_c("PHPSESSID=supersecret; Path=/"), authenticated=False)
    assert "supersecret" not in str(r)


def test_result_carries_cookie_name():
    r = classify_cookie(_c("PHPSESSID=x; Path=/"), authenticated=False)
    assert r.cookie_name == "PHPSESSID"
