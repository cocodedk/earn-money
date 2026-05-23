"""Tests for stub 3.5 session-fixation classification."""
from __future__ import annotations

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs.session_fixation.classify import (
    FixationResult,
    FixationStatus,
    classify_fixation,
)


def _c(header):
    return parse_set_cookie(header)


def test_same_sid_hash_confirmed():
    pre = [_c("sid=secret123; Path=/")]
    post = [_c("sid=secret123; Path=/")]
    r = classify_fixation(pre, post)
    assert r.status == FixationStatus.CONFIRMED
    assert r.confidence == "high"
    assert "sid" in r.affected_names


def test_different_sid_rejected():
    pre = [_c("sid=old; Path=/")]
    post = [_c("sid=new; Path=/")]
    r = classify_fixation(pre, post)
    assert r.status == FixationStatus.REJECTED
    assert r.confidence == "high"
    assert r.affected_names == []


def test_no_pre_cookie_not_applicable():
    r = classify_fixation([], [_c("sid=x; Path=/")])
    assert r.status == FixationStatus.NOT_APPLICABLE
    assert r.confidence == "high"


def test_no_post_cookie_rejected():
    pre = [_c("sid=x; Path=/")]
    r = classify_fixation(pre, [])
    assert r.status == FixationStatus.REJECTED


def test_low_sensitivity_cookie_not_applicable():
    pre = [_c("theme=dark; Path=/")]
    post = [_c("theme=dark; Path=/")]
    r = classify_fixation(pre, post)
    assert r.status == FixationStatus.NOT_APPLICABLE


def test_only_session_cookies_in_affected_names():
    pre = [_c("sid=x; Path=/"), _c("theme=dark; Path=/")]
    post = [_c("sid=x; Path=/"), _c("theme=dark; Path=/")]
    r = classify_fixation(pre, post)
    assert r.status == FixationStatus.CONFIRMED
    assert "sid" in r.affected_names
    assert "theme" not in r.affected_names


def test_result_carries_affected_names():
    pre = [_c("sid=abc; Path=/"), _c("auth=abc; Path=/")]
    post = [_c("sid=abc; Path=/"), _c("auth=abc; Path=/")]
    r = classify_fixation(pre, post)
    assert set(r.affected_names) == {"sid", "auth"}


def test_no_value_cookie_not_applicable():
    pre = [_c("sid")]
    post = [_c("sid")]
    r = classify_fixation(pre, post)
    assert r.status == FixationStatus.NOT_APPLICABLE
