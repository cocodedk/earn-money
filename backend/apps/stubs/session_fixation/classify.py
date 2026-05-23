"""Stub 3.5 — Session fixation classification."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from apps.stubs._shared.session.cookie_parser import ParsedCookie
from apps.stubs._shared.session.session_lifecycle import compare_session_cookies


class FixationStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class FixationResult:
    status: FixationStatus
    confidence: Literal["low", "medium", "high"]
    affected_names: list[str] = field(default_factory=list)


def classify_fixation(
    pre_cookies: list[ParsedCookie],
    post_cookies: list[ParsedCookie],
) -> FixationResult:
    result = compare_session_cookies(pre_cookies, post_cookies)
    if result.no_pre_cookie:
        return FixationResult(status=FixationStatus.NOT_APPLICABLE, confidence="high")
    if result.fixed_names:
        return FixationResult(
            status=FixationStatus.CONFIRMED, confidence="high",
            affected_names=result.fixed_names,
        )
    return FixationResult(status=FixationStatus.REJECTED, confidence="high")
