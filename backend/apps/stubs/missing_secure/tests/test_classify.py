"""Tests for stub 3.2 missing-secure classification."""
from __future__ import annotations

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs.missing_secure.classify import SecureResult, SecureStatus, classify_cookie


def _c(header: str):
    return parse_set_cookie(header)


def test_https_missing_secure_confirmed():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly; SameSite=Lax"), scheme="https")
    assert r.status == SecureStatus.CONFIRMED
    assert r.confidence == "high"


def test_framework_missing_secure_confirmed():
    r = classify_cookie(_c("PHPSESSID=x; Path=/; HttpOnly"), scheme="https")
    assert r.status == SecureStatus.CONFIRMED
    assert r.confidence == "high"


def test_samesite_none_missing_secure_confirmed():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly; SameSite=None"), scheme="https")
    assert r.status == SecureStatus.CONFIRMED
    assert r.confidence == "high"


def test_samesite_none_without_secure_confirmed_on_http():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly; SameSite=None"), scheme="http")
    assert r.status == SecureStatus.CONFIRMED
    assert r.confidence == "high"


def test_http_scheme_candidate():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly"), scheme="http")
    assert r.status == SecureStatus.CANDIDATE
    assert r.confidence == "medium"


def test_secure_present_rejected():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly; SameSite=Lax"), scheme="https")
    assert r.status == SecureStatus.REJECTED
    assert r.confidence == "high"


def test_preference_cookie_not_applicable():
    r = classify_cookie(_c("theme=dark; Path=/"), scheme="https")
    assert r.status == SecureStatus.NOT_APPLICABLE


def test_csrf_cookie_not_applicable():
    r = classify_cookie(_c("csrf_token=t; Path=/; SameSite=Lax"), scheme="https")
    assert r.status == SecureStatus.NOT_APPLICABLE


def test_result_carries_cookie_name():
    r = classify_cookie(_c("PHPSESSID=x; Path=/; HttpOnly"), scheme="https")
    assert r.cookie_name == "PHPSESSID"


def test_raw_value_not_in_result():
    r = classify_cookie(_c("PHPSESSID=supersecret; Path=/; HttpOnly"), scheme="https")
    assert "supersecret" not in str(r)
