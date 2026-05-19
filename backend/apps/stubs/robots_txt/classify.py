"""Response classification for stub 1.11.

Maps a `FetchOutcome` (emitted by the fetcher) → `Verdict`
(consumed by the runner). All decisions are pure functions of the
input; no I/O, no DB.

Spec §Response classification table:
- 200 with non-empty body → present / CONFIRMED / high
- 200 with empty body / 204 → empty / CONFIRMED / high
- 401 or 403 → protected / CANDIDATE / medium
- 404 or 410 → not_found / REJECTED
- Other 4xx → client_error / REJECTED
- 5xx → server_error / CANDIDATE / low
- redirect_limit (fetcher saw > max_redirects) → CANDIDATE / low
- cross_origin_blocked (fetcher refused a cross-origin Location) →
  CANDIDATE / low
- unreachable (network / TLS / timeout) → REJECTED / low

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/11-robots-txt.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, NamedTuple

from apps.findings.models import FindingStatus


FetchKind = Literal[
    "ok", "redirect_limit", "cross_origin_blocked", "unreachable",
]


@dataclass(frozen=True)
class FetchOutcome:
    """What the fetcher saw. `status`/`body` are populated only for
    `kind == "ok"`. `final_url` is the URL after any same-origin
    redirects the fetcher followed."""
    kind: FetchKind
    status: int | None
    body: str
    final_url: str
    redirected: bool = False
    # Reserved for future redirect-chain evidence; not used by
    # classify yet but kept on the dataclass so the fetcher can
    # populate it without a shape change.
    redirect_chain: tuple[str, ...] = field(default_factory=tuple)


class Verdict(NamedTuple):
    classification: str
    finding_status: FindingStatus
    confidence: str  # cookbook low|medium|high
    indicators: list[str]


_OK_STATUSES = {200, 204}
_PROTECTED_STATUSES = {401, 403}
_NOT_FOUND_STATUSES = {404, 410}


def classify_response(outcome: FetchOutcome) -> Verdict:
    if outcome.kind == "redirect_limit":
        return Verdict(
            "redirect_limit_exceeded", FindingStatus.CANDIDATE, "low",
            ["redirect_limit_exceeded"],
        )
    if outcome.kind == "cross_origin_blocked":
        return Verdict(
            "cross_origin_redirect_blocked",
            FindingStatus.CANDIDATE, "low",
            ["cross_origin_redirect_blocked"],
        )
    if outcome.kind == "unreachable":
        return Verdict(
            "unreachable", FindingStatus.REJECTED, "low",
            ["unreachable"],
        )

    status = outcome.status
    indicators: list[str] = []
    if outcome.redirected:
        indicators.append("redirected")

    if status in _PROTECTED_STATUSES:
        return Verdict(
            "protected", FindingStatus.CANDIDATE, "medium", indicators,
        )
    if status in _NOT_FOUND_STATUSES:
        return Verdict(
            "not_found", FindingStatus.REJECTED, "low", indicators,
        )
    if status in _OK_STATUSES:
        body = outcome.body or ""
        if not body.strip():
            return Verdict(
                "empty", FindingStatus.CONFIRMED, "high", indicators,
            )
        return Verdict(
            "present", FindingStatus.CONFIRMED, "high", indicators,
        )
    if status is not None and 500 <= status < 600:
        return Verdict(
            "server_error", FindingStatus.CANDIDATE, "low", indicators,
        )
    # Any other 4xx — `client_error` per spec. Status may also be
    # None if the fetcher emitted `ok` without populating it (a
    # contract violation, not a runtime path); fall through to the
    # same rejected/low bucket so the scan doesn't crash.
    return Verdict(
        "client_error", FindingStatus.REJECTED, "low", indicators,
    )
