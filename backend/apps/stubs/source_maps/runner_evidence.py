"""Evidence persistence for stub 1.14 runner.

Three thin wrappers (HTML / asset / map) over one parametrised
``_save_evidence`` so each call site reads as the domain action
("save the HTML evidence row") rather than as a kwarg blob. The
runner imports the three public helpers; ``_save_evidence`` stays
private to this module.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

from apps.evidence.models import Evidence, EvidenceSource
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .fetcher import FetchOutcome
from .parser import Asset
from .resolver import ResolvedMapUrl


_RAW_EXCERPT_CAP = 200
_ASSET_KIND_TO_SOURCE = {
    "javascript": EvidenceSource.SCRIPT,
    "css": EvidenceSource.CSS,
}


def save_html_evidence(
    scan_run: ScanRun, target: ScanTarget, outcome: FetchOutcome,
) -> Evidence:
    return _save_evidence(
        scan_run=scan_run, target=target, source=EvidenceSource.HTML,
        url=outcome.final_url, outcome=outcome, matched_value="html",
    )


def save_asset_evidence(
    scan_run: ScanRun, target: ScanTarget, asset: Asset,
    outcome: FetchOutcome,
) -> Evidence:
    return _save_evidence(
        scan_run=scan_run, target=target,
        source=_ASSET_KIND_TO_SOURCE[asset.kind],
        url=outcome.final_url, outcome=outcome,
        matched_value=asset.kind,
    )


def save_map_evidence(
    scan_run: ScanRun, target: ScanTarget, resolved: ResolvedMapUrl,
    outcome: FetchOutcome,
) -> Evidence:
    return _save_evidence(
        scan_run=scan_run, target=target, source=EvidenceSource.PATH,
        url=outcome.final_url, outcome=outcome,
        matched_value="source_map",
    )


def _save_evidence(
    *, scan_run: ScanRun, target: ScanTarget, source: EvidenceSource,
    url: str, outcome: FetchOutcome, matched_value: str,
) -> Evidence:
    excerpt = f"{outcome.kind}: {url} (status {outcome.status or 0})"
    ev = Evidence(
        scan_run=scan_run, target=target, source=source,
        url=url, method="GET", field=matched_value,
        matched_value=matched_value,
        raw_excerpt=excerpt[:_RAW_EXCERPT_CAP],
        data={
            "kind": outcome.kind, "status": outcome.status,
            "content_type": outcome.content_type,
        },
    )
    ev.save()
    return ev
