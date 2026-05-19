"""Per-asset source-map classifier (stub 1.14 slice 6).

Composes outputs from prior slices into one Verdict per (asset,
map) pair per spec §Classification + §Confidence rules + §Finding
status rules.

Status / confidence / severity decisions are deterministic — no AI,
no remote calls, no host-name heuristics. The runner persists one
SourceMapFinding row per verdict.

MVP deferred (spec items not blocking compliance):
* `stale` finding status — needs cross-run state (last-seen).
* Severity `medium` — needs a shared deterministic secret detector.
  Spec explicitly bans raising to medium on source-map exposure
  alone.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from apps.findings.models import FindingStatus, Severity

from .._shared.types import Confidence
from .fetcher import FetchOutcome
from .resolver import ResolvedMapUrl
from .validator import SourceMapMetadata


ReferenceType = Literal["comment", "fallback", "inline_data_url"]


@dataclass(frozen=True)
class Verdict:
    """One verdict per (asset, attempted map) pair. Persists onto
    a SourceMapFinding row via the runner."""
    finding_status: FindingStatus
    confidence: Confidence
    severity: Severity
    map_reference_type: ReferenceType
    indicators: tuple[str, ...]


def classify_map_result(
    *,
    resolved: ResolvedMapUrl,
    map_outcome: FetchOutcome | None,
    metadata: SourceMapMetadata | None,
    reference_type: Literal["comment", "fallback"],
) -> Verdict:
    """Reduce the per-slice outcomes into one Verdict.

    Priority order (each branch is mutually exclusive):

    1. Resolver said inline → candidate, low, info, inline_data_url.
    2. Resolver said cross_origin or invalid → rejected, low.
    3. Map fetched ok + valid Source Map v3 metadata → confirmed,
       high (comment) / medium (fallback), severity raises to low
       when sourcesContent or internal path indicators present.
    4. Map fetched ok but not a parseable source map → candidate,
       low (malformed).
    5. Map fetched blocked or inconclusive → candidate, low.
    6. Map fetched absent (404/410) → rejected, low.
    """
    if resolved.kind == "inline_data_url":
        return Verdict(
            finding_status=FindingStatus.CANDIDATE,
            confidence="low", severity=Severity.INFO,
            map_reference_type="inline_data_url",
            indicators=("inline_data_url_not_decoded",),
        )
    if resolved.kind == "cross_origin":
        return Verdict(
            finding_status=FindingStatus.REJECTED,
            confidence="low", severity=Severity.INFO,
            map_reference_type=reference_type,
            indicators=("cross_origin_map_rejected",),
        )
    if resolved.kind == "invalid":
        return Verdict(
            finding_status=FindingStatus.REJECTED,
            confidence="low", severity=Severity.INFO,
            map_reference_type=reference_type,
            indicators=("invalid_map_reference",),
        )

    # resolved.kind == "ok" — map fetch should have been attempted.
    # Use a durable RuntimeError rather than `assert` so the contract
    # survives `python -O`. The runner owns this invariant.
    if map_outcome is None:
        raise RuntimeError("ok-resolved must come with map_outcome")
    return _from_map_outcome(map_outcome, metadata, reference_type)


def _from_map_outcome(
    map_outcome: FetchOutcome,
    metadata: SourceMapMetadata | None,
    reference_type: Literal["comment", "fallback"],
) -> Verdict:
    if map_outcome.kind == "ok" and metadata is not None:
        return _confirmed(metadata, reference_type)
    if map_outcome.kind == "ok":
        return Verdict(
            finding_status=FindingStatus.CANDIDATE,
            confidence="low", severity=Severity.INFO,
            map_reference_type=reference_type,
            indicators=("malformed_or_not_source_map",),
        )
    if map_outcome.kind == "absent":
        return Verdict(
            finding_status=FindingStatus.REJECTED,
            confidence="low", severity=Severity.INFO,
            map_reference_type=reference_type,
            indicators=("map_not_found",),
        )
    if map_outcome.kind == "blocked":
        return Verdict(
            finding_status=FindingStatus.CANDIDATE,
            confidence="low", severity=Severity.INFO,
            map_reference_type=reference_type,
            indicators=("blocked_map",),
        )
    return Verdict(
        finding_status=FindingStatus.CANDIDATE,
        confidence="low", severity=Severity.INFO,
        map_reference_type=reference_type,
        indicators=("transient_or_inconclusive",),
    )


def _confirmed(
    metadata: SourceMapMetadata,
    reference_type: Literal["comment", "fallback"],
) -> Verdict:
    confidence: Confidence = (
        "high" if reference_type == "comment" else "medium"
    )
    indicators: list[str] = ["valid_source_map"]
    if metadata.has_sources_content:
        indicators.append("sources_content_exposed")
    if metadata.internal_path_indicators:
        indicators.append("internal_path_indicators_present")
    severity = (
        Severity.LOW
        if metadata.has_sources_content or metadata.internal_path_indicators
        else Severity.INFO
    )
    return Verdict(
        finding_status=FindingStatus.CONFIRMED,
        confidence=confidence, severity=severity,
        map_reference_type=reference_type,
        indicators=tuple(indicators),
    )
