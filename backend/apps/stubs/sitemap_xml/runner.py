"""Stub 1.12 runner — registered against stub_slug "1.12".

Per-seed pass:
1. fetch_sitemap each path in SEEDS until one succeeds with a
   parseable sitemap.
2. parse the body, classify the response.
3. aggregate extracted URLs: scope each + tag each.
4. persist one Evidence + one Finding pair.

MVP deferred (tracked):
- Nested sitemap fetching (sitemap index → child sitemaps).
- Per-URL SitemapXmlSignature rows (current MVP rolls into
  Finding.data lists/counts).
- max_sitemap_urls cap enforcement.
- Plain text + gzipped sitemap formats.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/12-sitemap-xml.md
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import urljoin

from django.db import transaction

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from .classify import FetchOutcome, Verdict, classify_response
from .fetcher import fetch_sitemap
from .parser import ParsedSitemap, parse_sitemap_xml
from .signals import classify_url_scope, tag_url


_FINDING_SOURCE = "sitemap_xml"
_RAW_EXCERPT_CAP = 200
_SAMPLE_URLS_CAP = 10

# Spec §Inputs Seed paths. Tried in declaration order; first
# success short-circuits the loop.
_SEEDS: tuple[str, ...] = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
)


@register("1.12")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    outcome, parsed, verdict = _probe_seeds(target.base_url)
    aggregate = _aggregate(parsed, target.base_url) if parsed else _empty_aggregate()

    with transaction.atomic():
        evidence = _build_evidence(
            scan_run=scan_run, target=target,
            outcome=outcome, verdict=verdict,
        )
        evidence.save()
        finding = _build_finding(
            scan_run=scan_run, target=target,
            outcome=outcome, verdict=verdict, aggregate=aggregate,
            evidence_id=str(evidence.id),
        )
        finding.save()


def _probe_seeds(
    base_url: str,
) -> tuple[FetchOutcome, ParsedSitemap | None, Verdict]:
    """Try seeds in order. Return the first one that classifies as
    a confirmed sitemap (urlset or sitemapindex). If none confirm,
    return the LAST outcome — typically a uniform 404/unreachable
    set so reporting any single seed gives the right shape."""
    last: tuple[FetchOutcome, ParsedSitemap | None, Verdict] | None = None
    for path in _SEEDS:
        url = urljoin(base_url + "/", path)
        outcome = fetch_sitemap(url)
        parsed = (
            parse_sitemap_xml(outcome.body)
            if outcome.kind == "ok"
            else None
        )
        verdict = classify_response(outcome, parsed=parsed)
        if verdict.finding_status == FindingStatus.CONFIRMED:
            return outcome, parsed, verdict
        last = (outcome, parsed, verdict)
    assert last is not None, "_SEEDS is non-empty"
    return last


def _empty_aggregate() -> dict:
    return {
        "extracted_url_count": 0,
        "in_scope_url_count": 0,
        "out_of_scope_url_count": 0,
        "tag_counts": {},
        "sample_urls": [],
    }


def _aggregate(parsed: ParsedSitemap, base_url: str) -> dict:
    tag_counter: Counter[str] = Counter()
    in_scope: list[str] = []
    out_of_scope = 0
    for entry in parsed.entries:
        scope = classify_url_scope(entry.loc, base_url)
        if scope == "in_scope":
            in_scope.append(entry.loc)
            tag_counter.update(tag_url(entry.loc))
        elif scope == "out_of_scope":
            out_of_scope += 1
    return {
        "extracted_url_count": len(parsed.entries),
        "in_scope_url_count": len(in_scope),
        "out_of_scope_url_count": out_of_scope,
        "tag_counts": dict(tag_counter),
        "sample_urls": in_scope[:_SAMPLE_URLS_CAP],
    }


def _build_evidence(
    *, scan_run: ScanRun, target: ScanTarget,
    outcome: FetchOutcome, verdict: Verdict,
) -> Evidence:
    excerpt = (
        f"{verdict.classification}: {outcome.final_url} "
        f"(status {outcome.status or 0})"
    )[:_RAW_EXCERPT_CAP]
    return Evidence(
        scan_run=scan_run,
        target=target,
        source=EvidenceSource.PATH,
        url=outcome.final_url,
        method="GET",
        field=verdict.classification,
        matched_value=verdict.classification,
        raw_excerpt=excerpt,
        data={
            "classification": verdict.classification,
            "status": outcome.status,
        },
    )


def _build_finding(
    *, scan_run: ScanRun, target: ScanTarget,
    outcome: FetchOutcome, verdict: Verdict, aggregate: dict,
    evidence_id: str,
) -> Finding:
    return Finding(
        scan_run=scan_run,
        target=target,
        stub_slug=scan_run.stub_slug,
        title=(
            f"Sitemap.xml {verdict.classification} "
            f"(status {outcome.status or 0})"
        ),
        category="sitemap_xml",
        severity=Severity.INFO,
        confidence=verdict.confidence,
        status=verdict.finding_status,
        data={
            "finding_type": "sitemap_xml",
            "classification": verdict.classification,
            "http_status": outcome.status,
            "sitemap_url": outcome.final_url,
            "indicators": verdict.indicators,
            "evidence_ids": [evidence_id],
            "source": _FINDING_SOURCE,
            **aggregate,
        },
    )
