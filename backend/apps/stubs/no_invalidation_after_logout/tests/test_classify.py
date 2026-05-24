"""Tests for stub 3.7 no-invalidation-after-logout classification."""
from __future__ import annotations

from apps.stubs.no_invalidation_after_logout.classify import (
    InvalidationResult,
    InvalidationStatus,
    classify_invalidation,
)


def test_session_still_valid_after_logout_confirmed():
    r = classify_invalidation(pre_logout_status=200, post_logout_status=200)
    assert r.status == InvalidationStatus.CONFIRMED
    assert r.confidence == "high"
    assert r.pre_logout_status == 200
    assert r.post_logout_status == 200


def test_session_rejected_401_after_logout():
    r = classify_invalidation(pre_logout_status=200, post_logout_status=401)
    assert r.status == InvalidationStatus.REJECTED
    assert r.confidence == "high"


def test_session_rejected_403_after_logout():
    r = classify_invalidation(pre_logout_status=200, post_logout_status=403)
    assert r.status == InvalidationStatus.REJECTED


def test_pre_logout_not_2xx_not_applicable():
    r = classify_invalidation(pre_logout_status=401, post_logout_status=200)
    assert r.status == InvalidationStatus.NOT_APPLICABLE
    assert r.confidence == "high"


def test_pre_logout_500_not_applicable():
    r = classify_invalidation(pre_logout_status=500, post_logout_status=200)
    assert r.status == InvalidationStatus.NOT_APPLICABLE


def test_post_logout_302_rejected():
    # redirect after logout → session not accessible directly → rejected
    r = classify_invalidation(pre_logout_status=200, post_logout_status=302)
    assert r.status == InvalidationStatus.REJECTED


def test_result_carries_status_codes():
    r = classify_invalidation(pre_logout_status=200, post_logout_status=200)
    assert r.pre_logout_status == 200
    assert r.post_logout_status == 200
