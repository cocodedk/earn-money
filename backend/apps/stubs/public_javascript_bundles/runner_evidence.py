"""Evidence persistence for stub 1.15 runner.

Two thin wrappers (HTML / bundle) over a private ``_save_evidence``
helper — mirrors the stub-1.14 pattern. Each call site reads as the
domain action ("save the HTML evidence row") rather than as a
kwarg blob.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

from apps.evidence.models import Evidence, EvidenceSource
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .fetcher import BundleFetchOutcome
from .parser import BundleCandidate


_RAW_EXCERPT_CAP = 200


def save_html_evidence(
    scan_run: ScanRun, target: ScanTarget,
    *, html_url: str, final_url: str, status: int,
) -> Evidence:
    """One Evidence row per HTML entry-point fetch. Status 0 marks
    a transport failure (caller passes 0)."""
    return _save_evidence(
        scan_run=scan_run, target=target,
        source=EvidenceSource.HTML,
        url=final_url, field="html", matched_value="html",
        excerpt=f"html: {final_url} (status {status})",
        content_hash="",
        data={"status": status, "discovered_from_url": html_url},
    )


def save_bundle_evidence(
    scan_run: ScanRun, target: ScanTarget,
    candidate: BundleCandidate, outcome: BundleFetchOutcome,
) -> Evidence:
    """One Evidence row per bundle fetch — regardless of outcome
    kind. The bundle hash carries over to content_hash so downstream
    triage can correlate the same bundle across runs."""
    return _save_evidence(
        scan_run=scan_run, target=target,
        source=EvidenceSource.SCRIPT,
        url=outcome.final_url,
        field=candidate.discovery_method,
        matched_value=candidate.script_type,
        excerpt=(
            f"{outcome.kind}: {outcome.final_url} "
            f"(status {outcome.status or 0})"
        ),
        content_hash=outcome.sha256 or "",
        data={
            "kind": outcome.kind,
            "status": outcome.status,
            "content_type": outcome.content_type,
            "truncated": outcome.truncated,
            "bytes_read": outcome.bytes_read,
        },
    )


def _save_evidence(
    *, scan_run: ScanRun, target: ScanTarget, source: EvidenceSource,
    url: str, field: str, matched_value: str, excerpt: str,
    content_hash: str, data: dict,
) -> Evidence:
    ev = Evidence(
        scan_run=scan_run, target=target, source=source,
        url=url, method="GET", field=field,
        matched_value=matched_value,
        raw_excerpt=excerpt[:_RAW_EXCERPT_CAP],
        content_hash=content_hash, data=data,
    )
    ev.save()
    return ev
