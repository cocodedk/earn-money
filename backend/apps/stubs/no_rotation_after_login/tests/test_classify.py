"""Tests for stub 3.6 no-rotation-after-login classification."""
from __future__ import annotations

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs.no_rotation_after_login.classify import (
    RotationResult,
    RotationStatus,
    classify_rotation,
)


def _c(header):
    return parse_set_cookie(header)


def test_same_sid_confirmed():
    pre = [_c("sid=x; Path=/")]
    post = [_c("sid=x; Path=/")]
    r = classify_rotation(pre, post)
    assert r.status == RotationStatus.CONFIRMED
    assert r.confidence == "high"
    assert "sid" in r.affected_names


def test_different_sid_rejected():
    pre = [_c("sid=old; Path=/")]
    post = [_c("sid=new; Path=/")]
    r = classify_rotation(pre, post)
    assert r.status == RotationStatus.REJECTED
    assert r.confidence == "high"
    assert r.affected_names == []


def test_no_pre_cookie_not_applicable():
    r = classify_rotation([], [_c("sid=x; Path=/")])
    assert r.status == RotationStatus.NOT_APPLICABLE
    assert r.confidence == "high"


def test_no_post_cookie_rejected():
    pre = [_c("sid=x; Path=/")]
    r = classify_rotation(pre, [])
    assert r.status == RotationStatus.REJECTED


def test_low_sensitivity_not_applicable():
    pre = [_c("theme=dark; Path=/")]
    post = [_c("theme=dark; Path=/")]
    r = classify_rotation(pre, post)
    assert r.status == RotationStatus.NOT_APPLICABLE


def test_multiple_session_cookies_affected():
    pre = [_c("sid=x; Path=/"), _c("auth=y; Path=/")]
    post = [_c("sid=x; Path=/"), _c("auth=y; Path=/")]
    r = classify_rotation(pre, post)
    assert set(r.affected_names) == {"sid", "auth"}


def test_partial_rotation():
    pre = [_c("sid=x; Path=/"), _c("auth=y; Path=/")]
    post = [_c("sid=new; Path=/"), _c("auth=y; Path=/")]
    r = classify_rotation(pre, post)
    assert r.status == RotationStatus.CONFIRMED
    assert r.affected_names == ["auth"]
    assert "sid" not in r.affected_names
