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
# blocked at an edge somewhere — even when no Finding identifies the
# vendor. Threshold deliberately high (80%) to avoid flagging
# normal scans whose well_known_paths probes return a 404 mix.
_UNKNOWN_WAF_THRESHOLD = 0.8
_UNKNOWN_WAF_MIN_EVIDENCE = 5


def _match_edge(value: str) -> str | None:
    """Return the canonical edge name if ``value`` is a known
    CDN/WAF technology, else None. Case-insensitive."""
    lo = value.lower()
    return lo if lo in _CDN_TECHNOLOGIES else None


def detect_edge_blocking(scan_run: "ScanRun") -> dict | None:
    """Return a summary dict if the scan-run was edge-blocked, else None.

    Two heuristics, in order:
        1. A Finding identifies a known CDN/WAF (technology field
           matches the server_headers stub's CDN signatures). Edge
           name comes from that Finding.
        2. No identifying Finding, but ≥80% of Evidence rows are 4xx
           across at least 5 probes → ``edge="unknown_waf"``.

    Result shape:
        {
            "edge": "cloudflare" | "aws_cloudfront" | "unknown_waf" | ...,
            "blocked_count": int,   # 4xx Evidence rows
            "total_evidence": int,  # all Evidence rows for this run
        }
    """
    from apps.evidence.models import Evidence
    from apps.findings.models import Finding

    edge: str | None = None
    for f in Finding.objects.filter(scan_run=scan_run).only("data"):
        data = f.data or {}
        edge = _match_edge(str(data.get("technology", "")))
        if edge:
            break

    evidence_qs = Evidence.objects.filter(scan_run=scan_run)
    total = evidence_qs.count()
    blocked = evidence_qs.filter(
        data__status__gte=400, data__status__lt=500,
    ).count()

    if edge is None:
        if (
            total >= _UNKNOWN_WAF_MIN_EVIDENCE
            and blocked / total >= _UNKNOWN_WAF_THRESHOLD
        ):
            edge = "unknown_waf"
        else:
            return None

    return {
        "edge": edge,
        "blocked_count": blocked,
        "total_evidence": total,
    }
