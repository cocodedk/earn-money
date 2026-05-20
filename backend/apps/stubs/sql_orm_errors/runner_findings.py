"""Finding persistence for stub 1.19 — `SqlOrmErrorFinding` shape per
spec §Persistence.

One Finding row per (response, strongest signature) pair. The
classifier returns None when there's nothing to persist; the runner
skips emission in that case.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from apps.findings.models import Finding, Severity
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .classify import Verdict
from .fetcher import ResponseSnapshot
from .redact import redact


_STUB_SLUG = "1.19"
_CATEGORY_PREFIX = "sql_orm_errors"

_SEVERITY_MAP = {
    "info": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
}


def emit_finding(
    scan_run: ScanRun, target: ScanTarget,
    *, snapshot: ResponseSnapshot, verdict: Verdict,
    evidence_ids: list[str], requested_url: str,
) -> Finding:
    redacted_excerpt = redact(verdict.error_excerpt)
    finding = Finding(
        scan_run=scan_run, target=target, stub_slug=_STUB_SLUG,
        title=(
            f"SQL/ORM error disclosure: {verdict.signature_family} "
            f"on {snapshot.final_url[:160]}"
        ),
        category=f"{_CATEGORY_PREFIX}.{verdict.signature_family}",
        severity=_SEVERITY_MAP[verdict.severity],
        confidence=verdict.confidence,
        status="candidate",
        data={
            "requested_url": requested_url,
            "final_url": snapshot.final_url,
            "method": "GET",
            "status_code": snapshot.status,
            "content_type": snapshot.content_type,
            "signature_id": verdict.signature_id,
            "signature_family": verdict.signature_family,
            "error_excerpt_redacted": redacted_excerpt,
            "evidence_ids": evidence_ids,
        },
    )
    finding.save()
    return finding
