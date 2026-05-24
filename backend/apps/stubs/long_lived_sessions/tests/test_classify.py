"""Tests for stub 3.8 long-lived-session classification."""
from __future__ import annotations

import datetime

from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs.long_lived_sessions.classify import (
    LongLivedResult,
    LongLivedStatus,
    classify_cookie,
)


def _c(header):
    return parse_set_cookie(header)


def _future_rfc2822(days: int) -> str:
    """Return an RFC-2822-formatted date that many days from now."""
    dt = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def test_max_age_30d_confirmed():
    r = classify_cookie(_c("sid=x; Max-Age=2592000; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.CONFIRMED
    assert r.confidence == "high"
    assert r.observed_max_age == 2592000


def test_max_age_30min_rejected():
    r = classify_cookie(_c("sid=x; Max-Age=1800; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.REJECTED
    assert r.confidence == "high"
    assert r.observed_max_age == 1800


def test_no_max_age_no_expires_not_applicable():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.NOT_APPLICABLE
    assert r.observed_max_age is None


def test_exactly_threshold_rejected():
    r = classify_cookie(_c("sid=x; Max-Age=86400; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.REJECTED


def test_one_second_over_threshold_confirmed():
    r = classify_cookie(_c("sid=x; Max-Age=86401; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.CONFIRMED


def test_very_long_max_age_confirmed():
    r = classify_cookie(_c("sid=x; Max-Age=31536000; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.CONFIRMED
    assert r.observed_max_age == 31536000


def test_custom_threshold():
    r = classify_cookie(
        _c("sid=x; Max-Age=3600; Path=/; Secure; HttpOnly"),
        max_session_age_seconds=3600,
    )
    assert r.status == LongLivedStatus.REJECTED


def test_preference_cookie_not_applicable():
    r = classify_cookie(_c("theme=dark; Max-Age=2592000; Path=/"))
    assert r.status == LongLivedStatus.NOT_APPLICABLE


def test_expires_far_future_confirmed():
    expires_str = _future_rfc2822(days=365)
    r = classify_cookie(_c(f"sid=x; Expires={expires_str}; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.CONFIRMED


def test_expires_near_future_rejected():
    expires_str = _future_rfc2822(days=0)  # ~0 seconds remaining, rounds to 0
    r = classify_cookie(_c(f"sid=x; Expires={expires_str}; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.REJECTED


def test_expires_invalid_string_not_applicable():
    r = classify_cookie(_c("sid=x; Expires=not-a-date; Path=/; Secure; HttpOnly"))
    assert r.status == LongLivedStatus.NOT_APPLICABLE


def test_max_age_takes_precedence_over_expires():
    # Max-Age=1800 (30 min, safe) with far-future Expires → should REJECT on Max-Age.
    expires_str = _future_rfc2822(days=365)
    r = classify_cookie(
        _c(f"sid=x; Max-Age=1800; Expires={expires_str}; Path=/; Secure; HttpOnly"),
    )
    assert r.status == LongLivedStatus.REJECTED


def test_result_carries_cookie_name():
    r = classify_cookie(_c("sid=x; Max-Age=2592000; Path=/; Secure; HttpOnly"))
    assert r.cookie_name == "sid"
