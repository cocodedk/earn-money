"""Stub 3.2 — Missing Secure classification."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity


class SecureStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class SecureResult:
    status: SecureStatus
    confidence: Literal["low", "medium", "high"]
    cookie_name: str
    raw_set_cookie: str


def classify_cookie(cookie: ParsedCookie, *, scheme: str) -> SecureResult:
    if cookie.sensitivity == Sensitivity.LOW:
        return SecureResult(
            status=SecureStatus.NOT_APPLICABLE, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    if cookie.secure:
        return SecureResult(
            status=SecureStatus.REJECTED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    # SameSite=None without Secure violates the spec regardless of observed scheme.
    if cookie.samesite and cookie.samesite.lower() == "none":
        return SecureResult(
            status=SecureStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    if scheme == "https":
        return SecureResult(
            status=SecureStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    return SecureResult(
        status=SecureStatus.CANDIDATE, confidence="medium",
        cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
    )
