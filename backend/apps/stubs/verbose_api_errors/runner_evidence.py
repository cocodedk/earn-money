"""Evidence persistence for stub 1.17 runner.

One Evidence row per probe (baseline + nonexistent_api_sibling).

FU-1 changes (vs initial slice 2):
* `raw_excerpt` is now a redacted body slice (≤ 4096 bytes) instead
  of a synthetic descriptor. Tokens, JWTs, API keys, basic-auth URL
  credentials, and emails are scrubbed via `redaction.redact`
  before persistence (spec §Safety + §config redact_secrets=true).
* `data.selected_headers` carries a tight allowlist of informative
  fingerprinting headers (Server, X-Powered-By, X-Runtime, X-AspNet-
  Version, X-AspNetMvc-Version, X-Generator, Via). Sensitive headers
  (Set-Cookie, Authorization, *-Key, *-Token, *-Secret) are NEVER
  persisted regardless of upstream content.
* `data.truncation` is True when the response body exceeded the
  fetcher cap OR the excerpt cap; downstream consumers know the
  excerpt is partial.
"""
from __future__ import annotations

from apps.evidence.models import Evidence, EvidenceSource
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .._shared.hashing import body_hash_bytes
from .fetcher import ResponseSnapshot
from .redaction import redact


_MAX_EXCERPT_BYTES = 4_096  # spec §config max_evidence_excerpt_bytes

_HEADER_ALLOWLIST: frozenset[str] = frozenset({
    "server",
    "x-powered-by",
    "x-runtime",
    "x-aspnet-version",
    "x-aspnetmvc-version",
    "x-generator",
    "via",
})


def save_response_evidence(
    scan_run: ScanRun, target: ScanTarget,
    *, requested_url: str, probe_kind: str,
    snapshot: ResponseSnapshot,
) -> Evidence:
    content_hash = (
        body_hash_bytes(snapshot.body.encode("utf-8"))
        if snapshot.body else ""
    )
    excerpt = redact(snapshot.body[:_MAX_EXCERPT_BYTES])
    truncation = snapshot.body_truncated or len(snapshot.body) > _MAX_EXCERPT_BYTES
    selected_headers = {
        name: value for name, value in snapshot.headers.items()
        if name in _HEADER_ALLOWLIST
    }
    ev = Evidence(
        scan_run=scan_run, target=target,
        source=EvidenceSource.HTML,
        url=snapshot.final_url, method="GET",
        field=probe_kind, matched_value=snapshot.content_type or "",
        raw_excerpt=excerpt,
        content_hash=content_hash,
        data={
            "status": snapshot.status,
            "content_type": snapshot.content_type,
            "requested_url": requested_url,
            "probe_kind": probe_kind,
            "selected_headers": selected_headers,
            "truncation": truncation,
        },
    )
    ev.save()
    return ev
