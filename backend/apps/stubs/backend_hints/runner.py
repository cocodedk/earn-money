"""Stub 1.4 runner — registered against stub_slug "1.4".

Multi-probe backend fingerprinting: fetch /, /api/, /__scanner_404_*,
match the signature library against each probe's headers/cookies/body,
group matches by technology, and emit one Finding per technology with
one Evidence per matched signature.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/04-backend-hints.md
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.confidence import max_confidence
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from .fetcher import fetch_evidence
from .matcher import extract_version, match_signatures
from .signatures import SIGNATURES


_FINDING_SOURCE = "backend_hints"

_EVIDENCE_SOURCE_BY_SIG_SOURCE = {
    "header": EvidenceSource.HEADER,
    "cookie": EvidenceSource.COOKIE,
    "body": EvidenceSource.HTML,
}


@register("1.4")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    bundle = fetch_evidence(target.base_url)

    matches = match_signatures(SIGNATURES, bundle)
    if not matches:
        return

    evidences, findings = _build_rows(
        matches=matches,
        bundle=bundle,
        scan_run=scan_run,
        target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        Finding.objects.bulk_create(findings)


def _build_rows(
    matches: list[dict[str, Any]],
    bundle: dict[str, Any],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []
    url = target.base_url

    by_tech: dict[str, list[dict[str, Any]]] = {}
    for sig in matches:
        by_tech.setdefault(sig["technology"], []).append(sig)

    for technology, sigs in by_tech.items():
        tech_evidences = [
            _build_evidence(sig, scan_run, target, url) for sig in sigs
        ]
        evidences.extend(tech_evidences)
        primary = sigs[0]
        version = extract_version(primary, bundle)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"{technology} detected on {target.host}",
                category=primary["category"],
                severity=Severity.INFO,
                confidence=max_confidence(sigs),
                status=FindingStatus.CANDIDATE,
                data={
                    "technology": technology,
                    "technology_category": primary["category"],
                    "version": version,
                    "evidence_ids": [str(ev.id) for ev in tech_evidences],
                    "signature_ids": [sig["id"] for sig in sigs],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings


def _build_evidence(
    signature: dict[str, Any],
    scan_run: ScanRun,
    target: ScanTarget,
    url: str,
) -> Evidence:
    sig_source = signature["source"]
    return Evidence(
        scan_run=scan_run,
        target=target,
        source=_EVIDENCE_SOURCE_BY_SIG_SOURCE[sig_source],
        url=url,
        method="GET",
        field=_field_for(signature),
        matched_value=signature["value_pattern"],
        raw_excerpt=f"{sig_source}: {_field_for(signature)} ~ {signature['value_pattern']}"[:200],
        data={
            "signature_id": signature["id"],
            "technology": signature["technology"],
            "match_type": signature["match_type"],
        },
    )


def _field_for(signature: dict[str, Any]) -> str:
    """Header signatures carry an explicit `field`; cookie/body sources
    don't (whole-haystack match). Return a stable string for the
    Evidence.field column either way."""
    if signature["source"] == "header":
        return signature["field"]
    return signature["source"]
