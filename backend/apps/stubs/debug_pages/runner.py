"""Stub 1.10 runner — registered against stub_slug "1.10".

Discovers exposed debug / profiler / diagnostic surfaces via:
1. fetch_evidence: GET / (baseline) + each SEEDED_PATHS entry
2. classify each non-control probe per spec §Response classification
3. redact secret-like values in the raw_excerpt before persistence
4. persist Evidence + Finding pairs in one atomic transaction

MVP deferred (tracked separately):
- discovered_paths input wiring (extra_paths argument is reserved)
- cross-run idempotence + stale tracking (platform-wide, #82)
- redirect classification (spec §Redirect handling, #86)
- HEAD-first request discipline (spec §Request discipline)

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations

from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, Severity
from apps.findings.bulk import bulk_create_findings
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .classify import Verdict, classify_probe
from .fetcher import CONTROL_MARKER, fetch_evidence
from .redact import redact_secrets


_FINDING_SOURCE = "debug_pages"
_RAW_EXCERPT_CAP = 200


@guarded_runner("1.10")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    bundle = fetch_evidence(target.base_url)
    if bundle["baseline"] is None:
        return

    baseline_body = bundle["baseline"].get("body") or ""
    hits = _classify_all(bundle["probes"], baseline_body)
    if not hits:
        return

    evidences, findings = _build_rows(
        hits=hits, scan_run=scan_run, target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        bulk_create_findings(findings)


def _classify_all(
    probes: dict[str, dict], baseline_body: str,
) -> list[tuple[str, dict, Verdict]]:
    """Per spec §Detection logic: control probes are never classified
    — they're the soft-404 reference. Skip them by their nonce marker."""
    out: list[tuple[str, dict, Verdict]] = []
    for path, probe in probes.items():
        if CONTROL_MARKER in path:
            continue
        verdict = classify_probe(path, probe, baseline_body)
        if verdict is not None:
            out.append((path, probe, verdict))
    return out


def _build_rows(
    hits: list[tuple[str, dict, Verdict]],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []

    for path, probe, verdict in hits:
        url = urljoin(target.base_url, path)
        # Spec §Evidence handling "short redacted snippet": carry a
        # bounded chunk of the response body so the operator can see
        # what triggered the finding. Redaction runs BEFORE truncation
        # — truncating first could split mid-secret and leak a prefix.
        body_snippet = redact_secrets((probe.get("body") or "")[:120])
        excerpt = (
            f"{verdict.kind}: {path} (status {probe['status']}) | "
            f"{body_snippet}"
        )[:_RAW_EXCERPT_CAP]
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.PATH,
            url=url,
            method="GET",
            field=verdict.kind,
            matched_value=path,
            raw_excerpt=excerpt,
            data={
                "path": path,
                "status": probe["status"],
                "kind": verdict.kind,
                "exposure": verdict.exposure,
                "indicators": verdict.indicators,
                "leaked_data_classes": verdict.leaked_data_classes,
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=(
                    f"Debug page: {verdict.kind} at {path} "
                    f"(status {probe['status']})"
                ),
                category=verdict.kind,
                severity=Severity.INFO,
                confidence=verdict.confidence,
                status=verdict.finding_status,
                data={
                    "finding_type": "debug_page",
                    "path": path,
                    "status": probe["status"],
                    "kind": verdict.kind,
                    "exposure": verdict.exposure,
                    "indicators": verdict.indicators,
                    "leaked_data_classes": verdict.leaked_data_classes,
                    "evidence_ids": [str(evidence.id)],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings
