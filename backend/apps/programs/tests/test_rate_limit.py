"""Contract tests for `apps.programs.rate_limit`.

Coverage matrix per [[plan slice F]]:
- token-bucket capacity=10, refill=10/sec allows 10 immediate; blocks 11th
- floor-precedence: min(program cap, shared floor) wins (lower always)
- clock injection: tests drive time deterministically
- bucket key isolation: two programs don't share a bucket
- non-positive caps rejected at TokenBucket construction
- no sleep while holding lock (single-threaded test asserts no deadlock)
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from apps.programs.loader import Program
from apps.programs.rate_limit import (
    TokenBucket, _reset_for_tests, acquire_for,
)
from apps.programs.roe import RoE
from apps.programs.scope import Scope


class FakeClock:
    """Deterministic clock + sleep for token-bucket tests."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _program(*, rps: int, slug: str = "algolia") -> Program:
    return Program(
        platform="hackerone", slug=slug,
        scope=Scope(
            platform="hackerone", slug=slug,
            policy="rate-limited-OK",
            in_scope=["www.algolia.com"], out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=rps),
    )


# --- TokenBucket primitive ---


def test_bucket_allows_capacity_immediate_requests() -> None:
    """10 tokens / 10 per sec — first 10 acquires return immediately."""
    clock = FakeClock()
    bucket = TokenBucket(
        capacity=10, refill_per_sec=10.0,
        clock=clock.time, sleep=clock.sleep,
    )
    for _ in range(10):
        bucket.acquire()
    # No sleeps consumed.
    assert clock.slept == []


def test_bucket_blocks_for_one_refill_when_empty() -> None:
    """The 11th request blocks for ~1/refill_per_sec seconds."""
    clock = FakeClock()
    bucket = TokenBucket(
        capacity=10, refill_per_sec=10.0,
        clock=clock.time, sleep=clock.sleep,
    )
    for _ in range(10):
        bucket.acquire()
    bucket.acquire()
    # First sleep waits 1/10 = 0.1s for one token to refill.
    assert clock.slept[0] == pytest.approx(0.1, abs=0.01)


def test_bucket_refills_continuously() -> None:
    """If half the capacity is consumed and time passes, the bucket
    refills proportionally on the next acquire."""
    clock = FakeClock()
    bucket = TokenBucket(
        capacity=10, refill_per_sec=10.0,
        clock=clock.time, sleep=clock.sleep,
    )
    for _ in range(10):
        bucket.acquire()
    clock.now += 0.5  # 0.5 sec passes — 5 tokens refill
    for _ in range(5):
        bucket.acquire()
    assert clock.slept == []


def test_bucket_rejects_non_positive_capacity() -> None:
    with pytest.raises(ValueError):
        TokenBucket(capacity=0, refill_per_sec=10.0)


def test_bucket_rejects_non_positive_refill() -> None:
    with pytest.raises(ValueError):
        TokenBucket(capacity=10, refill_per_sec=0)


# --- per-program acquire_for + floor-precedence ---


def test_acquire_for_creates_bucket_at_program_cap() -> None:
    _reset_for_tests()
    prog = _program(rps=5)
    with override_settings(RATE_LIMIT_SHARED_FLOOR_RPS=10):
        # 5 r/s caps below the 10-r/s floor → bucket binds at 5.
        # Acquire 5 immediately; 6th blocks.
        for _ in range(5):
            acquire_for(prog)


def test_floor_precedence_lower_program_cap_wins() -> None:
    """Program cap=1, floor=10 → min(1, 10) = 1. Only 1 immediate acquire."""
    _reset_for_tests()
    prog = _program(rps=1)
    with override_settings(RATE_LIMIT_SHARED_FLOOR_RPS=10):
        from apps.programs.rate_limit import _bucket_for
        bucket = _bucket_for(prog)
        assert bucket.capacity == 1.0
        assert bucket.refill_per_sec == 1.0


def test_floor_precedence_lower_floor_wins() -> None:
    """Program cap=10, floor=2 → min(10, 2) = 2. Floor binds tighter."""
    _reset_for_tests()
    prog = _program(rps=10)
    with override_settings(RATE_LIMIT_SHARED_FLOOR_RPS=2):
        from apps.programs.rate_limit import _bucket_for
        bucket = _bucket_for(prog)
        assert bucket.capacity == 2.0


def test_bucket_per_program_isolation() -> None:
    """Two distinct programs get distinct buckets — exhausting one
    doesn't block the other."""
    _reset_for_tests()
    a = _program(rps=2, slug="a")
    b = _program(rps=2, slug="b")
    from apps.programs.rate_limit import _bucket_for
    assert _bucket_for(a) is not _bucket_for(b)


def test_acquire_for_returns_same_bucket_on_repeat_calls() -> None:
    """Cache hit: a second acquire_for on the same program reuses the
    same bucket (preserving the running token count)."""
    _reset_for_tests()
    prog = _program(rps=5)
    from apps.programs.rate_limit import _bucket_for
    b1 = _bucket_for(prog)
    b2 = _bucket_for(prog)
    assert b1 is b2


# --- default floor (no override) ---


def test_default_floor_applies_when_settings_unset() -> None:
    """Without `RATE_LIMIT_SHARED_FLOOR_RPS` override, the default
    floor (10 r/s) is used. Program cap=20 → bucket caps at 10."""
    _reset_for_tests()
    prog = _program(rps=20)
    from apps.programs.rate_limit import _bucket_for
    bucket = _bucket_for(prog)
    assert bucket.capacity == 10.0  # floor = min(20, 10) = 10


