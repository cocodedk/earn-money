"""Stub 1.5 runner — registered against stub_slug "1.5".

For each probed dep-manifest response, run the matching parser AND a
banner-regex scan. Emit one Finding per unique (package, version) tuple
across the whole scan — same package surfacing in multiple sources
collapses to one Finding with multiple Evidence rows.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/05-package-version-leaks.md
"""
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from .banners import scan_banners
from .fetcher import fetch_evidence
from .parsers.package_json import parse_package_json
from .parsers.requirements_txt import parse_requirements_txt


_FINDING_SOURCE = "package_leaks"


_PATH_PARSERS: dict[str, Callable[[str], list[dict[str, str]]]] = {
    "/package.json": parse_package_json,
    "/requirements.txt": parse_requirements_txt,
}


@register("1.5")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    bundle = fetch_evidence(target.base_url)
    responses = bundle["responses"]
    if not responses:
        return

    hits = _collect_hits(responses)
    if not hits:
        return

    evidences, findings = _build_rows(
        hits=hits, scan_run=scan_run, target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        Finding.objects.bulk_create(findings)


def _collect_hits(
    responses: dict[str, dict],
) -> list[tuple[str, dict[str, str]]]:
    """Return [(probe_path, hit), ...] across all responses.

    Each `hit` dict comes from a parser or the banner scanner and has
    {package, version, source_kind}. Same (package, version) pair from
    two probes appears twice — dedup is the runner's job."""
    out: list[tuple[str, dict[str, str]]] = []
    for path, response in responses.items():
        body = response["body"]
        parser = _PATH_PARSERS.get(path)
        if parser is not None:
            for hit in parser(body):
                out.append((path, hit))
        for hit in scan_banners(body):
            out.append((path, hit))
    return out


def _build_rows(
    hits: list[tuple[str, dict[str, str]]],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    for path, hit in hits:
        key = (hit["package"], hit["version"])
        if key in seen:
            continue
        seen.add(key)

        url = urljoin(target.base_url, path)
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.PATH,
            url=url,
            method="GET",
            field=hit["source_kind"],
            matched_value=f"{hit['package']}=={hit['version']}",
            raw_excerpt=f"{hit['source_kind']}: {hit['package']} {hit['version']}"[:200],
            data={
                "package": hit["package"],
                "version": hit["version"],
                "source_kind": hit["source_kind"],
                "probe_path": path,
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"{hit['package']} {hit['version']} disclosed via {hit['source_kind']}",
                category=hit["source_kind"],
                severity=Severity.INFO,
                confidence="high",
                status=FindingStatus.CANDIDATE,
                data={
                    "package": hit["package"],
                    "version": hit["version"],
                    "source_kind": hit["source_kind"],
                    "probe_path": path,
                    "evidence_ids": [str(evidence.id)],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings
