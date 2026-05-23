"""Stub 3.7 — No session invalidation after logout classification."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class InvalidationStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class InvalidationResult:
    status: InvalidationStatus
    confidence: Literal["low", "medium", "high"]
    pre_logout_status: int
    post_logout_status: int


def classify_invalidation(
    pre_logout_status: int, post_logout_status: int,
) -> InvalidationResult:
    if not (200 <= pre_logout_status < 300):
        return InvalidationResult(
            status=InvalidationStatus.NOT_APPLICABLE, confidence="high",
            pre_logout_status=pre_logout_status,
            post_logout_status=post_logout_status,
        )
    if 200 <= post_logout_status < 300:
        return InvalidationResult(
            status=InvalidationStatus.CONFIRMED, confidence="high",
            pre_logout_status=pre_logout_status,
            post_logout_status=post_logout_status,
        )
    return InvalidationResult(
        status=InvalidationStatus.REJECTED, confidence="high",
        pre_logout_status=pre_logout_status,
        post_logout_status=post_logout_status,
    )
