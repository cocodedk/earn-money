"""Evidence persistence for stub 1.15 runner.

Two thin wrappers (HTML / bundle) over the shared Evidence model so
each call site reads as the domain action ("save the HTML evidence
row") rather than as a kwarg blob.

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
    a transport failure (caller passes 0; the HTML body is still
    not persisted here — only the bounded excerpt below)."""
    excerpt = f"html: {final_url} (status {status})"
    ev = Evidence(
        scan_run=scan_run, target=target,
        source=EvidenceSource.HTML,
        url=final_url, method="GET", field="html",
        matched_value="html",
        raw_excerpt=excerpt[:_RAW_EXCERPT_CAP],
        data={"status": status, "discovered_from_url": html_url},
    )
    ev.save()
    return ev


def save_bundle_evidence(
    scan_run: ScanRun, target: ScanTarget,
    candidate: BundleCandidate, outcome: BundleFetchOutcome,
) -> Evidence:
    """One Evidence row per bundle fetch — regardless of outcome
    kind. The bundle hash carries over to content_hash so downstream
    triage can correlate the same bundle across runs."""
    excerpt = (
        f"{outcome.kind}: {outcome.final_url} "
        f"(status {outcome.status or 0})"
    )
    ev = Evidence(
        scan_run=scan_run, target=target,
        source=EvidenceSource.SCRIPT,
        url=outcome.final_url, method="GET",
        field=candidate.discovery_method,
        matched_value=candidate.script_type,
        raw_excerpt=excerpt[:_RAW_EXCERPT_CAP],
        content_hash=outcome.sha256 or "",
        data={
            "kind": outcome.kind,
            "status": outcome.status,
            "content_type": outcome.content_type,
            "truncated": outcome.truncated,
            "bytes_read": outcome.bytes_read,
        },
    )
    ev.save()
    return ev
