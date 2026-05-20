"""Stub 1.5 runner — registered against stub_slug "1.5".

Why parser + banner side-by-side: a misconfigured server or a CDN
that returns a JS bundle at /package.json would slip past a parser-
only pipeline. Running scan_banners on every probe body — even paths
that have a dedicated parser — surfaces those disclosures too.

Why dedup across sources: a polyglot repo legitimately leaks the same
(package, version) tuple from /package.json AND /requirements.txt
(rare but real). Both Evidence rows go into the bundle so the operator
sees every channel; they're aggregated under one Finding so the
triage queue isn't padded with logical duplicates.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/05-package-version-leaks.md
"""
from __future__ import annotations

from typing import Callable
from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.findings.bulk import bulk_create_findings
from apps.programs.exceptions import OutOfScope
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.http import resolve_and_guard
from apps.targets.models import ScanTarget

from ..runners import register
from .banners import scan_banners
from .fetcher import fetch_evidence
from .parsers.package_json import parse_package_json
from .parsers.requirements_txt import parse_requirements_txt


_FINDING_SOURCE = "package_leaks"
_BANNER_SOURCE_KIND = "banner"


_PATH_PARSERS: dict[str, Callable[[str], list[dict[str, str]]]] = {
    "/package.json": parse_package_json,
    "/requirements.txt": parse_requirements_txt,
}


@register("1.5")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    try:
        resolve_and_guard(scan_run, target, stub_id="1.5")
    except OutOfScope:
        return  # event already emitted; halt this stub
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
        bulk_create_findings(findings)


def _collect_hits(
    responses: dict[str, dict],
) -> list[tuple[str, dict[str, str]]]:
    """Return [(probe_path, hit), ...] across all responses. Each hit
    dict comes from a parser or scan_banners and has
    {package, version, source_kind}."""
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

    by_key: dict[tuple[str, str], list[tuple[str, dict[str, str]]]] = {}
    for path, hit in hits:
        key = (hit["package"], hit["version"])
        by_key.setdefault(key, []).append((path, hit))

    for (package, version), hit_list in by_key.items():
        pkg_evidences = [
            _build_evidence(path, hit, scan_run, target)
            for path, hit in hit_list
        ]
        evidences.extend(pkg_evidences)
        primary_path, primary_hit = hit_list[0]
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"{package} {version} disclosed via {primary_hit['source_kind']}",
                category=primary_hit["source_kind"],
                severity=Severity.INFO,
                confidence=_confidence_for(primary_hit),
                status=FindingStatus.CANDIDATE,
                data={
                    "package": package,
                    "version": version,
                    "source_kind": primary_hit["source_kind"],
                    "probe_path": primary_path,
                    "evidence_ids": [str(ev.id) for ev in pkg_evidences],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings


def _build_evidence(
    path: str, hit: dict[str, str],
    scan_run: ScanRun, target: ScanTarget,
) -> Evidence:
    url = urljoin(target.base_url, path)
    return Evidence(
        scan_run=scan_run,
        target=target,
        source=_evidence_source_for(hit),
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


def _evidence_source_for(hit: dict[str, str]) -> str:
    """Banner matches live inside a JS body — those are SCRIPT evidence.
    Manifest matches (package.json etc.) are PATH evidence — operator
    triage filters can split them cleanly."""
    if hit["source_kind"] == _BANNER_SOURCE_KIND:
        return EvidenceSource.SCRIPT
    return EvidenceSource.PATH


def _confidence_for(hit: dict[str, str]) -> str:
    """Manifest disclosure is unambiguous (high). A banner in a JS bundle
    could be a vendored copy of the package rather than the app's actual
    declared dep — medium, not high."""
    if hit["source_kind"] == _BANNER_SOURCE_KIND:
        return "medium"
    return "high"
