"""Stub 1.13 runner — registered against stub_slug "1.13".

Per-scan pass:
1. fetch_security_txt at /.well-known/security.txt (canonical).
2. fetch_security_txt at /security.txt (legacy) — always, so
   conflicting_files / legacy_only verdicts can fire.
3. parse whichever body is "ok"; prefer canonical when both are.
4. classify per spec §Finding rules.
5. persist Evidence rows (one per fetched URL) + one Finding.

MVP deferred (tracked):
- check_legacy_path config flag (MVP always probes both, ~2 GETs).
- max_redirects override via config (defaults to spec's 3).
- prefer_https switching.
- Multiple Findings per scan (MVP emits the worst-applicable
  verdict only; secondary conditions land in `indicators`).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/13-security-txt.md
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.db import transaction
from django.utils import timezone as django_timezone

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget

from ..runners import register
from .classify import FetchOutcome, Verdict, classify_security_txt
from .fetcher import fetch_security_txt
from .parser import ParsedSecurityTxt, parse_security_txt


_FINDING_SOURCE = "security_txt"
_RAW_EXCERPT_CAP = 200
_CANONICAL_PATH = "/.well-known/security.txt"
_LEGACY_PATH = "/security.txt"


@register("1.13")
def run(scan_run: ScanRun, target_run: ScanTargetRun) -> None:
    target = target_run.target
    canonical = fetch_security_txt(target.base_url, _CANONICAL_PATH)
    legacy = fetch_security_txt(target.base_url, _LEGACY_PATH)

    parsed = _pick_parsed(canonical, legacy)
    verdict = classify_security_txt(
        canonical=canonical, legacy=legacy,
        parsed=parsed, now=_now_utc(),
    )

    with transaction.atomic():
        evidence_ids: list[str] = []
        for outcome in (canonical, legacy):
            ev = _build_evidence(
                scan_run=scan_run, target=target,
                outcome=outcome, verdict=verdict,
            )
            ev.save()
            evidence_ids.append(str(ev.id))

        finding = _build_finding(
            scan_run=scan_run, target=target,
            canonical=canonical, legacy=legacy,
            verdict=verdict, parsed=parsed,
            evidence_ids=evidence_ids,
        )
        finding.save()


def _pick_parsed(
    canonical: FetchOutcome, legacy: FetchOutcome,
) -> ParsedSecurityTxt | None:
    """Parse the body the classifier will treat as primary: canonical
    when present, legacy as fallback. None when neither was `ok`."""
    if canonical.kind == "ok":
        return parse_security_txt(canonical.body)
    if legacy.kind == "ok":
        return parse_security_txt(legacy.body)
    return None


def _now_utc() -> datetime:
    """Inject the current UTC time. Wrapped so tests can monkeypatch
    if a deterministic clock is needed; production uses
    django.utils.timezone."""
    return django_timezone.now().astimezone(timezone.utc)


def _build_evidence(
    *, scan_run: ScanRun, target: ScanTarget,
    outcome: FetchOutcome, verdict: Verdict,
) -> Evidence:
    excerpt = (
        f"{outcome.kind}: {outcome.final_url} "
        f"(status {outcome.status or 0})"
    )[:_RAW_EXCERPT_CAP]
    # `field` carries the verdict's finding_type so cross-stub
    # evidence indexes against a stable classification vocabulary
    # (matches stubs 1.11/1.12 convention). The per-probe outcome
    # kind lives in `data.kind` for audit.
    return Evidence(
        scan_run=scan_run,
        target=target,
        source=EvidenceSource.PATH,
        url=outcome.final_url,
        method="GET",
        field=verdict.finding_type,
        matched_value=verdict.finding_type,
        raw_excerpt=excerpt,
        data={
            "kind": outcome.kind,
            "status": outcome.status,
            "verdict_finding_type": verdict.finding_type,
        },
    )


def _build_finding(
    *, scan_run: ScanRun, target: ScanTarget,
    canonical: FetchOutcome, legacy: FetchOutcome,
    verdict: Verdict, parsed: ParsedSecurityTxt | None,
    evidence_ids: list[str],
) -> Finding:
    primary = canonical if canonical.kind == "ok" else legacy
    return Finding(
        scan_run=scan_run,
        target=target,
        stub_slug=scan_run.stub_slug,
        title=f"security.txt: {verdict.finding_type}",
        category="security_txt",
        severity=Severity.INFO,
        confidence=verdict.confidence,
        status=verdict.finding_status,
        data={
            "finding_type": verdict.finding_type,
            "http_status": primary.status,
            "primary_url": primary.final_url,
            "canonical_kind": canonical.kind,
            "legacy_kind": legacy.kind,
            "indicators": verdict.indicators,
            "evidence_ids": evidence_ids,
            "fields": _serialise_fields(parsed),
            "source": _FINDING_SOURCE,
        },
    )


def _serialise_fields(parsed: ParsedSecurityTxt | None) -> dict:
    if parsed is None:
        return {}
    return {
        "contact": list(parsed.contact),
        "expires": list(parsed.expires),
        "encryption": list(parsed.encryption),
        "acknowledgments": list(parsed.acknowledgments),
        "preferred_languages": list(parsed.preferred_languages),
        "canonical": list(parsed.canonical),
        "policy": list(parsed.policy),
        "hiring": list(parsed.hiring),
        "csaf": list(parsed.csaf),
        "unknown_fields": [list(p) for p in parsed.unknown_fields],
        "parse_errors": list(parsed.parse_errors),
    }
