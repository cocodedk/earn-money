"""Stub 3.1 — Missing HttpOnly classification."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity
from apps.stubs._shared.types import Confidence


class HttpOnlyStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class HttpOnlyResult:
    status: HttpOnlyStatus
    confidence: Confidence
    cookie_name: str
    raw_set_cookie: str


def classify_cookie(cookie: ParsedCookie, *, authenticated: bool) -> HttpOnlyResult:
    if cookie.sensitivity == Sensitivity.LOW:
        return HttpOnlyResult(
            status=HttpOnlyStatus.NOT_APPLICABLE,
            confidence="high",
            cookie_name=cookie.name,
            raw_set_cookie=cookie.raw_set_cookie,
        )
    if cookie.httponly:
        return HttpOnlyResult(
            status=HttpOnlyStatus.REJECTED,
            confidence="high",
            cookie_name=cookie.name,
            raw_set_cookie=cookie.raw_set_cookie,
        )
    if authenticated or cookie.sensitivity == Sensitivity.HIGH:
        return HttpOnlyResult(
            status=HttpOnlyStatus.CONFIRMED,
            confidence="high",
            cookie_name=cookie.name,
            raw_set_cookie=cookie.raw_set_cookie,
        )
    return HttpOnlyResult(
        status=HttpOnlyStatus.CANDIDATE,
        confidence="medium",
        cookie_name=cookie.name,
        raw_set_cookie=cookie.raw_set_cookie,
    )
