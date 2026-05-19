"""Stub 1.15 runner — registered against stub_slug "1.15".

Orchestrates HTML fetch → bundle-candidate extraction → per-bundle
fetch → extractors → classifier → persist Evidence + Finding rows.

MVP deferred (tracked):
* Cross-run idempotence: signature upsert by (scan_target_id,
  bundle_url). Current pass always creates new rows.
* `stale` status: needs cross-run state. Same MVP shape as stub
  1.14 — classifier never emits stale; runner doesn't yet.
* include_cdn_metadata=true path: today cross-origin candidates
  are always emitted as metadata-only (status=candidate,
  confidence=low) without fetching. The flag isn't read from
  config yet.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

from django.db import transaction

from apps.scans.models import ScanRun, ScanTargetRun

from ..runners import register
from .fetcher import BundleFetcherConfig, fetch_bundle
from .parser import BundleCandidate, extract_bundle_candidates
from .runner_evidence import save_bundle_evidence, save_html_evidence
from .runner_findings import emit_finding, emit_unfetched_finding


_MAX_BUNDLE_COUNT = 50
_HTML_FETCHER_CONFIG = BundleFetcherConfig(max_body_bytes=1_048_576)


@register("1.15")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    base_url = target.base_url
    # Bare base_urls like "https://x.example" leave the GET path
    # empty; normalise to "https://x.example/" so the runner always
    # probes a canonical resource and downstream urljoin resolves
    # relative bundle URLs against the root.
    html_url = base_url if base_url.endswith("/") else base_url + "/"
    # fetch_bundle returns kind="non_js" for text/html but retains
    # the body — we exploit that to share one HTTP layer + one mock
    # harness across both fetch types. Spec §Inputs sizes the HTML
    # budget separately (max_html_bytes=1 MiB) from the bundle
    # budget (max_bundle_bytes=5 MiB), so the HTML call uses a
    # tighter config.
    html_outcome = fetch_bundle(html_url, _HTML_FETCHER_CONFIG)

    with transaction.atomic():
        html_evidence = save_html_evidence(
            scan_run, target,
            html_url=html_url,
            final_url=html_outcome.final_url,
            status=html_outcome.status or 0,
        )
        if not html_outcome.body or html_outcome.status != 200:
            return
        candidates = extract_bundle_candidates(html_outcome.body, html_url)
        html_evidence_id = str(html_evidence.id)
        for candidate in candidates[:_MAX_BUNDLE_COUNT]:
            _process_bundle(
                scan_run, target, candidate,
                html_url=html_url, html_evidence_id=html_evidence_id,
            )


def _process_bundle(
    scan_run: ScanRun, target, candidate: BundleCandidate,
    *, html_url: str, html_evidence_id: str,
) -> None:
    if not candidate.same_origin:
        # include_cdn_metadata=true would change this; tracked above.
        emit_unfetched_finding(
            scan_run, target, candidate,
            html_url=html_url, evidence_ids=[html_evidence_id],
        )
        return
    bundle_outcome = fetch_bundle(candidate.url)
    bundle_evidence = save_bundle_evidence(
        scan_run, target, candidate, bundle_outcome,
    )
    emit_finding(
        scan_run, target, candidate, bundle_outcome,
        html_url=html_url,
        evidence_ids=[html_evidence_id, str(bundle_evidence.id)],
    )


