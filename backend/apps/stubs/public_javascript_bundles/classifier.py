"""Confidence + status classifier for stub 1.15 (slice 6).

Spec §5 'Confidence rules' + §6 'Status rules'. Pure function from
two signals — the fetch outcome kind and whether the response's
content-type belongs to the JS allowlist — to a typed verdict.

The classifier is deliberately small: every input is already known
by the time the runner has the fetch result, so packaging the
six-arm decision table here keeps the runner readable. The 'stale'
status is NOT produced here — it's runner-applied during
persistence by comparing against a previously-confirmed signature
on the same (scan_target_id, bundle_url) key.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

from typing import Literal, NamedTuple

from .._shared.types import Confidence
from .fetcher import BundleFetchKind


Status = Literal["candidate", "confirmed", "rejected", "stale"]


class Verdict(NamedTuple):
    confidence: Confidence
    status: Status


def classify(
    *,
    fetch_kind: BundleFetchKind | None,
    content_type_is_js: bool,
) -> Verdict:
    if fetch_kind is None:
        return Verdict(confidence="low", status="candidate")
    if fetch_kind == "ok":
        return Verdict(
            confidence="high" if content_type_is_js else "medium",
            status="confirmed",
        )
    if fetch_kind in ("non_js", "absent"):
        return Verdict(confidence="low", status="rejected")
    # blocked | inconclusive — retry-class, keep as candidate
    return Verdict(confidence="low", status="candidate")
