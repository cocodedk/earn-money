"""Finding persistence for stub 1.14 runner.

``emit_finding`` is the per-(asset, attempted-map) hook the runner
calls. It owns the optional map fetch, classification, evidence
chaining, and the Finding row write. Internals (``_save_finding``,
``_finding_data``) stay private to this module.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

from apps.findings.models import Finding
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .classify import ReferenceType, Verdict, classify_map_result
from .fetcher import FetchOutcome, fetch_url
from .parser import Asset
from .resolver import ResolvedMapUrl
from .runner_evidence import save_map_evidence
from .validator import SourceMapMetadata, parse_source_map


FINDING_SOURCE = "source_maps"


def emit_finding(
    scan_run: ScanRun, target: ScanTarget, asset: Asset,
    asset_outcome: FetchOutcome, resolved: ResolvedMapUrl,
    base_origin: str, asset_evidence_id: str,
    reference_type: ReferenceType,
) -> None:
    map_outcome: FetchOutcome | None = None
    metadata: SourceMapMetadata | None = None
    map_evidence_id: str | None = None

    if resolved.kind == "ok" and resolved.absolute_url is not None:
        map_outcome = fetch_url(resolved.absolute_url, base_origin)
        if map_outcome.kind == "ok":
            metadata = parse_source_map(map_outcome.body)
        map_evidence_id = str(
            save_map_evidence(scan_run, target, resolved, map_outcome).id,
        )

    verdict = classify_map_result(
        resolved=resolved, map_outcome=map_outcome,
        metadata=metadata, reference_type=reference_type,
    )
    evidence_ids = [asset_evidence_id]
    if map_evidence_id is not None:
        evidence_ids.append(map_evidence_id)
    _save_finding(
        scan_run, target, asset, asset_outcome, resolved, map_outcome,
        metadata, verdict, evidence_ids,
    )


def _save_finding(
    scan_run: ScanRun, target: ScanTarget, asset: Asset,
    asset_outcome: FetchOutcome, resolved: ResolvedMapUrl,
    map_outcome: FetchOutcome | None,
    metadata: SourceMapMetadata | None,
    verdict: Verdict, evidence_ids: list[str],
) -> Finding:
    finding = Finding(
        scan_run=scan_run, target=target, stub_slug=scan_run.stub_slug,
        title=f"Source map: {verdict.finding_status.value}",
        category="source_maps", severity=verdict.severity,
        confidence=verdict.confidence, status=verdict.finding_status,
        data=_finding_data(
            asset, asset_outcome, resolved, map_outcome,
            metadata, verdict, evidence_ids,
        ),
    )
    finding.save()
    return finding


def _finding_data(
    asset: Asset, asset_outcome: FetchOutcome,
    resolved: ResolvedMapUrl, map_outcome: FetchOutcome | None,
    metadata: SourceMapMetadata | None, verdict: Verdict,
    evidence_ids: list[str],
) -> dict:
    data: dict = {
        "asset_url": asset.url, "asset_kind": asset.kind,
        "asset_final_url": asset_outcome.final_url,
        "map_url": resolved.absolute_url,
        "map_reference_type": verdict.map_reference_type,
        "indicators": verdict.indicators,
        "evidence_ids": evidence_ids, "source": FINDING_SOURCE,
    }
    if map_outcome is not None:
        data["map_status"] = map_outcome.status
        data["map_final_url"] = map_outcome.final_url
    if metadata is not None:
        data["source_map_version"] = metadata.version
        data["sources_count"] = metadata.sources_count
        data["has_sources_content"] = metadata.has_sources_content
        data["source_path_samples"] = metadata.source_path_samples
        data["source_path_categories"] = metadata.source_path_categories
        data["internal_path_indicators"] = metadata.internal_path_indicators
    return data
