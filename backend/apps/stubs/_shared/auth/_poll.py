"""Shared bounded-polling loop used by the mailbox backends.

`poll_until(poll_fn, ...)` calls `poll_fn` repeatedly until it
returns a non-None value or the deadline expires. The clock and
sleep functions are injected so tests can drive time
deterministically without monkey-patching `time` globally.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


def poll_until(
    poll_fn: Callable[[], "T | None"], *,
    timeout_s: float,
    interval_s: float,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> "T | None":
    """Return the first non-None result of ``poll_fn``, or None on
    timeout. The final sleep is clamped to the remaining deadline so
    a slow poll near the boundary doesn't overshoot.

    `clock`/`sleep` default to `time.monotonic`/`time.sleep` resolved
    at CALL time — `None` defaults let `patch("..._poll.time.sleep")`
    in tests actually affect the polling cadence (function defaults
    capture references at definition time, defeating monkey-patches).
    """
    _clock = clock or time.monotonic
    _sleep = sleep or time.sleep
    deadline = _clock() + timeout_s
    while True:
        result = poll_fn()
        if result is not None:
            return result
        now = _clock()
        if now >= deadline:
            return None
        _sleep(min(interval_s, deadline - now))
