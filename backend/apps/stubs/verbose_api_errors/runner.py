"""Stub 1.17 runner — registered against stub_slug "1.17".

Two probes per target: the base_url baseline + one safe
nonexistent-API-sibling probe (`/api/__scanner_nonexistent_<nonce>__`)
to trigger framework 404/route errors. Each response is matched +
classified; on a non-None verdict the runner emits one
VerboseApiErrorFinding row.

MVP deferred (tracked):
* Endpoint discovery from prior Evidence — current pass probes
  only base_url + one API-prefix non-existent route.
* Invalid-path-identifier probe + invalid-query-parameter probe
  (spec §"Probe plan" 3 & 4) — require known endpoints.
* OPTIONS probe — same gating.
* Cross-run idempotence + stale flip — tied to runner idempotence
  work across Phase 1.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

import secrets

from django.db import transaction

from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from .classifier import classify
from .fetcher import fetch_response
from .indicators import detect_all_indicators
from .runner_evidence import save_response_evidence
from .runner_findings import emit_finding


@register("1.17")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    base_url = target.base_url
    entry_url = base_url if base_url.endswith("/") else base_url + "/"
    nonce = secrets.token_hex(6)
    api_probe_url = entry_url + f"api/__scanner_nonexistent_{nonce}__"

    for requested_url, probe_kind in (
        (entry_url, "baseline"),
        (api_probe_url, "nonexistent_api_sibling"),
    ):
        _process_probe(scan_run, target, requested_url, probe_kind)


def _process_probe(
    scan_run: ScanRun, target: ScanTarget,
    requested_url: str, probe_kind: str,
) -> None:
    snapshot = fetch_response(requested_url)
    indicators = (
        detect_all_indicators(snapshot.body, snapshot.content_type)
        if snapshot.body else []
    )
    verdict = classify(indicators, response_status=snapshot.status)
    with transaction.atomic():
        evidence = save_response_evidence(
            scan_run, target,
            requested_url=requested_url, probe_kind=probe_kind,
            snapshot=snapshot,
        )
        if verdict is None:
            return
        emit_finding(
            scan_run, target,
            snapshot=snapshot, indicators=indicators, verdict=verdict,
            evidence_id=str(evidence.id), probe_kind=probe_kind,
        )
