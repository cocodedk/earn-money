"""Stub 1.16 runner — registered against stub_slug "1.16".

Two probes per target: the base_url entry point + a single safe
missing-route GET for "what does the app return on unknown
routes?". Each response is matched, classified, and (when the
classifier returns a Verdict) persisted as a StackTraceFinding.

MVP deferred (tracked):
* Cross-run idempotence: signature dedupe by
  (target_id, normalized_url_path, signature_family, exception_type,
  top_frame_hash). Current pass creates new rows per scan.
* `stale` flip when a previously-confirmed trace no longer
  reproduces — also tied to the idempotence work.
* "Passive-first" reuse of existing Evidence bodies. Current MVP
  re-fetches the two probes because Evidence.raw_excerpt is bounded
  at 200 chars and the full body isn't persisted.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/16-stack-traces.md
"""
from __future__ import annotations

import secrets

from django.db import transaction

from apps.programs.exceptions import OutOfScope
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.http import resolve_and_guard
from apps.targets.models import ScanTarget

from ..runners import register
from .classifier import classify
from .false_positives import is_documentation_like
from .fetcher import fetch_response
from .matcher import detect_stack_traces, strongest_match
from .runner_evidence import save_response_evidence
from .runner_findings import emit_finding


@register("1.16")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    try:
        resolve_and_guard(scan_run, target, stub_id="1.16")
    except OutOfScope:
        return  # event already emitted; halt this stub
    base_url = target.base_url
    entry_url = base_url if base_url.endswith("/") else base_url + "/"
    probe_url = entry_url + f"__scanner_missing_route_{secrets.token_hex(6)}"

    with transaction.atomic():
        for requested_url, probe_kind in (
            (entry_url, "entry_point"),
            (probe_url, "missing_route"),
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
    matches = detect_stack_traces(snapshot.body, snapshot.content_type)
    verdict = classify(
        matches,
        response_status=snapshot.status,
        is_docs_like=is_documentation_like(
            snapshot.body, status=snapshot.status,
        ),
    )
    if verdict is None:
        return
    emit_finding(
        scan_run, target,
        snapshot=snapshot, match=strongest_match(matches),
        verdict=verdict, evidence_ids=[str(evidence.id)],
        requested_url=requested_url,
    )
