"""Stub 3.3 — Weak SameSite classification."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity


class SameSiteStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


class WeaknessKind(str, Enum):
    MISSING_SAMESITE = "missing_samesite"
    EXPLICIT_NONE = "explicit_none"
    NONE_WITHOUT_SECURE = "none_without_secure"
    INVALID_SAMESITE = "invalid_samesite"


@dataclass(frozen=True)
class SameSiteResult:
    status: SameSiteStatus
    confidence: Literal["low", "medium", "high"]
    cookie_name: str
    raw_set_cookie: str
    weakness_kind: Optional[WeaknessKind] = field(default=None)


_VALID_SAMESITE = frozenset({"strict", "lax", "none"})


def classify_cookie(
    cookie: ParsedCookie, *, sso_allowlisted: bool = False,
) -> SameSiteResult:
    if cookie.sensitivity == Sensitivity.LOW or sso_allowlisted:
        return SameSiteResult(
            status=SameSiteStatus.NOT_APPLICABLE, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    if not cookie.samesite:
        return SameSiteResult(
            status=SameSiteStatus.CANDIDATE, confidence="medium",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
            weakness_kind=WeaknessKind.MISSING_SAMESITE,
        )
    ss = cookie.samesite.lower()
    if ss not in _VALID_SAMESITE:
        return SameSiteResult(
            status=SameSiteStatus.CONFIRMED, confidence="medium",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
            weakness_kind=WeaknessKind.INVALID_SAMESITE,
        )
    if ss == "none":
        if not cookie.secure:
            return SameSiteResult(
                status=SameSiteStatus.CONFIRMED, confidence="high",
                cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
                weakness_kind=WeaknessKind.NONE_WITHOUT_SECURE,
            )
        return SameSiteResult(
            status=SameSiteStatus.CANDIDATE, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
            weakness_kind=WeaknessKind.EXPLICIT_NONE,
        )
    return SameSiteResult(
        status=SameSiteStatus.REJECTED, confidence="high",
        cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
    )
