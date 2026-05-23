"""Tests for the shared cookie parser."""
from __future__ import annotations

import pytest

from apps.stubs._shared.session.cookie_parser import (
    CookieCategory,
    ParsedCookie,
    Sensitivity,
    is_sensitive_cookie,
    parse_set_cookie,
)


def test_parses_name_and_value():
    c = parse_set_cookie("sid=abc123")
    assert c.name == "sid" and c.value_redacted is not None


def test_httponly_present_case_insensitive():
    for attr in ("HttpOnly", "httponly", "HTTPONLY"):
        c = parse_set_cookie(f"sid=x; Path=/; {attr}")
        assert c.httponly is True, f"failed for: {attr}"


def test_httponly_absent():
    c = parse_set_cookie("sid=x; Path=/; Secure; SameSite=Lax")
    assert c.httponly is False


def test_secure_present():
    c = parse_set_cookie("sid=x; Secure; HttpOnly")
    assert c.secure is True


def test_secure_absent():
    c = parse_set_cookie("sid=x; HttpOnly")
    assert c.secure is False


def test_samesite_values():
    for val in ("Strict", "Lax", "None"):
        c = parse_set_cookie(f"sid=x; SameSite={val}")
        assert c.samesite == val


def test_samesite_missing_is_none():
    c = parse_set_cookie("sid=x")
    assert c.samesite is None


def test_samesite_invalid_value():
    c = parse_set_cookie("sid=x; SameSite=Loose")
    assert c.samesite == "Loose"


def test_domain_extracted():
    c = parse_set_cookie("sid=x; Domain=example.test; Path=/")
    assert c.domain == "example.test"


def test_domain_leading_dot_stripped():
    c = parse_set_cookie("sid=x; Domain=.example.test")
    assert c.domain == "example.test"


def test_path_extracted():
    c = parse_set_cookie("sid=x; Path=/app")
    assert c.path == "/app"


def test_max_age_extracted():
    c = parse_set_cookie("sid=x; Max-Age=3600")
    assert c.max_age == 3600


def test_expires_extracted():
    c = parse_set_cookie("sid=x; Expires=Thu, 01 Jan 2099 00:00:00 GMT")
    assert c.expires is not None


def test_value_is_redacted():
    c = parse_set_cookie("PHPSESSID=supersecret1234567890; Path=/")
    assert "supersecret1234567890" not in (c.value_redacted or "")


def test_framework_session_high_sensitivity():
    for name in ("PHPSESSID", "JSESSIONID", "connect.sid", "ASP.NET_SessionId"):
        s = is_sensitive_cookie(name)
        assert s == Sensitivity.HIGH, f"{name} should be HIGH"


def test_session_name_high_sensitivity():
    for name in ("session", "sid", "auth", "access_token", "refresh_token", "jwt"):
        assert is_sensitive_cookie(name) == Sensitivity.HIGH


def test_medium_sensitivity_names():
    for name in ("my_session_id", "auth_helper", "token_store", "remember_me"):
        assert is_sensitive_cookie(name) == Sensitivity.MEDIUM


def test_preference_cookie_low():
    for name in ("theme", "locale", "_ga", "ab_test", "consent"):
        assert is_sensitive_cookie(name) == Sensitivity.LOW


def test_csrf_token_low_by_default():
    assert is_sensitive_cookie("csrf_token") == Sensitivity.LOW


def test_cookie_category_framework():
    c = parse_set_cookie("PHPSESSID=x; Path=/")
    assert c.category == CookieCategory.FRAMEWORK_SESSION


def test_cookie_category_session():
    c = parse_set_cookie("session=x; Path=/")
    assert c.category == CookieCategory.SESSION


def test_cookie_category_access_token():
    c = parse_set_cookie("access_token=x; Path=/")
    assert c.category == CookieCategory.ACCESS_TOKEN


def test_cookie_category_refresh_token():
    c = parse_set_cookie("refresh_token=x; Path=/")
    assert c.category == CookieCategory.REFRESH_TOKEN


def test_raw_value_not_in_raw_set_cookie():
    c = parse_set_cookie("PHPSESSID=topsecret; Path=/; HttpOnly")
    assert "topsecret" not in c.raw_set_cookie


def test_max_age_invalid_string_is_none():
    c = parse_set_cookie("sid=x; Max-Age=notanumber")
    assert c.max_age is None


def test_cookie_category_auth():
    c = parse_set_cookie("auth=x; Path=/")
    assert c.category == CookieCategory.AUTH


def test_cookie_category_remember_me():
    c = parse_set_cookie("remember_me=x; Path=/")
    assert c.category == CookieCategory.REMEMBER_ME
