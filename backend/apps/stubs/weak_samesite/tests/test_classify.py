"""Tests for stub 3.3 weak-samesite classification."""
from __future__ import annotations

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs.weak_samesite.classify import (
    SameSiteResult,
    SameSiteStatus,
    WeaknessKind,
    classify_cookie,
)


def _c(header: str):
    return parse_set_cookie(header)


def test_missing_samesite_is_candidate():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly"))
    assert r.status == SameSiteStatus.CANDIDATE
    assert r.confidence == "medium"
    assert r.weakness_kind == WeaknessKind.MISSING_SAMESITE


def test_explicit_none_with_secure_is_candidate():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly; SameSite=None"))
    assert r.status == SameSiteStatus.CANDIDATE
    assert r.confidence == "high"
    assert r.weakness_kind == WeaknessKind.EXPLICIT_NONE


def test_none_without_secure_is_confirmed():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly; SameSite=None"))
    assert r.status == SameSiteStatus.CONFIRMED
    assert r.confidence == "high"
    assert r.weakness_kind == WeaknessKind.NONE_WITHOUT_SECURE


def test_invalid_samesite_value_is_confirmed():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly; SameSite=Loose"))
    assert r.status == SameSiteStatus.CONFIRMED
    assert r.confidence == "medium"
    assert r.weakness_kind == WeaknessKind.INVALID_SAMESITE


def test_lax_is_rejected():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly; SameSite=Lax"))
    assert r.status == SameSiteStatus.REJECTED
    assert r.confidence == "high"
    assert r.weakness_kind is None


def test_strict_is_rejected():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly; SameSite=Strict"))
    assert r.status == SameSiteStatus.REJECTED
    assert r.confidence == "high"
    assert r.weakness_kind is None


def test_preference_cookie_not_applicable():
    r = classify_cookie(_c("theme=dark; Path=/"))
    assert r.status == SameSiteStatus.NOT_APPLICABLE


def test_csrf_cookie_not_applicable():
    r = classify_cookie(_c("csrf_token=t; Path=/"))
    assert r.status == SameSiteStatus.NOT_APPLICABLE


def test_sso_allowlisted_not_applicable():
    r = classify_cookie(
        _c("sso_state=val; Path=/; Secure; HttpOnly; SameSite=None"),
        sso_allowlisted=True,
    )
    assert r.status == SameSiteStatus.NOT_APPLICABLE


def test_samesite_case_insensitive_lax():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly; SameSite=LAX"))
    assert r.status == SameSiteStatus.REJECTED


def test_result_carries_cookie_name():
    r = classify_cookie(_c("PHPSESSID=x; Path=/; HttpOnly"))
    assert r.cookie_name == "PHPSESSID"


def test_raw_value_not_in_result():
    r = classify_cookie(_c("PHPSESSID=supersecret; Path=/; HttpOnly"))
    assert "supersecret" not in str(r)
