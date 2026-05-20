"""Stub 1.6 runner — registered against stub_slug "1.6".

Soft-404 detection: build a body-hash set from the two nonce probes,
then suppress any common-path probe whose body matches. The hash set
reliably catches SPA fallthrough (every unknown path returns the same
shell) without false positives on genuinely-distinct response bodies.

Metadata extraction: robots.txt Disallow paths and sitemap.xml <loc>
URLs surface as Findings without follow-up fetches — the operator
makes the active-probe call in a later phase. MVP records them as
"disclosed routes" with source_kind on the Finding.

Cross-source dedup: same path emerging from a probe AND from
robots/sitemap collapses to one Finding (taxonomy choice favours the
probe source — operator knows the path was actually reachable).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/06-hidden-routes.md
"""
from __future__ import annotations

from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.findings.bulk import bulk_create_findings
from apps.programs.exceptions import OutOfScope
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.http import resolve_and_guard
from apps.targets.models import ScanTarget

from .._shared.hashing import body_hash

from ..runners import register
from .extractors.robots_txt import parse_robots_txt
from .extractors.sitemap_xml import parse_sitemap_xml
from .fetcher import COMMON_PATHS, fetch_evidence


_FINDING_SOURCE = "hidden_routes"
_NONCE_MARKER = "scanner_nonexistent"
_ROBOTS_PATH = "/robots.txt"
_SITEMAP_PATH = "/sitemap.xml"


@register("1.6")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    try:
        resolve_and_guard(scan_run, target, stub_id="1.6")
    except OutOfScope:
        return  # event already emitted; halt this stub
    bundle = fetch_evidence(target.base_url)
    if bundle["baseline"] is None:
        return

    probes = bundle["probes"]
    soft_404 = _soft_404_profile(probes)

    candidates: dict[str, str] = {}  # path → source_kind
    _add_probe_candidates(probes, soft_404, candidates)
    _add_metadata_candidates(probes, target.base_url, candidates)

    if not candidates:
        return

    evidences, findings = _build_rows(
        candidates=candidates, scan_run=scan_run, target=target,
    )

    with transaction.atomic():
        Evidence.objects.bulk_create(evidences)
        bulk_create_findings(findings)


def _soft_404_profile(probes: dict[str, dict]) -> set[str]:
    """Return body hashes from the two nonce probes — any other probe
    whose body hash matches one of these is filtered as a soft 404."""
    return {
        body_hash(probe["body"])
        for path, probe in probes.items()
        if _NONCE_MARKER in path
    }


def _add_probe_candidates(
    probes: dict[str, dict],
    soft_404: set[str],
    candidates: dict[str, str],
) -> None:
    for path in COMMON_PATHS:
        probe = probes.get(path)
        if probe is None:
            continue
        if probe["status"] == 404:
            continue
        if body_hash(probe["body"]) in soft_404:
            continue
        candidates.setdefault(path, "common_path")


def _add_metadata_candidates(
    probes: dict[str, dict],
    base_url: str,
    candidates: dict[str, str],
) -> None:
    """`Disallow: /` (deny-all) is a legitimate robots directive but
    "/" is the baseline, not a hidden route — filter it out.
    Similarly empty paths."""
    robots = probes.get(_ROBOTS_PATH)
    if robots is not None and robots["status"] == 200:
        for path in parse_robots_txt(robots["body"]):
            if _is_meaningful_path(path):
                candidates.setdefault(path, "robots.txt")

    sitemap = probes.get(_SITEMAP_PATH)
    if sitemap is not None and sitemap["status"] == 200:
        for path in parse_sitemap_xml(sitemap["body"], base_url):
            if _is_meaningful_path(path):
                candidates.setdefault(path, "sitemap.xml")


def _is_meaningful_path(path: str) -> bool:
    return path not in {"", "/"}


def _build_rows(
    candidates: dict[str, str],
    scan_run: ScanRun,
    target: ScanTarget,
) -> tuple[list[Evidence], list[Finding]]:
    evidences: list[Evidence] = []
    findings: list[Finding] = []

    for path, source_kind in candidates.items():
        url = urljoin(target.base_url, path)
        evidence = Evidence(
            scan_run=scan_run,
            target=target,
            source=EvidenceSource.PATH,
            url=url,
            method="GET",
            field=source_kind,
            matched_value=path,
            raw_excerpt=f"{source_kind}: {path}"[:200],
            data={
                "path": path,
                "source_kind": source_kind,
            },
        )
        evidences.append(evidence)
        findings.append(
            Finding(
                scan_run=scan_run,
                target=target,
                stub_slug=scan_run.stub_slug,
                title=f"Hidden route candidate: {path} (via {source_kind})",
                category=source_kind,
                severity=Severity.INFO,
                confidence=_confidence_for(source_kind),
                status=FindingStatus.CANDIDATE,
                data={
                    "path": path,
                    "source_kind": source_kind,
                    "evidence_ids": [str(evidence.id)],
                    "source": _FINDING_SOURCE,
                },
            )
        )

    return evidences, findings


def _confidence_for(source_kind: str) -> str:
    """Common-path probes that returned non-soft-404 bodies are high-
    confidence (we got actual content). Metadata files are medium —
    they disclose the path's existence but we haven't fetched it."""
    if source_kind == "common_path":
        return "high"
    return "medium"
