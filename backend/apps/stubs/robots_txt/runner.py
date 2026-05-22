"""Stub 1.11 runner — registered against stub_slug "1.11".

Single robots.txt probe:
1. fetch_robots: GET {base_url}/robots.txt with manual same-origin
   redirect handling
2. parse the body (if any) into typed groups + sitemaps + warnings
3. classify the response into a Verdict per spec §Response
   classification
4. compute sensitive-path hints across all disallow/allow paths
5. categorise sitemaps as same-origin vs cross-origin
6. persist one Evidence + one Finding pair atomically

MVP deferred (tracked separately):
- RobotsTxtSignature rows per disallow/allow/sitemap (current MVP
  rolls everything into Finding.data lists/counts).
- cross-run idempotence + stale tracking (platform-wide, #82)
- max_extracted_paths / max_extracted_sitemaps enforcement
  (current MVP serializes everything the parser found)

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/11-robots-txt.md
"""
from __future__ import annotations

from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import guarded_runner
from .classify import FetchOutcome, Verdict, classify_response
from .fetcher import fetch_robots
from .parser import ParsedRobots, parse_robots
from .signals import classify_sitemap_origin, is_sensitive_path


_FINDING_SOURCE = "robots_txt"
_RAW_EXCERPT_CAP = 200


@guarded_runner("1.11")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    outcome = fetch_robots(target.base_url)
    parsed = (
        parse_robots(outcome.body) if outcome.kind == "ok" else None
    )
    verdict = classify_response(outcome)
    hints = _aggregate_hints(parsed, target.base_url) if parsed else _empty_hints()

    evidence, finding = _build_rows(
        scan_run=scan_run, target=target,
        outcome=outcome, verdict=verdict, hints=hints,
    )

    with transaction.atomic():
        evidence.save()
        finding.data["evidence_ids"] = [str(evidence.id)]
        finding.save()


def _empty_hints() -> dict:
    return {
        "disallowed_paths": [],
        "allowed_paths": [],
        "sitemaps": [],
        "cross_origin_sitemaps": [],
        "sensitive_hints": [],
        "parse_warnings": [],
    }


def _aggregate_hints(
    parsed: ParsedRobots, base_url: str,
) -> dict:
    disallowed: list[str] = []
    allowed: list[str] = []
    for group in parsed.groups:
        disallowed.extend(group.disallows)
        allowed.extend(group.allows)

    same_origin_sitemaps: list[str] = []
    cross_origin_sitemaps: list[str] = []
    for sitemap_url in parsed.sitemaps:
        bucket = (
            same_origin_sitemaps
            if classify_sitemap_origin(sitemap_url, base_url) == "same_origin"
            else cross_origin_sitemaps
        )
        bucket.append(sitemap_url)

    sensitive_hints: list[dict] = []
    for path in disallowed + allowed:
        tokens = is_sensitive_path(path)
        if tokens:
            sensitive_hints.append({"path": path, "tokens": list(tokens)})

    return {
        "disallowed_paths": disallowed,
        "allowed_paths": allowed,
        "sitemaps": same_origin_sitemaps,
        "cross_origin_sitemaps": cross_origin_sitemaps,
        "sensitive_hints": sensitive_hints,
        "parse_warnings": list(parsed.warnings),
    }


def _build_rows(
    *,
    scan_run: ScanRun,
    target: ScanTarget,
    outcome: FetchOutcome,
    verdict: Verdict,
    hints: dict,
) -> tuple[Evidence, Finding]:
    url = outcome.final_url or urljoin(target.base_url + "/", "/robots.txt")
    status = outcome.status if outcome.status is not None else 0
    excerpt = (
        f"{verdict.classification}: {url} (status {status})"
    )[:_RAW_EXCERPT_CAP]

    evidence = Evidence(
        scan_run=scan_run,
        target=target,
        source=EvidenceSource.PATH,
        url=url,
        method="GET",
        field=verdict.classification,
        matched_value=verdict.classification,
        raw_excerpt=excerpt,
        data={
            "classification": verdict.classification,
            "status": status,
            "redirected": outcome.redirected,
        },
    )
    finding = Finding(
        scan_run=scan_run,
        target=target,
        stub_slug=scan_run.stub_slug,
        title=(
            f"Robots.txt {verdict.classification} "
            f"(status {status})"
        ),
        category="robots_txt",
        severity=Severity.INFO,
        confidence=verdict.confidence,
        status=verdict.finding_status,
        data={
            "finding_type": "robots_txt",
            "classification": verdict.classification,
            "http_status": status,
            "redirected": outcome.redirected,
            "indicators": verdict.indicators,
            "disallowed_paths_count": len(hints["disallowed_paths"]),
            "allowed_paths_count": len(hints["allowed_paths"]),
            "sitemaps_count": len(hints["sitemaps"]) + len(hints["cross_origin_sitemaps"]),
            "sensitive_path_hints_count": len(hints["sensitive_hints"]),
            "same_origin_path_hints": hints["disallowed_paths"] + hints["allowed_paths"],
            "same_origin_sitemaps": hints["sitemaps"],
            "cross_origin_sitemaps": hints["cross_origin_sitemaps"],
            "sensitive_hints": hints["sensitive_hints"],
            "parse_warnings": hints["parse_warnings"],
            "source": _FINDING_SOURCE,
        },
    )
    return evidence, finding
