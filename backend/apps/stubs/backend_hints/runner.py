"""Stub 1.4 runner — registered against stub_slug "1.4".

Multi-probe backend fingerprinting: fetch /, /api/, /__scanner_404_*,
match the signature library against each probe's headers/cookies/body,
group matches by technology, and emit one Finding per technology with
one Evidence per matched signature.

Evidence rows carry the ACTUAL probe URL that fired (not the base URL)
and the ACTUAL matched value (not just the signature pattern) so the
triage UI can show operators exactly what evidence supports each hint.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/04-backend-hints.md
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.confidence import max_confidence
from apps.findings.models import Finding, FindingStatus, Severity
from apps.findings.bulk import bulk_create_findings
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .fetcher import fetch_evidence
from .matcher import extract_version, find_first_match, match_signatures
from .signatures import SIGNATURES


_FINDING_SOURCE = "backend_hints"

# Lossy: body source projects to EvidenceSource.HTML even when the
# probe returned text/plain or a JSON error page. The precise origin
# survives on Evidence.field (signature_id for body, cookie name for
# cookies, header name for headers) so the asymmetry is recoverable.
_EVIDENCE_SOURCE_BY_SIG_SOURCE = {
    "header": EvidenceSource.HEADER,
    "cookie": EvidenceSource.COOKIE,
    "body": EvidenceSource.HTML,
}


@guarded_runner("1.4")
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
        bulk_create_findings(findings)


def _build_rows(
    matches: list[dict[str, Any]],
    bundle: dict[str, Any],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []

    by_tech: dict[str, list[dict[str, Any]]] = {}
    for sig in matches:
        by_tech.setdefault(sig["technology"], []).append(sig)

    for technology, sigs in by_tech.items():
        tech_evidences = [
            _build_evidence(sig, bundle, scan_run, target) for sig in sigs
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
    bundle: dict[str, Any],
    scan_run: ScanRun,
    target: ScanTarget,
) -> Evidence:
    sig_source = signature["source"]
    match = find_first_match(signature, bundle)
    probe_path, matched_value = match  # match is not None — sig is in `matches`
    url = urljoin(target.base_url, probe_path)
    return Evidence(
        scan_run=scan_run,
        target=target,
        source=_EVIDENCE_SOURCE_BY_SIG_SOURCE[sig_source],
        url=url,
        method="GET",
        field=_field_for(signature, matched_value),
        matched_value=matched_value,
        raw_excerpt=_excerpt(signature, matched_value),
        data={
            "signature_id": signature["id"],
            "technology": signature["technology"],
            "match_type": signature["match_type"],
            "probe_path": probe_path,
        },
    )


def _field_for(signature: dict[str, Any], matched_value: str) -> str:
    """Evidence.field's discriminator per source: header name for header
    sigs, the matched cookie NAME for cookie sigs, the signature_id
    for body sigs (since the haystack is the whole body)."""
    source = signature["source"]
    if source == "header":
        return signature["field"]
    if source == "cookie":
        return matched_value
    return signature["id"]


def _excerpt(signature: dict[str, Any], matched_value: str) -> str:
    """Short string showing the actual evidence behind the match —
    capped at 200 chars. For body sigs, return a 200-char window
    centred on the needle so operators see surrounding context."""
    source = signature["source"]
    if source != "body":
        return matched_value[:200]
    pattern = signature["value_pattern"]
    idx = matched_value.find(pattern)
    if idx < 0:
        return matched_value[:200]  # pragma: no cover  # defense: matched-by-contains means idx >= 0
    return matched_value[max(0, idx - 40):idx + 160]
