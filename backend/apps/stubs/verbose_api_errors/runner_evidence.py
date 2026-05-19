"""Evidence persistence for stub 1.17 runner. One Evidence row per
probe (baseline + nonexistent_api_sibling). Mirrors 1.16's shape."""
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
    content_hash = (
        body_hash_bytes(snapshot.body.encode("utf-8"))
        if snapshot.body else ""
    )
    excerpt = (
        f"{probe_kind}: {snapshot.final_url} (status {snapshot.status})"
    )
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
