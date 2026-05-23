"""Stub 3.6 — No session rotation after login classification."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from apps.stubs._shared.session.cookie_parser import ParsedCookie
from apps.stubs._shared.session.session_lifecycle import compare_session_cookies
from apps.stubs._shared.types import Confidence


class RotationStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class RotationResult:
    status: RotationStatus
    confidence: Confidence
    affected_names: list[str] = field(default_factory=list)


def classify_rotation(
    pre_cookies: list[ParsedCookie],
    post_cookies: list[ParsedCookie],
) -> RotationResult:
    result = compare_session_cookies(pre_cookies, post_cookies)
    if result.no_pre_cookie:
        return RotationResult(status=RotationStatus.NOT_APPLICABLE, confidence="high")
    if result.fixed_names:
        return RotationResult(
            status=RotationStatus.CONFIRMED, confidence="high",
            affected_names=result.fixed_names,
        )
    return RotationResult(status=RotationStatus.REJECTED, confidence="high")
