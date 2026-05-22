"""Throttle / rate-limit signal detection — used by stub 2.4.

`is_throttled(response)` returns True when the response carries ANY
rate-limit / temporary-block / CAPTCHA / lockout signal. Composes
`classify_abort_body` (the existing CAPTCHA/WAF/LOCKOUT/RATE_LIMIT/
MFA body scan) with three additional checks 2.4 requires:

* HTTP status 429.
* Retry-After header presence.
* RateLimit-* / X-RateLimit-* header presence.
* Extended body markers ("too many attempts", "try again later",
  "temporarily blocked", "temporarily locked", "verification
  required") that aren't covered by `_ABORT_MARKERS`.

Per spec 2.4 §5 latency alone is NOT a throttle signal.
"""
from __future__ import annotations

from typing import Protocol

from ..body_match import contains_any_lowered
from ._normalize_abort import classify_abort_body


_HTTP_THROTTLE_STATUS = 429
_RETRY_AFTER_HEADER = "retry-after"
_RATE_LIMIT_HEADER_PREFIXES: tuple[str, ...] = (
    "ratelimit-", "x-ratelimit-",
)
_EXTRA_BODY_MARKERS: tuple[str, ...] = (
    "too many attempts",
    "too many login attempts",
    "try again later",
    "temporarily blocked",
    "temporarily locked",
    "verification required",
)


class _ResponseLike(Protocol):
    """Structural subset of httpx.Response that is_throttled() needs."""
    status_code: int
    headers: dict
    text: str


def is_throttled(response: _ResponseLike) -> bool:
    """True if ``response`` carries any rate-limit / throttle / block
    signal. False otherwise — the caller treats False as "another
    attempt is permitted."""
    if response.status_code == _HTTP_THROTTLE_STATUS:
        return True
    if _has_rate_limit_header(response.headers):
        return True
    body = response.text or ""
    if classify_abort_body(body) is not None:
        return True
    return contains_any_lowered(body.lower(), _EXTRA_BODY_MARKERS)


def _has_rate_limit_header(headers: dict) -> bool:
    """True if any header name signals throttling (Retry-After or a
    rate-limit family header)."""
    for name in headers:
        lo = str(name).lower()
        if lo == _RETRY_AFTER_HEADER:
            return True
        if any(lo.startswith(p) for p in _RATE_LIMIT_HEADER_PREFIXES):
            return True
    return False
