"""Stub 1.14 runner — registered against stub_slug "1.14".

Per-scan pass (one ScanTargetRun → one base_url):

1. Fetch the HTML at base_url. Diagnostic Evidence row written
   regardless of outcome.
2. Parse same-origin JS/CSS assets out of the HTML body
   (parser.parse_html_assets) — bounded by spec max_assets=50.
3. For each asset:
   a. Fetch the asset; persist Evidence(source=SCRIPT|CSS).
   b. If asset body has a sourceMappingURL comment → resolve and
      attempt map fetch with reference_type="comment".
   c. Otherwise → probe ``{asset_url}.map`` once with
      reference_type="fallback".
4. Classify (classify_map_result) and persist a Finding per
   (asset, attempted map) pair.

MVP deferred (tracked):
* Cross-run idempotence — current pass always creates new rows.
* `stale` status — needs cross-run state.
* Connection-pool reuse — see #126.
* HTML asset walker lift — see #123.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding
from apps.scans.models import ScanRun, ScanTargetRun

from .._shared.url import origin
from ..runners import register
from .classify import Verdict, classify_map_result
from .fetcher import FetchOutcome, fetch_url
from .parser import Asset, extract_source_mapping_url, parse_html_assets
from .resolver import ResolvedMapUrl, resolve_map_url
from .validator import SourceMapMetadata, parse_source_map


_RAW_EXCERPT_CAP = 200
_FINDING_SOURCE = "source_maps"
_ASSET_KIND_TO_SOURCE = {
    "javascript": EvidenceSource.SCRIPT,
    "css": EvidenceSource.CSS,
}


@register("1.14")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    base_url = target.base_url
    base_origin = origin(base_url)
    # Bare base_urls like "https://x.example" leave the GET path
    # empty; normalise to "https://x.example/" so the runner always
    # probes a canonical resource and downstream urljoin resolves
    # relative asset paths against the root.
    html_url = base_url if base_url.endswith("/") else base_url + "/"
    html_outcome = fetch_url(html_url, base_origin)

    with transaction.atomic():
        _save_html_evidence(scan_run, target, html_outcome)
        if html_outcome.kind != "ok":
            return
        for asset in parse_html_assets(html_outcome.body, html_url):
            _process_asset(scan_run, target, asset, base_origin)


def _process_asset(
    scan_run: ScanRun, target, asset: Asset, base_origin: str,
) -> None:
    """Fetch the asset, then run the sourceMappingURL comment +
    `.map` fallback paths. Each path that yields a verdict gets one
    Finding row."""
    asset_outcome = fetch_url(asset.url, base_origin)
    asset_evidence = _save_asset_evidence(
        scan_run, target, asset, asset_outcome,
    )
    if asset_outcome.kind != "ok":
        return

    raw_value = extract_source_mapping_url(asset_outcome.body, asset.kind)
    if raw_value is not None:
        resolved = resolve_map_url(raw_value, asset_outcome.final_url)
        _emit_finding(
            scan_run, target, asset, asset_outcome, resolved,
            base_origin, asset_evidence_id=str(asset_evidence.id),
            reference_type="comment",
        )
        return

    # Fallback probe path: the asset was ok and same-origin (the
    # fetcher already enforced that), so the asset_url + ".map"
    # always resolves to a same-origin URL — no need to re-check.
    fallback_url = _fallback_map_url(asset_outcome.final_url)
    resolved = resolve_map_url(fallback_url, asset_outcome.final_url)
    _emit_finding(
        scan_run, target, asset, asset_outcome, resolved,
        base_origin, asset_evidence_id=str(asset_evidence.id),
        reference_type="fallback",
    )


def _emit_finding(
    scan_run: ScanRun, target, asset: Asset,
    asset_outcome: FetchOutcome, resolved: ResolvedMapUrl,
    base_origin: str, asset_evidence_id: str,
    reference_type,
) -> None:
    map_outcome: FetchOutcome | None = None
    metadata: SourceMapMetadata | None = None
    map_evidence_id: str | None = None

    if resolved.kind == "ok" and resolved.absolute_url is not None:
        map_outcome = fetch_url(resolved.absolute_url, base_origin)
        if map_outcome.kind == "ok":
            metadata = parse_source_map(map_outcome.body)
        map_evidence_id = str(
            _save_map_evidence(scan_run, target, resolved, map_outcome).id,
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


def _save_html_evidence(
    scan_run: ScanRun, target, outcome: FetchOutcome,
) -> Evidence:
    return _save_evidence(
        scan_run=scan_run, target=target, source=EvidenceSource.HTML,
        url=outcome.final_url, outcome=outcome,
        matched_value="html",
    )


def _save_asset_evidence(
    scan_run: ScanRun, target, asset: Asset, outcome: FetchOutcome,
) -> Evidence:
    return _save_evidence(
        scan_run=scan_run, target=target,
        source=_ASSET_KIND_TO_SOURCE[asset.kind],
        url=outcome.final_url or asset.url, outcome=outcome,
        matched_value=asset.kind,
    )


def _save_map_evidence(
    scan_run: ScanRun, target, resolved: ResolvedMapUrl,
    outcome: FetchOutcome,
) -> Evidence:
    map_url = outcome.final_url or resolved.absolute_url or ""
    return _save_evidence(
        scan_run=scan_run, target=target, source=EvidenceSource.PATH,
        url=map_url, outcome=outcome, matched_value="source_map",
    )


def _save_evidence(
    *, scan_run: ScanRun, target, source: str, url: str,
    outcome: FetchOutcome, matched_value: str,
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


def _save_finding(
    scan_run: ScanRun, target, asset: Asset,
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
        "indicators": list(verdict.indicators),
        "evidence_ids": evidence_ids, "source": _FINDING_SOURCE,
    }
    if map_outcome is not None:
        data["map_status"] = map_outcome.status
        data["map_final_url"] = map_outcome.final_url
    if metadata is not None:
        data["source_map_version"] = metadata.version
        data["sources_count"] = metadata.sources_count
        data["has_sources_content"] = metadata.has_sources_content
        data["source_path_samples"] = list(metadata.source_path_samples)
        data["source_path_categories"] = list(metadata.source_path_categories)
        data["internal_path_indicators"] = list(
            metadata.internal_path_indicators,
        )
    return data


def _fallback_map_url(asset_final_url: str) -> str:
    """Spec §Common .map fallback probing: strip query + fragment,
    append ``.map`` to the path. Single deterministic probe per
    asset — no wordlists, no parent-directory walks."""
    parts = urlsplit(asset_final_url)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path + ".map", "", ""),
    )
