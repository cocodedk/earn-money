"""Abort-signal detection — CAPTCHA / WAF / lockout / rate-limit / MFA.

Body-content scan that drives the `NormalizedResponse.abort_signal`
field. A scan that hits one of these must NOT promote findings to
`confirmed`; the safety helper records `stale` or an event-only
refusal instead.
"""
from __future__ import annotations

from ..body_match import contains_any_lowered
from .safety import AbortSignal


_ABORT_MARKERS: tuple[tuple[AbortSignal, tuple[str, ...]], ...] = (
    (AbortSignal.CAPTCHA, (
        "captcha", "recaptcha", "hcaptcha", "i'm not a robot",
    )),
    (AbortSignal.WAF, (
        "cloudflare", "access denied", "blocked by our security",
        "akamai reference",
    )),
    (AbortSignal.LOCKOUT, (
        "account is locked", "account locked",
        "too many failed attempts", "account has been locked",
    )),
    (AbortSignal.RATE_LIMIT, (
        "rate limit", "too many requests", "slow down",
    )),
    (AbortSignal.MFA, (
        "authenticator", "verification code", "two-factor", "mfa",
    )),
)


def classify_abort_body(body: str) -> AbortSignal | None:
    """Body-content scan for known abort markers. First match wins —
    per spec the stub treats any abort as a hard stop."""
    if not body:
        return None
    lo = body.lower()
    for signal, markers in _ABORT_MARKERS:
        if contains_any_lowered(lo, markers):
            return signal
    return None
