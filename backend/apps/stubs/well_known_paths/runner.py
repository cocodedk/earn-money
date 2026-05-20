"""Stub `well_known_paths` runner — registered against stub_slug "1.20".

Soft-404 baseline prelude → per-family candidate iteration → HEAD-first
GET-with-Range fetcher → classifier → redact → persist Evidence +
Finding rows.

One @register("1.20") absorbs cookbook specs 1.20-1.25 (env / git /
config_files / logs / backup_archives / db_dumps). Specs 1.21-1.25
close via frontmatter in slice WKP-D.

MVP deferred (tracked):
* Cross-run idempotence + `stale` flip — shared infra gap, same as
  1.16/1.17/1.19.
* Per-target candidate-path overrides.
* Authenticated-context probes (spec mentions; depends on Phase 2
  auth state machine).

Spec sources: 1.20-1.25.
"""
from __future__ import annotations

from urllib.parse import urljoin

from django.db import transaction

from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from . import soft_404
from .classify import classify
from .families import FAMILIES, FamilySpec
from .fetcher import fetch_response
from .runner_evidence import save_response_evidence
from .runner_findings import emit_finding


_TEXT_FAMILY_CAP = 65_536
_BINARY_FAMILY_CAP = 4_096
_BINARY_FAMILIES = ("backup_archives", "db_dumps")


def _max_bytes_for(family: str) -> int:
    return _BINARY_FAMILY_CAP if family in _BINARY_FAMILIES else _TEXT_FAMILY_CAP


@register("1.20")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    base_url = target.base_url
    base = base_url if base_url.endswith("/") else base_url + "/"

    # Soft-404 baseline prelude — one probe per target.
    baseline_url = urljoin(base, soft_404.random_nonexistent_path().lstrip("/"))
    baseline = fetch_response(baseline_url, max_bytes=_TEXT_FAMILY_CAP)
    footprint = soft_404.footprint_for(status=baseline.status, body=baseline.body)

    with transaction.atomic():
        for fam in FAMILIES:
            _scan_family(scan_run, target, base, fam, footprint)


def _scan_family(
    scan_run: ScanRun, target: ScanTarget, base_url: str,
    fam: FamilySpec, footprint: soft_404.SoftFootprint,
) -> None:
    max_bytes = _max_bytes_for(fam.family)
    for path in fam.candidate_paths:
        url = urljoin(base_url, path.lstrip("/"))
        snapshot = fetch_response(url, max_bytes=max_bytes)
        evidence = save_response_evidence(
            scan_run, target,
            requested_url=url, family=fam.family,
            candidate_path=path, snapshot=snapshot,
        )
        if not snapshot.body:
            continue
        if soft_404.matches_soft_404(
            footprint, status=snapshot.status, body=snapshot.body,
        ):
            continue
        verdict = classify(
            status=snapshot.status, body=snapshot.body,
            family=fam.family, signatures=fam.signatures,
            severity_hint=fam.severity_hint,
        )
        if verdict is None:
            continue
        emit_finding(
            scan_run, target,
            snapshot=snapshot, verdict=verdict,
            evidence_ids=[str(evidence.id)],
            requested_url=url, candidate_path=path,
        )
