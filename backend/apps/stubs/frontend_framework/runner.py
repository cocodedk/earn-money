"""Stub 1.3 runner — registered against stub_slug "1.3".

Per-target flow: fetch base HTML + linked same-origin JS/CSS bodies,
match the signature library against html_body / script_paths /
asset_body sources, group by technology, then for each detected
technology emit one Finding aggregating the strongest confidence
across signatures and one Evidence per matched signature inside one
bulk_create + transaction.atomic.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/03-frontend-framework.md
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
from .matcher import extract_version, match_signatures
from .signatures import SIGNATURES


_FINDING_SOURCE = "frontend_framework"


# Lossy: both script_src_path and asset_body collapse to SCRIPT. The
# triage UI groups by EvidenceSource for headline filtering; the
# precise origin (path vs body) survives on Evidence.field and in
# Evidence.data["signature_id"], so the asymmetry is recoverable.
_EVIDENCE_SOURCE_BY_SIG_SOURCE = {
    "html_body": EvidenceSource.HTML,
    "script_src_path": EvidenceSource.SCRIPT,
    "asset_body": EvidenceSource.SCRIPT,
}


@guarded_runner("1.3")
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
    url = bundle["url"]

    by_tech: dict[str, list[dict[str, Any]]] = {}
    for sig in matches:
        by_tech.setdefault(sig["technology"], []).append(sig)

    for technology, sigs in by_tech.items():
        tech_evidences = [
            _build_evidence(sig, bundle, scan_run, target, url)
            for sig in sigs
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
    url: str,
) -> Evidence:
    sig_source = signature["source"]
    return Evidence(
        scan_run=scan_run,
        target=target,
        source=_EVIDENCE_SOURCE_BY_SIG_SOURCE[sig_source],
        url=url,
        method="GET",
        field=sig_source,
        matched_value=_matched_value_summary(signature),
        raw_excerpt=_excerpt(signature, bundle),
        data={
            "signature_id": signature["id"],
            "technology": signature["technology"],
            "match_type": signature["match_type"],
        },
    )


def _matched_value_summary(signature: dict[str, Any]) -> str:
    pattern = signature["value_pattern"]
    if isinstance(pattern, list):
        return ",".join(pattern)
    return pattern


def _excerpt(
    signature: dict[str, Any], bundle: dict[str, Any]
) -> str:
    """Short context string for the evidence row — capped at 200 chars."""
    sig_source = signature["source"]
    if sig_source == "html_body":
        body = bundle.get("html_body", "")
        return _body_excerpt(signature, body)
    if sig_source == "script_src_path":
        paths = bundle.get("script_paths", [])
        return f"script_paths: {paths}"[:200]
    paths = list(bundle.get("asset_bodies", {}).keys())
    return f"asset_bodies: {paths}"[:200]


def _body_excerpt(signature: dict[str, Any], body: str) -> str:
    pattern = signature["value_pattern"]
    needle = pattern[0] if isinstance(pattern, list) else pattern
    idx = body.find(needle)
    if idx < 0:
        return body[:200]
    return body[max(0, idx - 40):idx + 160]
