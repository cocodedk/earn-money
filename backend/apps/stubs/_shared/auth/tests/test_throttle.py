"""Unit tests for `_shared/auth/throttle.is_throttled`."""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.stubs._shared.auth.throttle import is_throttled


@dataclass
class _FakeResp:
    status_code: int = 200
    text: str = ""
    headers: dict = field(default_factory=dict)


def test_status_429_is_throttle() -> None:
    assert is_throttled(_FakeResp(status_code=429)) is True


def test_status_200_clean_body_not_throttle() -> None:
    assert is_throttled(_FakeResp(text="Invalid credentials")) is False


def test_retry_after_header_is_throttle() -> None:
    assert is_throttled(
        _FakeResp(headers={"Retry-After": "60"}),
    ) is True


def test_ratelimit_header_is_throttle() -> None:
    assert is_throttled(
        _FakeResp(headers={"RateLimit-Limit": "100"}),
    ) is True


def test_x_ratelimit_header_is_throttle() -> None:
    assert is_throttled(
        _FakeResp(headers={"X-RateLimit-Reset": "1234"}),
    ) is True


def test_header_name_case_insensitive() -> None:
    assert is_throttled(_FakeResp(headers={"retry-after": "30"})) is True


def test_body_marker_too_many_attempts() -> None:
    assert is_throttled(_FakeResp(text="Too many attempts.")) is True


def test_body_marker_try_again_later() -> None:
    assert is_throttled(_FakeResp(text="Please try again later")) is True


def test_body_marker_temporarily_blocked() -> None:
    assert is_throttled(_FakeResp(text="Account temporarily blocked")) is True


def test_body_marker_verification_required() -> None:
    assert is_throttled(_FakeResp(text="Verification required")) is True


def test_body_falls_through_to_abort_classifier() -> None:
    """The existing CAPTCHA marker from `_normalize_abort` should
    still trigger via the composed call."""
    assert is_throttled(_FakeResp(text="Please solve this captcha")) is True


def test_no_text_no_throttle() -> None:
    assert is_throttled(_FakeResp(text="")) is False


def test_unrelated_header_not_throttle() -> None:
    assert is_throttled(
        _FakeResp(headers={"Content-Type": "text/html"}),
    ) is False
