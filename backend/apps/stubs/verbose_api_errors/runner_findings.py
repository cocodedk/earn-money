"""Finding persistence for stub 1.17 — VerboseApiErrorFinding shape.

Finding.data carries the spec's persisted hint arrays
(matched_indicators, disclosure_types, database_hints,
file_path_hints, framework_hints). Each hint list is bounded by
`_MAX_HINTS` so a debug page with hundreds of matches can't bloat
the JSON column.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

from typing import Iterable

from apps.findings.models import Finding, Severity
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .classifier import Verdict
from .fetcher import ResponseSnapshot
from .indicators import ApiErrorIndicator


_STUB_SLUG = "1.17"
_CATEGORY = "verbose_api_errors"
_MAX_HINTS = 50  # bounds each persisted hint array


def emit_finding(
    scan_run: ScanRun, target: ScanTarget,
    *, snapshot: ResponseSnapshot, indicators: list[ApiErrorIndicator],
    verdict: Verdict, evidence_id: str, probe_kind: str,
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
        data=_build_data(snapshot, indicators, evidence_id, probe_kind),
    )
    finding.save()
    return finding


def _build_data(
    snapshot: ResponseSnapshot, indicators: list[ApiErrorIndicator],
    evidence_id: str, probe_kind: str,
) -> dict[str, object]:
    return {
        "url": snapshot.final_url,
        "method": "GET",
        "probe_kind": probe_kind,
        "status_code": snapshot.status,
        "content_type": snapshot.content_type,
        "disclosure_types": sorted({ind.kind for ind in indicators}),
        "matched_indicators": _dedupe_capped(
            i.matched_value for i in indicators
        ),
        "file_path_hints": _dedupe_capped(
            i.matched_value for i in indicators if i.kind == "source_path"
        ),
        "database_hints": _dedupe_capped(
            i.matched_value for i in indicators if i.kind == "database_error"
        ),
        "framework_hints": [],
        "ai_assistance": "none",
        "evidence_ids": [evidence_id],
    }


def _dedupe_capped(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))[:_MAX_HINTS]
