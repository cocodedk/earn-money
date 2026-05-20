"""Evidence persistence for stub 1.19 runner.

One Evidence row per inspected response. Mirrors stub 1.16 + 1.17.
Body is hashed for dedup keying.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from apps.evidence.models import Evidence, EvidenceSource
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .._shared.hashing import body_hash_bytes
from .fetcher import ResponseSnapshot


_RAW_EXCERPT_CAP = 200


def save_response_evidence(
    scan_run: ScanRun, target: ScanTarget,
    *, requested_url: str, probe_kind: str,
    snapshot: ResponseSnapshot,
) -> Evidence:
    """``probe_kind`` is `baseline` or `error_probe` — recorded in
    evidence.data so triage can distinguish the canonical fetch from
    the deliberate malformed-query probe."""
    excerpt = (
        f"{probe_kind}: {snapshot.final_url} (status {snapshot.status})"
    )
    content_hash = body_hash_bytes(snapshot.body) if snapshot.body else ""
    ev = Evidence(
        scan_run=scan_run, target=target,
        source=EvidenceSource.HTML,
        url=snapshot.final_url, method="GET",
        field=probe_kind, matched_value=snapshot.content_type or "",
        raw_excerpt=excerpt[:_RAW_EXCERPT_CAP],
        content_hash=content_hash,
        data={
            "status": snapshot.status,
            "content_type": snapshot.content_type,
            "requested_url": requested_url,
            "probe_kind": probe_kind,
        },
    )
    ev.save()
    return ev
