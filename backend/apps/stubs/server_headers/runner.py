"""Stub 1.2 runner — registered against stub_slug "1.2".

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/02-server-headers.md
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.confidence import confidence_rank
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun

from ..runners import register
from .fetcher import fetch_evidence
from .matcher import extract_version, match_signatures, normalize_headers
from .redaction import redact_headers
from .signatures import SIGNATURES


_FINDING_SOURCE = "server_headers"


@register("1.2")
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
        safe_headers=safe_headers,
        bundle=bundle,
        scan_run=scan_run,
        target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        Finding.objects.bulk_create(findings)


def _build_rows(
    matches: list[dict[str, Any]],
    norm_headers: dict[str, str],
    safe_headers: dict[str, str],
    bundle: dict[str, Any],
    scan_run: ScanRun,
    target: object,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []
    method = bundle.get("method", "GET")
    url = bundle["url"]

    by_tech: dict[str, list[dict[str, Any]]] = {}
    for sig in matches:
        by_tech.setdefault(sig["technology"], []).append(sig)

    for technology, sigs in by_tech.items():
        primary = sigs[0]
        matched_value = _matched_header_value(primary, safe_headers)
        version = extract_version(primary, norm_headers)
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.HEADER,
            url=url,
            method=method,
            field=primary["header_name"],
            matched_value=matched_value,
            raw_excerpt=_excerpt(primary, safe_headers),
            data={
                "signature_id": primary["id"],
                "technology": technology,
                "version": version,
                "match_type": primary["match_type"],
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"{technology} detected on {target.host}",
                category=primary["technology_category"],
                severity=Severity.INFO,
                confidence=_max_confidence(sigs),
                status=FindingStatus.CANDIDATE,
                data={
                    "technology": technology,
                    "technology_category": primary["technology_category"],
                    "version": version,
                    "matched_header_name": primary["header_name"],
                    "matched_header_value": matched_value,
                    "evidence_ids": [str(evidence.id)],
                    "signature_ids": [sig["id"] for sig in sigs],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings


def _matched_header_value(
    signature: dict[str, Any], safe_headers: dict[str, str]
) -> str:
    name = signature["header_name"]
    for key, value in safe_headers.items():
        if key.lower() == name:
            return value
    return ""  # pragma: no cover  # signature matched, so the header is present


def _excerpt(
    signature: dict[str, Any], safe_headers: dict[str, str]
) -> str:
    value = _matched_header_value(signature, safe_headers)
    return f"{signature['header_name']}: {value}"[:200]


def _max_confidence(signatures: list[dict[str, Any]]) -> str:
    return max((sig["confidence"] for sig in signatures), key=confidence_rank)
