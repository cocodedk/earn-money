"""Per-program rate limiter — token-bucket keyed by (platform, slug).

`acquire_for(program)` blocks just long enough to honor the program's
`roe.max_requests_per_second`, capped by the repo-wide shared floor.
The lower of the two wins (negative-rate-is-gospel).

This MVP uses an in-memory bucket per Python process. Cross-worker
coordination via Redis is deferred — until then, live H1 scans must
run on a single Celery worker so two workers can't both consume the
last token. Tracked as a blocking follow-up before broad scans.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from django.conf import settings

from .loader import Program


# Repo-wide floor in requests per second. Overridable in settings as
# `RATE_LIMIT_SHARED_FLOOR_RPS`. Default: 10. Programs whose RoE caps
# go lower bind tighter; programs whose RoE goes higher are clamped.
_DEFAULT_FLOOR_RPS = 10


class TokenBucket:
    """A simple token-bucket. `capacity` tokens fully refill in
    `1/refill_per_sec` seconds; each `acquire()` consumes one. When
    empty, the call blocks until the next refill grants a token.

    Clock is injected so tests can drive time deterministically.
    """

    def __init__(
        self, *, capacity: int, refill_per_sec: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if capacity <= 0 or refill_per_sec <= 0:
            raise ValueError(
                f"capacity + refill_per_sec must be > 0; "
                f"got capacity={capacity} refill_per_sec={refill_per_sec}"
            )
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._tokens = float(capacity)
        self._clock = clock
        self._sleep = sleep
        self._last = clock()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        """Caller must hold ``_lock``."""
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
        self._last = now

    def acquire(self) -> None:
        """Consume one token; block (without holding the lock) until
        a token is available.

        The implementation explicitly releases the lock before sleeping
        so a second waiter doesn't deadlock on a slow refill.
        """
        while True:
            with self._lock:
                self._refill_locked()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Compute the wait time outside the lock-protected critical section.
                deficit = 1.0 - self._tokens
                wait = deficit / self.refill_per_sec
            self._sleep(wait)


_buckets: dict[tuple[str, str], TokenBucket] = {}
_buckets_lock = threading.Lock()


def _floor_rps() -> int:
    """Repo-wide floor. Settings-overridable for tests."""
    return int(getattr(settings, "RATE_LIMIT_SHARED_FLOOR_RPS", _DEFAULT_FLOOR_RPS))


def _bucket_for(program: Program) -> TokenBucket:
    """Get-or-create the bucket for one (platform, slug) pair.

    Capacity = `min(program.roe.max_requests_per_second, shared floor)`.
    """
    key = (program.platform, program.slug)
    with _buckets_lock:
        bucket = _buckets.get(key)
        if bucket is not None:
            return bucket
        cap = min(program.roe.max_requests_per_second, _floor_rps())
        bucket = TokenBucket(capacity=cap, refill_per_sec=cap)
        _buckets[key] = bucket
        return bucket


def acquire_for(program: Program) -> None:
    """Block until the program's rate-limit budget grants one request."""
    _bucket_for(program).acquire()


def _reset_for_tests() -> None:
    """Test hook — clear the bucket registry between independent
    test cases that exercise the same program at different caps."""
    with _buckets_lock:
        _buckets.clear()
