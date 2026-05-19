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

from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from .._shared.url import origin
from ..runners import register
from .fetcher import fetch_url
from .parser import Asset, extract_source_mapping_url, parse_html_assets
from .resolver import resolve_map_url
from .runner_evidence import save_asset_evidence, save_html_evidence
from .runner_findings import emit_finding


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
        save_html_evidence(scan_run, target, html_outcome)
        if html_outcome.kind != "ok":
            return
        for asset in parse_html_assets(html_outcome.body, html_url):
            _process_asset(scan_run, target, asset, base_origin)


def _process_asset(
    scan_run: ScanRun, target: ScanTarget, asset: Asset, base_origin: str,
) -> None:
    asset_outcome = fetch_url(asset.url, base_origin)
    asset_evidence = save_asset_evidence(
        scan_run, target, asset, asset_outcome,
    )
    if asset_outcome.kind != "ok":
        return

    raw_value = extract_source_mapping_url(asset_outcome.body, asset.kind)
    if raw_value is not None:
        resolved = resolve_map_url(raw_value, asset_outcome.final_url)
        emit_finding(
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
    emit_finding(
        scan_run, target, asset, asset_outcome, resolved,
        base_origin, asset_evidence_id=str(asset_evidence.id),
        reference_type="fallback",
    )


def _fallback_map_url(asset_final_url: str) -> str:
    """Spec §Common .map fallback probing: strip query + fragment,
    append ``.map`` to the path. Single deterministic probe per
    asset — no wordlists, no parent-directory walks."""
    parts = urlsplit(asset_final_url)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path + ".map", "", ""),
    )
