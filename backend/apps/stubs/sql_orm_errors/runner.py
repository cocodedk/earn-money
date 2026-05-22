"""Stub 1.19 runner — registered against stub_slug "1.19".

Two probes per target:
* baseline GET of `target.base_url`
* one safe malformed-query probe (`?scanner_sql_orm_error_probe_%27`)
  appended to the base — spec §Detection logic §Request plan #3.
  Inert URL-encoded quote sentinel; no SQL operators per
  §Safety §Payload restrictions.

Each response is matched, classified, and (on a non-None verdict)
persisted as a SqlOrmErrorFinding row with redacted excerpt.

MVP deferred (tracked):
* Cross-run idempotence + `stale` flip — same shared infra gap as
  stub 1.16 + 1.17.
* Crawler-driven candidate URL discovery beyond `base_url` — depends
  on Phase 2 crawler MVP per the Phase 1 closeout plan.
* `include_query_param_probe` / `include_path_probe` config knobs —
  always-on MVP; runtime config follows.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from django.db import transaction

from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .classify import classify
from .fetcher import fetch_response
from .runner_evidence import save_response_evidence
from .runner_findings import emit_finding


_PROBE_SENTINEL = "scanner_sql_orm_error_probe_%27"


@guarded_runner("1.19")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    base_url = target.base_url
    entry_url = base_url if base_url.endswith("/") else base_url + "/"
    probe_url = f"{entry_url}?{_PROBE_SENTINEL}"

    with transaction.atomic():
        for requested_url, probe_kind in (
            (entry_url, "baseline"),
            (probe_url, "error_probe"),
        ):
            _process_probe(scan_run, target, requested_url, probe_kind)


def _process_probe(
    scan_run: ScanRun, target: ScanTarget,
    requested_url: str, probe_kind: str,
) -> None:
    snapshot = fetch_response(requested_url)
    evidence = save_response_evidence(
        scan_run, target,
        requested_url=requested_url, probe_kind=probe_kind,
        snapshot=snapshot,
    )
    if not snapshot.body:
        return
    verdict = classify(status=snapshot.status, body=snapshot.body)
    if verdict is None:
        return
    emit_finding(
        scan_run, target,
        snapshot=snapshot, verdict=verdict,
        evidence_ids=[str(evidence.id)], requested_url=requested_url,
    )
