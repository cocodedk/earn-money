"""Post-scan analyzers.

`detect_edge_blocking` runs at scan-run completion. When a CDN/WAF
fingerprint shows up in the run's Findings *and* the Evidence rows
are mostly 4xx responses, we emit an `EDGE_BLOCKING_DETECTED` event
so the dashboard can show a clear "origin not reached" banner
instead of just "0 findings".

This catches the common pattern where Cloudflare (or Akamai, Fastly,
etc.) returns 403/406 to UA-less probes at the edge, so the rest of
the stub suite has nothing to fingerprint. Without this signal the
operator can't distinguish "scan worked, target is hardened" from
"scanner is broken".
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from apps.stubs.server_headers.signatures import SIGNATURES

if TYPE_CHECKING:
    from apps.scans.models import ScanRun


# Canonical CDN/WAF technology names, sourced from the same signature
# library stub 1.2 (server_headers) uses to identify them. Reading
# from `SIGNATURES` rather than hard-coding the list prevents drift:
# any new CDN added to the stub's signatures automatically becomes a
# known edge here.
_CDN_TECHNOLOGIES: frozenset[str] = frozenset(
    sig["technology"].lower()
    for sig in SIGNATURES
    if sig.get("technology_category") == "cdn"
)

# A scan whose Evidence is mostly 4xx is almost certainly being
# blocked at an edge somewhere. Threshold deliberately high (80%) to
# avoid flagging normal scans whose well_known_paths probes return a
# 404 mix. The same precondition now applies to BOTH identified-edge
# and unknown_waf branches (codex P2.2): merely fingerprinting a CDN
# isn't enough — there must be blocked-response evidence too.
_BLOCKING_THRESHOLD = 0.8
_BLOCKING_MIN_EVIDENCE = 5


def _match_edge(value: str) -> str | None:
    """Return the canonical edge name if ``value`` is a known
    CDN/WAF technology, else None. Case-insensitive."""
    lo = value.lower()
    return lo if lo in _CDN_TECHNOLOGIES else None


def _has_blocking_evidence(blocked: int, total: int) -> bool:
    """True if the evidence rows pass the blocked-response threshold
    that distinguishes "edge actively blocking" from "edge present
    but transparent". Used by both branches in
    `detect_edge_blocking` so a Cloudflare-fronted site that returns
    200s doesn't trip the EDGE_BLOCKING_DETECTED banner."""
    if total < _BLOCKING_MIN_EVIDENCE:
        return False
    return blocked / total >= _BLOCKING_THRESHOLD


def detect_edge_blocking(scan_run: "ScanRun") -> dict | None:
    """Return a summary dict if the scan-run was edge-blocked, else None.

    Decision shape:
        - At least `_BLOCKING_MIN_EVIDENCE` evidence rows AND
          `_BLOCKING_THRESHOLD` of them are 4xx — required precondition.
        - Edge name: the first CDN/WAF technology that appears in a
          Finding's `technology` field, else `unknown_waf` when the
          ratio is met without an identifying Finding.

    Result shape:
        {
            "edge": "cloudflare" | "aws_cloudfront" | "unknown_waf" | ...,
            "blocked_count": int,   # 4xx Evidence rows
            "total_evidence": int,  # all Evidence rows for this run
        }
    """
    from django.db.models import Count, Q

    from apps.evidence.models import Evidence
    from apps.findings.models import Finding

    edge: str | None = None
    for f in Finding.objects.filter(scan_run=scan_run).only("data"):
        data = f.data or {}
        edge = _match_edge(str(data.get("technology", "")))
        if edge:
            break

    # One round-trip: total + 4xx-only count in a single aggregate.
    counts = Evidence.objects.filter(scan_run=scan_run).aggregate(
        total=Count("id"),
        blocked=Count("id", filter=Q(
            data__status__gte=400, data__status__lt=500,
        )),
    )
    total = counts["total"]
    blocked = counts["blocked"]

    if not _has_blocking_evidence(blocked, total):
        return None
    if edge is None:
        edge = "unknown_waf"

    return {
        "edge": edge,
        "blocked_count": blocked,
        "total_evidence": total,
    }
