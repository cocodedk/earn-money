"""Response classification for stub 1.12.

Maps a `FetchOutcome` + optional `ParsedSitemap` → `Verdict` per
spec §Classification. All decisions are pure; no I/O.

MVP scope: classify a single response. Aggregating multiple sitemap
responses (sitemap index + children) into a higher-level finding
is the runner's job.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/12-sitemap-xml.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NamedTuple

from apps.findings.models import FindingStatus

from .._shared.types import Confidence
from .parser import ParsedSitemap


FetchKind = Literal["ok", "too_large", "unreachable"]


@dataclass(frozen=True)
class FetchOutcome:
    """What the fetcher saw. `status`/`body` are populated only for
    `kind == "ok"`. `final_url` is the requested URL after redirects."""
    kind: FetchKind
    status: int | None
    body: str
    final_url: str


class Verdict(NamedTuple):
    classification: str
    finding_status: FindingStatus
    confidence: Confidence
    indicators: list[str]


_OK_STATUSES = {200, 204}
_PROTECTED_STATUSES = {401, 403}
_NOT_FOUND_STATUSES = {404, 410}


def classify_response(
    outcome: FetchOutcome, *, parsed: ParsedSitemap | None,
) -> Verdict:
    if outcome.kind == "too_large":
        return Verdict(
            "sitemap_too_large", FindingStatus.CANDIDATE, "low",
            ["sitemap_too_large"],
        )
    if outcome.kind == "unreachable":
        return Verdict(
            "sitemap_fetch_error", FindingStatus.REJECTED, "low",
            ["unreachable"],
        )

    status = outcome.status
    if status in _PROTECTED_STATUSES:
        return Verdict(
            "protected", FindingStatus.CANDIDATE, "medium", [],
        )
    if status in _NOT_FOUND_STATUSES:
        return Verdict(
            "not_found", FindingStatus.REJECTED, "low", [],
        )
    if status is not None and 500 <= status < 600:
        return Verdict(
            "sitemap_fetch_error", FindingStatus.CANDIDATE, "low",
            [f"status:{status}"],
        )
    if status in _OK_STATUSES:
        return _classify_ok(parsed)

    return Verdict(
        "client_error", FindingStatus.REJECTED, "low", [],
    )


def _classify_ok(parsed: ParsedSitemap | None) -> Verdict:
    """200 / 204 — classification depends on what the parser made of
    the body. `unknown` kind = body didn't look like a sitemap at
    all (HTML, garbage); classifier records it as a parse-error
    candidate so the operator can spot it without surfacing a
    confirmed finding."""
    if parsed is None or parsed.kind == "unknown":
        return Verdict(
            "sitemap_parse_error", FindingStatus.CANDIDATE, "low",
            ["unparseable_body"],
        )
    if parsed.kind == "sitemapindex":
        return Verdict(
            "sitemap_index_present", FindingStatus.CONFIRMED, "high",
            [f"child_count:{len(parsed.entries)}"],
        )
    return Verdict(
        "sitemap_present", FindingStatus.CONFIRMED, "high",
        [f"url_count:{len(parsed.entries)}"],
    )
