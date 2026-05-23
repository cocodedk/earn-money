"""Tests for shared session lifecycle comparison helpers."""
from __future__ import annotations

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs._shared.session.session_lifecycle import CompareResult, compare_session_cookies


def _c(header):
    return parse_set_cookie(header)


def test_same_value_is_fixed():
    pre = [_c("sid=x; Path=/")]
    post = [_c("sid=x; Path=/")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == ["sid"]


def test_different_value_not_fixed():
    pre = [_c("sid=x; Path=/")]
    post = [_c("sid=y; Path=/")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == []
    assert r.no_pre_cookie is False


def test_no_pre_cookie():
    r = compare_session_cookies([], [_c("sid=x; Path=/")])
    assert r.no_pre_cookie is True
    assert r.fixed_names == []


def test_no_post_cookie_not_fixed():
    pre = [_c("sid=x; Path=/")]
    r = compare_session_cookies(pre, [])
    assert r.fixed_names == []
    assert r.no_pre_cookie is False


def test_none_value_skipped():
    # cookie with no value (no "=") — value_redacted is None, must not trigger false positive
    pre = [_c("sid")]
    post = [_c("sid")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == []


def test_empty_value_skipped():
    # cookie with empty value ("sid=") — value_redacted is None, must not flag as fixed
    pre = [_c("sid=; Path=/")]
    post = [_c("sid=; Path=/")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == []


def test_low_sensitivity_skipped():
    # preference cookies are Sensitivity.LOW and must be ignored
    pre = [_c("theme=dark; Path=/")]
    post = [_c("theme=dark; Path=/")]
    r = compare_session_cookies(pre, post)
    assert r.no_pre_cookie is True


def test_multiple_session_cookies():
    pre = [_c("sid=a; Path=/"), _c("auth=b; Path=/")]
    post = [_c("sid=a; Path=/"), _c("auth=c; Path=/")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == ["sid"]
    assert "auth" not in r.fixed_names


def test_compare_result_fields():
    r = CompareResult(fixed_names=["sid"], no_pre_cookie=False)
    assert r.fixed_names == ["sid"]
    assert r.no_pre_cookie is False
