"""Finding persistence for `well_known_paths` runner.

One Finding row per (response, family, signature-hit) — `Finding.category`
is `well_known_paths.<family>` per spec §Persistence to preserve
per-family taxonomy.

Spec sources: 1.20-1.25 §Persistence.
"""
from __future__ import annotations

from apps.findings.models import Finding
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .classify import Verdict
from .fetcher import ResponseSnapshot
from .redact import redact


_STUB_SLUG = "1.20"  # owner ID; absorbs 1.21-1.25 via spec closure
_CATEGORY_PREFIX = "well_known_paths"


def emit_finding(
    scan_run: ScanRun, target: ScanTarget,
    *, snapshot: ResponseSnapshot, verdict: Verdict,
    evidence_ids: list[str], requested_url: str,
    candidate_path: str,
) -> Finding:
    redacted_excerpt = redact(family=verdict.family, body=snapshot.body)
    finding = Finding(
        scan_run=scan_run, target=target, stub_slug=_STUB_SLUG,
        title=(
            f"Exposed {verdict.family}: {candidate_path} on "
            f"{snapshot.final_url[:160]}"
        ),
        category=f"{_CATEGORY_PREFIX}.{verdict.family}",
        severity=verdict.severity,
        confidence=verdict.confidence,
        status="candidate",
        data={
            "requested_url": requested_url,
            "final_url": snapshot.final_url,
            "method": "GET",
            "status_code": snapshot.status,
            "content_type": snapshot.content_type,
            "family": verdict.family,
            "candidate_path": candidate_path,
            "signature_id": verdict.signature_id,
            "matched_text": verdict.matched_text,
            "redacted_excerpt": redacted_excerpt,
            "evidence_ids": evidence_ids,
        },
    )
    finding.save()
    return finding
