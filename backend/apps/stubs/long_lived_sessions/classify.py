"""Stub 3.8 — Long-lived session detection classification."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Literal, Optional

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity

_DEFAULT_MAX_AGE = 86400  # seconds (24 hours)


class LongLivedStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class LongLivedResult:
    status: LongLivedStatus
    confidence: Literal["low", "medium", "high"]
    cookie_name: str
    observed_max_age: Optional[int]


def classify_cookie(
    cookie: ParsedCookie,
    max_session_age_seconds: int = _DEFAULT_MAX_AGE,
) -> LongLivedResult:
    if cookie.sensitivity == Sensitivity.LOW:
        return LongLivedResult(
            status=LongLivedStatus.NOT_APPLICABLE, confidence="high",
            cookie_name=cookie.name, observed_max_age=None,
        )
    if cookie.max_age is None and cookie.expires is None:
        return LongLivedResult(
            status=LongLivedStatus.NOT_APPLICABLE, confidence="low",
            cookie_name=cookie.name, observed_max_age=None,
        )
    # Max-Age takes precedence; fall back to Expires if absent.
    if cookie.max_age is not None:
        age = cookie.max_age
    else:
        age = _expires_to_seconds(cookie.expires)
    if age is None:
        return LongLivedResult(
            status=LongLivedStatus.NOT_APPLICABLE, confidence="low",
            cookie_name=cookie.name, observed_max_age=None,
        )
    if age > max_session_age_seconds:
        return LongLivedResult(
            status=LongLivedStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, observed_max_age=age,
        )
    return LongLivedResult(
        status=LongLivedStatus.REJECTED, confidence="high",
        cookie_name=cookie.name, observed_max_age=age,
    )


def _expires_to_seconds(expires: str) -> Optional[int]:
    try:
        dt = parsedate_to_datetime(expires)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        remaining = int((dt - now).total_seconds())
        return max(remaining, 0)
    except Exception:
        return None
