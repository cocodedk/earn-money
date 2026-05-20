"""Evidence persistence for `well_known_paths` runner.

One Evidence row per inspected response. Mirrors stub 1.19's pattern.

Spec sources: 1.20-1.25 §Persistence.
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
    *, requested_url: str, family: str, candidate_path: str,
    snapshot: ResponseSnapshot,
) -> Evidence:
    """`family` + `candidate_path` recorded in evidence.data so triage
    can see which family the probe was for."""
    excerpt = (
        f"{family}: {candidate_path} → {snapshot.final_url} "
        f"(status {snapshot.status})"
    )
    content_hash = body_hash_bytes(snapshot.body) if snapshot.body else ""
    ev = Evidence(
        scan_run=scan_run, target=target,
        source=EvidenceSource.HTML,
        url=snapshot.final_url, method="GET",
        field=family, matched_value=snapshot.content_type or "",
        raw_excerpt=excerpt[:_RAW_EXCERPT_CAP],
        content_hash=content_hash,
        data={
            "status": snapshot.status,
            "content_type": snapshot.content_type,
            "requested_url": requested_url,
            "family": family,
            "candidate_path": candidate_path,
            "head_supported": snapshot.head_supported,
        },
    )
    ev.save()
    return ev
