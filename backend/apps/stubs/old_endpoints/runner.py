"""Stub 1.9 runner — registered against stub_slug "1.9".

Discovers legacy/deprecated endpoints via:
1. fetch_evidence: GET / + 3 random control nonces + each seeded path
2. classify each non-control probe per spec §6/§7 decision table
3. Persist Evidence + Finding pairs in one atomic transaction

MVP deferred (tracked separately): discovered_paths input wiring,
version-shadow generation, cross-run idempotence + stale tracking,
soft-404 hash-based dedup (current MVP uses baseline-body equality).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/09-old-endpoints.md
"""
from __future__ import annotations

from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from .classify import Verdict, classify_probe
from .fetcher import fetch_evidence


_FINDING_SOURCE = "old_endpoints"
_CONTROL_MARKER = "__scanner_control_"


@register("1.9")
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
        Finding.objects.bulk_create(findings)


def _classify_all(
    probes: dict[str, dict], baseline_body: str,
) -> list[tuple[str, dict, Verdict]]:
    """Per spec §6: control probes themselves are NOT classified —
    they're the soft-404 reference. Skip them by their nonce marker."""
    out: list[tuple[str, dict, Verdict]] = []
    for path, probe in probes.items():
        if _CONTROL_MARKER in path:
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
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.PATH,
            url=url,
            method="GET",
            field=verdict.classification,
            matched_value=path,
            raw_excerpt=(
                f"{verdict.classification}: {path} "
                f"(status {probe['status']})"
            )[:200],
            data={
                "path": path,
                "status": probe["status"],
                "classification": verdict.classification,
                "indicators": verdict.indicators,
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=(
                    f"Old endpoint: {path} "
                    f"({verdict.classification}, "
                    f"status {probe['status']})"
                ),
                category=verdict.classification,
                severity=Severity.INFO,
                confidence=verdict.confidence,
                status=getattr(FindingStatus, verdict.finding_status.upper()),
                data={
                    "finding_type": "old_endpoint",
                    "path": path,
                    "status": probe["status"],
                    "classification": verdict.classification,
                    "indicators": verdict.indicators,
                    "evidence_ids": [str(evidence.id)],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings
