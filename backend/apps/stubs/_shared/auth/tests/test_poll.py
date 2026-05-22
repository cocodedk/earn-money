"""Unit tests for `_shared/auth/_poll.poll_until`."""
from __future__ import annotations

from apps.stubs._shared.auth._poll import poll_until


def test_returns_first_non_none_immediately() -> None:
    """First poll wins → no sleeps, no clock advances."""
    sleeps: list[float] = []
    calls: list[int] = []

    def poll() -> int | None:
        calls.append(0)
        return 42

    out = poll_until(
        poll, timeout_s=10.0, interval_s=1.0,
        clock=lambda: 0.0, sleep=sleeps.append,
    )
    assert out == 42
    assert len(calls) == 1
    assert sleeps == []


def test_returns_none_when_deadline_hits() -> None:
    """poll always returns None → loop sleeps until deadline → None."""
    sleeps: list[float] = []
    ticks = iter([0.0, 0.5, 1.0, 2.0])  # deadline = 1.0

    def poll() -> int | None:
        return None

    out = poll_until(
        poll, timeout_s=1.0, interval_s=0.3,
        clock=lambda: next(ticks), sleep=sleeps.append,
    )
    assert out is None
    # First poll → check clock=0.5 (< 1.0) → sleep, then check clock=
    # 1.0 (>= 1.0) → return None. Only one sleep call.
    assert len(sleeps) == 1


def test_returns_non_none_on_second_poll() -> None:
    """First poll returns None, second returns a value → that value."""
    answers = iter([None, "hit"])
    sleeps: list[float] = []
    ticks = iter([0.0, 0.5, 1.5])

    out = poll_until(
        lambda: next(answers),
        timeout_s=10.0, interval_s=0.2,
        clock=lambda: next(ticks), sleep=sleeps.append,
    )
    assert out == "hit"
    assert sleeps == [0.2]  # exactly one inter-poll sleep


def test_final_sleep_clamped_to_remaining_deadline() -> None:
    """interval_s=5.0 but remaining time = 0.5 → sleep called with
    0.5, not 5.0 (no overshoot)."""
    sleeps: list[float] = []
    ticks = iter([0.0, 0.5, 999.0])

    out = poll_until(
        lambda: None, timeout_s=1.0, interval_s=5.0,
        clock=lambda: next(ticks), sleep=sleeps.append,
    )
    assert out is None
    assert sleeps == [0.5]  # min(5.0, 1.0 - 0.5)
