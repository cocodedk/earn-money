"""Composition layer for stub 1.13.

Maps `(canonical FetchOutcome, legacy FetchOutcome, ParsedSecurityTxt) →
Verdict` per spec §Finding rules. The 10 finding types are
prioritised — the worst applicable one wins, and the runner records
others under `indicators` for audit.

Priority (most-severe first):
1. blocked_security_txt   (403/401 on canonical)
2. missing_security_txt   (both absent)
3. malformed_security_txt (present body, no parseable fields)
4. security_txt_no_contact
5. security_txt_expired
6. security_txt_canonical_mismatch
7. security_txt_legacy_only
8. security_txt_conflicting_files
9. security_txt_missing_expires
10. security_txt_present_valid

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/13-security-txt.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Literal, NamedTuple

from apps.findings.models import FindingStatus

from .._shared.types import Confidence
from .parser import ParsedSecurityTxt
from .validators import (
    is_canonical_match,
    is_expired,
    is_valid_contact,
)


FetchKind = Literal["ok", "absent", "blocked", "inconclusive"]


@dataclass(frozen=True)
class FetchOutcome:
    """What the fetcher saw for one candidate URL. `kind="ok"` means
    a `200` with body content; `absent` covers 404/410/204/empty;
    `blocked` covers 401/403; `inconclusive` covers
    timeout/TLS/oversized."""
    kind: FetchKind
    status: int | None
    body: str
    final_url: str


class Verdict(NamedTuple):
    finding_type: str  # one of the 10 spec types
    finding_status: FindingStatus
    confidence: Confidence
    indicators: list[str]


def classify_security_txt(
    *,
    canonical: FetchOutcome | None,
    legacy: FetchOutcome | None,
    parsed: ParsedSecurityTxt | None,
    now: datetime,
) -> Verdict:
    """Pick the single most-severe applicable finding type for the
    pair of fetch outcomes + parsed body. The runner reads the rest
    via `indicators` and the persisted Evidence rows."""
    canonical_kind = canonical.kind if canonical else "absent"
    legacy_kind = legacy.kind if legacy else "absent"

    if canonical_kind == "blocked":
        return Verdict(
            "blocked_security_txt", FindingStatus.CONFIRMED, "high",
            [f"canonical_status:{canonical.status}"]
            if canonical else [],
        )
    if canonical_kind != "ok" and legacy_kind != "ok":
        confidence: Confidence = (
            "high"
            if canonical_kind == "absent" and legacy_kind == "absent"
            else "medium"
        )
        return Verdict(
            "missing_security_txt", FindingStatus.CONFIRMED, confidence,
            [f"canonical:{canonical_kind}", f"legacy:{legacy_kind}"],
        )

    # At least one path is `ok`. Promote the legacy file when canonical
    # was absent — the runner only has the legacy body to validate.
    primary = canonical if canonical_kind == "ok" else legacy
    assert primary is not None and parsed is not None, (
        "ok kind requires populated outcome + parsed result"
    )

    indicators: list[str] = []
    has_valid_contact = any(is_valid_contact(c) for c in parsed.contact)
    has_expires = bool(parsed.expires)
    expired = any(
        is_expired(value, now=now) for value in parsed.expires
    ) if parsed.expires else False
    canonical_matches = (
        any(is_canonical_match(c, final_url=primary.final_url)
            for c in parsed.canonical)
        if parsed.canonical else None
    )
    has_any_known_field = (
        bool(parsed.contact) or has_expires or bool(parsed.canonical)
        or bool(parsed.policy) or bool(parsed.encryption)
    )

    if not has_any_known_field:
        return Verdict(
            "malformed_security_txt", FindingStatus.CONFIRMED, "high",
            ["no_parseable_fields"]
            + [f"parse_error:{e}" for e in parsed.parse_errors[:3]],
        )
    if not has_valid_contact:
        return Verdict(
            "security_txt_no_contact", FindingStatus.CONFIRMED, "high",
            ["no_valid_contact"],
        )
    if expired:
        indicators.append("expired")
        return Verdict(
            "security_txt_expired", FindingStatus.CONFIRMED, "high",
            indicators,
        )
    if canonical_matches is False:
        return Verdict(
            "security_txt_canonical_mismatch",
            FindingStatus.CONFIRMED, "medium",
            ["canonical_does_not_match_final_url"],
        )
    if canonical_kind != "ok" and legacy_kind == "ok":
        return Verdict(
            "security_txt_legacy_only",
            FindingStatus.CONFIRMED, "medium",
            ["only_legacy_path_present"],
        )
    if (
        canonical_kind == "ok" and legacy_kind == "ok"
        and _bodies_differ(canonical, legacy)
    ):
        return Verdict(
            "security_txt_conflicting_files",
            FindingStatus.CONFIRMED, "medium",
            ["legacy_body_differs_from_canonical"],
        )
    if not has_expires:
        return Verdict(
            "security_txt_missing_expires",
            FindingStatus.CONFIRMED, "medium",
            ["missing_expires"],
        )
    return Verdict(
        "security_txt_present_valid",
        FindingStatus.CONFIRMED, "high",
        ["valid_contact", "future_expires"],
    )


def _bodies_differ(a: FetchOutcome, b: FetchOutcome) -> bool:
    return _hash_normalised(a.body) != _hash_normalised(b.body)


def _hash_normalised(body: str) -> str:
    """SHA-256 over the body after newline + trailing-whitespace
    normalisation so a single trailing `\\n` doesn't flag both paths
    as conflicting."""
    normalised = "\n".join(
        line.rstrip() for line in body.splitlines()
    ).strip()
    return sha256(normalised.encode("utf-8")).hexdigest()
