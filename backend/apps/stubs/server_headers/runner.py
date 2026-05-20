"""Stub 1.2 runner — registered against stub_slug "1.2".

Per-target flow: redact response headers (so sensitive values never
reach the matcher or the Evidence rows), normalize them once for
case-insensitive lookups, match the signature library, then for each
detected technology emit one Finding aggregating the strongest
confidence across signatures and one Evidence per matched signature
inside one bulk_create + transaction.atomic. Evidence_ids on the
Finding stays consistent with signature_ids — both have N entries when
N signatures contributed.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/02-server-headers.md
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.confidence import max_confidence
from apps.findings.models import Finding, FindingStatus, Severity
from apps.findings.bulk import bulk_create_findings
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .fetcher import fetch_evidence
from .matcher import extract_version, match_signatures, normalize_headers
from .redaction import redact_headers
from .signatures import SIGNATURES


_FINDING_SOURCE = "server_headers"


@guarded_runner("1.2")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    bundle = fetch_evidence(target.base_url)

    safe_headers = redact_headers(bundle["headers"])
    norm_headers = normalize_headers(safe_headers)

    matches = match_signatures(SIGNATURES, safe_headers)
    if not matches:
        return

    evidences, findings = _build_rows(
        matches=matches,
        norm_headers=norm_headers,
        bundle=bundle,
        scan_run=scan_run,
        target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        bulk_create_findings(findings)


def _build_rows(
    matches: list[dict[str, Any]],
    norm_headers: dict[str, str],
    bundle: dict[str, Any],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []
    method = bundle["method"]
    url = bundle["url"]

    by_tech: dict[str, list[dict[str, Any]]] = {}
    for sig in matches:
        by_tech.setdefault(sig["technology"], []).append(sig)

    for technology, sigs in by_tech.items():
        tech_evidences = [
            _build_evidence(sig, norm_headers, scan_run, target, url, method)
            for sig in sigs
        ]
        evidences.extend(tech_evidences)
        primary = sigs[0]
        primary_value = norm_headers[primary["header_name"]]
        version = extract_version(primary, norm_headers)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"{technology} detected on {target.host}",
                category=primary["technology_category"],
                severity=Severity.INFO,
                confidence=max_confidence(sigs),
                status=FindingStatus.CANDIDATE,
                data={
                    "technology": technology,
                    "technology_category": primary["technology_category"],
                    "version": version,
                    "matched_header_name": primary["header_name"],
                    "matched_header_value": primary_value,
                    "evidence_ids": [str(ev.id) for ev in tech_evidences],
                    "signature_ids": [sig["id"] for sig in sigs],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings


def _build_evidence(
    signature: dict[str, Any],
    norm_headers: dict[str, str],
    scan_run: ScanRun,
    target: ScanTarget,
    url: str,
    method: str,
) -> Evidence:
    name = signature["header_name"]
    value = norm_headers[name]
    return Evidence(
        scan_run=scan_run,
        target=target,
        source=EvidenceSource.HEADER,
        url=url,
        method=method,
        field=name,
        matched_value=value,
        raw_excerpt=f"{name}: {value}"[:200],
        data={
            "signature_id": signature["id"],
            "technology": signature["technology"],
            "match_type": signature["match_type"],
        },
    )
