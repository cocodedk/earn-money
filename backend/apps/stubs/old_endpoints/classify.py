"""Pure-function classification for stub 1.9 candidate responses.

Maps an HTTP probe response into a (classification, confidence,
status, indicators) tuple per spec §6 (Classify signature) and §7
(Create finding). No I/O, no DB.

Returns None when the probe should NOT yield a finding (404/410,
soft-404 match, generic fallback, no stale evidence on a live path).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/09-old-endpoints.md
"""
from __future__ import annotations

from typing import NamedTuple

from apps.findings.models import FindingStatus

from .signals import (
    body_has_deprecation_marker,
    header_deprecation_evidence,
    path_has_stale_token_segment,
)


_NOT_FOUND_STATUSES = {404, 410}
_ALIVE_STATUSES = {200, 204, 206}
_AUTH_BOUNDARY_STATUSES = {401, 403}


class Verdict(NamedTuple):
    classification: str  # "alive" | "auth_boundary" | "method_discovery_only"
    finding_status: FindingStatus
    confidence: str  # "low" | "medium" | "high"
    indicators: list[str]  # spec stale_indicators vocabulary


def classify_probe(
    path: str, probe: dict, baseline_body: str,
) -> Verdict | None:
    """Per-probe classification. Returns None when no finding should
    be emitted; otherwise a Verdict ready for persistence."""
    status = probe["status"]
    if status in _NOT_FOUND_STATUSES:
        return None

    headers = probe.get("headers") or {}
    body = probe.get("body") or ""
    header_evidence = header_deprecation_evidence(headers)
    stale_token = path_has_stale_token_segment(path)
    indicators = list(header_evidence)
    if stale_token:
        indicators.append(f"path_token:{stale_token}")

    # Spec §7 row 1: explicit deprecation header → confirmed/high. The
    # presence of any allowlisted deprecation marker is enough; path
    # token isn't required (the header is the server's authority).
    if header_evidence:
        return Verdict(
            "alive", FindingStatus.CONFIRMED, "high", indicators,
        )

    # Spec §7 row 2: deprecation marker in the body → confirmed/high.
    # Body markers count only on alive (200/204/206) responses per
    # spec §5 ("from each live response, extract indicators"). 5xx
    # error pages and 3xx redirect bodies routinely echo the requested
    # path back — Express's `<title>Error: Unexpected path: /api/
    # deprecated</title>` would otherwise be read as the server
    # confirming the endpoint's deprecation.
    if (
        status in _ALIVE_STATUSES
        and body
        and body_has_deprecation_marker(body)
    ):
        return Verdict(
            "alive", FindingStatus.CONFIRMED, "high",
            indicators + ["body_marker:deprecation"],
        )

    # Without an explicit marker, we need at least a stale token in the
    # path to consider this an old endpoint at all (per spec §Negative:
    # "must not create a finding for /products/gold" — random live
    # paths aren't endpoints just by responding 200).
    if not stale_token:
        return None

    # Spec §7 row 4: stale-token path returns 401/403 → candidate
    # medium (auth gate on a legacy path is signal but not proof).
    if status in _AUTH_BOUNDARY_STATUSES:
        return Verdict(
            "auth_boundary", FindingStatus.CANDIDATE, "medium", indicators,
        )
    if status == 405:
        return Verdict(
            "method_discovery_only", FindingStatus.CANDIDATE, "medium",
            indicators,
        )

    # Spec §7 row 3: stale-token path is LIVE (200/204/206) with no
    # explicit marker → candidate/medium. Anything outside the alive
    # set (redirects, 5xx, etc.) needs explicit marker evidence per
    # spec §Request discipline — without it, return None.
    if status not in _ALIVE_STATUSES:
        return None

    # Spec §6 generic_fallback rule: body identical to the homepage
    # baseline classifies as fallback, not endpoint hit.
    if body and body == baseline_body:
        return None
    return Verdict(
        "alive", FindingStatus.CANDIDATE, "medium", indicators,
    )
