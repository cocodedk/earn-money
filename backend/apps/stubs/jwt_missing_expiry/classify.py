"""Stub 3.11 — JWT missing-expiry classifier."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from apps.stubs._shared.auth.jwt_utils import ParsedJwt
from apps.stubs._shared.types import Confidence, Status

_ACCESS_KINDS = frozenset({"access_token", "id_token", "session_jwt"})


class ExpiryStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ExpiryResult:
    status: ExpiryStatus
    confidence: Confidence
    exp: int | None


def classify_jwt_expiry(
    parsed: ParsedJwt,
    *,
    token_kind: str = "unknown_jwt",
    refresh_expiry_required: bool = False,
) -> ExpiryResult:
    """Classify a JWT for missing or malformed expiry."""
    raw_exp = parsed.payload.get("exp")

    # Malformed (non-numeric, non-None) exp
    if raw_exp is not None and not isinstance(raw_exp, (int, float)):
        return ExpiryResult(
            status=ExpiryStatus.CONFIRMED, confidence="medium", exp=None
        )

    exp = int(raw_exp) if isinstance(raw_exp, (int, float)) and raw_exp else None

    if exp is not None:
        return ExpiryResult(status=ExpiryStatus.REJECTED, confidence="high", exp=exp)

    # Missing exp — severity by token kind
    if token_kind in _ACCESS_KINDS:
        return ExpiryResult(status=ExpiryStatus.CONFIRMED, confidence="high", exp=None)

    if token_kind == "refresh_token":
        if refresh_expiry_required:
            return ExpiryResult(
                status=ExpiryStatus.CONFIRMED, confidence="high", exp=None
            )
        return ExpiryResult(
            status=ExpiryStatus.CANDIDATE, confidence="medium", exp=None
        )

    return ExpiryResult(status=ExpiryStatus.CANDIDATE, confidence="low", exp=None)
