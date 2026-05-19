"""Evidence + Finding row construction for stub 1.8 admin-panels.

Bulk-build path: the runner collects every hit, then calls
`build_rows` once, then `bulk_create`s both lists inside one
`transaction.atomic()`. Different shape from source_maps (which
streams per-asset saves to chain evidence_ids) — admin_panels
references each evidence row's id directly inside the same loop
iteration, so the bulk shape stays coherent without back-references.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/08-exposed-admin-panels.md
"""
from __future__ import annotations

from urllib.parse import urljoin

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget


_FINDING_SOURCE = "admin_panels"


def build_rows(
    hits: list[tuple[str, dict, str, str]],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []

    for path, probe, confidence, signal_kind in hits:
        url = urljoin(target.base_url, path)
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.PATH,
            url=url,
            method="GET",
            field=signal_kind,
            matched_value=path,
            raw_excerpt=f"{signal_kind}: {path} (status {probe['status']})"[:200],
            data={
                "path": path,
                "status": probe["status"],
                "signal_kind": signal_kind,
                "location": probe.get("location"),
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"Admin panel exposure: {path} ({signal_kind})",
                category=signal_kind,
                severity=Severity.INFO,
                confidence=confidence,
                status=FindingStatus.CANDIDATE,
                data={
                    "finding_type": "exposed_admin_panel",
                    "path": path,
                    "status": probe["status"],
                    "signal_kind": signal_kind,
                    "evidence_ids": [str(evidence.id)],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings
