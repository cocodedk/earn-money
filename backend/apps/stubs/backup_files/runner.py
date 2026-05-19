"""Stub 1.7 runner — registered against stub_slug "1.7".

For each surviving probe (non-404, non-SPA-shell, non-transport-error),
emit one Finding tagged with the candidate's `source_kind`
(archive / db_dump / secret_file / config_file / vcs_leak /
os_metadata). Confidence is high — these paths are deny-by-default
and any non-404 reachable response is a real leak.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/07-backup-files.md
"""
from __future__ import annotations

from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from .fetcher import fetch_evidence


_FINDING_SOURCE = "backup_files"


@register("1.7")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    bundle = fetch_evidence(target.base_url)
    responses = bundle["responses"]
    if not responses:
        return

    evidences, findings = _build_rows(
        responses=responses, scan_run=scan_run, target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        Finding.objects.bulk_create(findings)


def _build_rows(
    responses: dict[str, dict],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []

    # Every Finding uses confidence="high": the fetcher already filtered
    # 404s and SPA-shell responses, so a 2xx survival on a deny-by-
    # default path IS a real leak — source_kind varies the category,
    # not the certainty.
    for path, response in responses.items():
        source_kind = response["source_kind"]
        url = urljoin(target.base_url, path)
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.PATH,
            url=url,
            method="GET",
            field=source_kind,
            matched_value=path,
            raw_excerpt=f"{source_kind}: {path} (status {response['status']})"[:200],
            data={
                "path": path,
                "source_kind": source_kind,
                "status": response["status"],
                "content_type": response["content_type"],
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"Backup-file leak: {path} ({source_kind})",
                category=source_kind,
                severity=Severity.INFO,
                confidence="high",
                status=FindingStatus.CANDIDATE,
                data={
                    "path": path,
                    "source_kind": source_kind,
                    "status": response["status"],
                    "evidence_ids": [str(evidence.id)],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings
