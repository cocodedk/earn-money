"""Finding persistence for stub 1.17 — VerboseApiErrorFinding shape.

Finding.data carries the spec's persisted hint arrays
(matched_indicators, disclosure_types, database_hints,
file_path_hints, framework_hints). `detect_all_indicators`
populates them faithfully (full coverage, not first-match-per-kind).

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

from apps.findings.models import Finding, Severity
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .classifier import Verdict
from .fetcher import ResponseSnapshot
from .indicators import ApiErrorIndicator


_STUB_SLUG = "1.17"
_CATEGORY = "verbose_api_errors"


def emit_finding(
    scan_run: ScanRun, target: ScanTarget,
    *, snapshot: ResponseSnapshot, indicators: list[ApiErrorIndicator],
    all_indicators: list[ApiErrorIndicator], verdict: Verdict,
    evidence_id: str, probe_kind: str,
) -> Finding:
    finding = Finding(
        scan_run=scan_run, target=target, stub_slug=_STUB_SLUG,
        title=(
            f"Verbose API error: {probe_kind} on "
            f"{snapshot.final_url[:140]}"
        ),
        category=_CATEGORY,
        severity=(Severity.LOW if verdict.confidence == "high" else Severity.INFO),
        confidence=verdict.confidence, status=verdict.status,
        data=_build_data(
            snapshot, indicators, all_indicators, evidence_id, probe_kind,
        ),
    )
    finding.save()
    return finding


def _build_data(
    snapshot: ResponseSnapshot, indicators: list[ApiErrorIndicator],
    all_indicators: list[ApiErrorIndicator],
    evidence_id: str, probe_kind: str,
) -> dict[str, object]:
    disclosure_types = sorted({ind.kind for ind in indicators})
    file_path_hints = _dedupe(
        i.matched_value for i in all_indicators if i.kind == "source_path"
    )
    database_hints = _dedupe(
        i.matched_value for i in all_indicators if i.kind == "database_error"
    )
    matched_indicators = _dedupe(i.matched_value for i in all_indicators)
    return {
        "url": snapshot.final_url,
        "method": "GET",
        "probe_kind": probe_kind,
        "status_code": snapshot.status,
        "content_type": snapshot.content_type,
        "disclosure_types": disclosure_types,
        "matched_indicators": matched_indicators,
        "file_path_hints": file_path_hints,
        "database_hints": database_hints,
        "framework_hints": [],
        "ai_assistance": "none",
        "evidence_ids": [evidence_id],
    }


def _dedupe(items) -> list[str]:
    return list(dict.fromkeys(items))
