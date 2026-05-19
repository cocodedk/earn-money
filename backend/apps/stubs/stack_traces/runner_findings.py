"""Finding persistence for stub 1.16 — StackTraceFinding shape per
spec §"Persistence".

One Finding row per (response, strongest StackTraceMatch) pair.
The classifier returns None when there's nothing to persist; the
runner skips emission in that case.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/16-stack-traces.md
"""
from __future__ import annotations

from apps.findings.models import Finding, Severity
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .classifier import Verdict
from .fetcher import ResponseSnapshot
from .matcher import StackTraceMatch


_STUB_SLUG = "1.16"
_CATEGORY = "stack_traces"
# Generic fallbacks emit info; everything else (concrete framework
# stack, language-specific runtime) emits low because the spec ties
# severity_source=deterministic to the evidence carrying a real
# language/framework leak.
_GENERIC_FAMILIES = frozenset({"generic_stack_trace", "path_line_leak"})


def emit_finding(
    scan_run: ScanRun, target: ScanTarget,
    *, snapshot: ResponseSnapshot, match: StackTraceMatch,
    verdict: Verdict, evidence_ids: list[str], requested_url: str,
) -> Finding:
    severity = (
        Severity.INFO if match.family in _GENERIC_FAMILIES else Severity.LOW
    )
    finding = Finding(
        scan_run=scan_run, target=target, stub_slug=_STUB_SLUG,
        title=f"Stack trace: {match.family} on {snapshot.final_url[:160]}",
        category=_CATEGORY, severity=severity,
        confidence=verdict.confidence, status=verdict.status,
        data=_build_data(snapshot, match, evidence_ids, requested_url),
    )
    finding.save()
    return finding


def _build_data(
    snapshot: ResponseSnapshot, match: StackTraceMatch,
    evidence_ids: list[str], requested_url: str,
) -> dict[str, object]:
    return {
        "requested_url": requested_url,
        "final_url": snapshot.final_url,
        "method": "GET",
        "status_code": snapshot.status,
        "content_type": snapshot.content_type,
        "signature_family": match.family,
        "language_hint": match.language,
        "framework_hint": match.framework,
        "exception_type": match.exception_type,
        "top_frame": match.top_frame,
        "stack_frame_count": match.stack_frame_count,
        "evidence_ids": evidence_ids,
    }
