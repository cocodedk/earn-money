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

if TYPE_CHECKING:
    from apps.scans.models import ScanRun


# Known CDN / WAF tokens. Matched case-insensitively against any
# Finding's `technology` field or `matched_header_value`. Keep the
# list narrow — false positives here hide real findings under a
# "scan was blocked" banner.
_EDGE_TOKENS: dict[str, str] = {
    "cloudflare": "cloudflare",
    "cloudfront": "cloudfront",
    "akamai": "akamai",
    "akamaighost": "akamai",
    "fastly": "fastly",
    "sucuri": "sucuri",
    "imperva": "imperva",
    "incapsula": "imperva",
}


def _match_edge(value: str) -> str | None:
    """Return the canonical edge name if ``value`` contains a known
    edge token, else None."""
    lo = value.lower()
    for token, edge in _EDGE_TOKENS.items():
        if token in lo:
            return edge
    return None


# A scan whose Evidence is mostly 4xx is almost certainly being
# blocked at an edge somewhere — even when no Finding identifies the
# vendor. Threshold deliberately high (80%) to avoid flagging
# normal scans whose well_known_paths probes return a 404 mix.
_UNKNOWN_WAF_THRESHOLD = 0.8
_UNKNOWN_WAF_MIN_EVIDENCE = 5


def detect_edge_blocking(scan_run: "ScanRun") -> dict | None:
    """Return a summary dict if the scan-run was edge-blocked, else None.

    Two heuristics, in order:
        1. A Finding identifies a known CDN/WAF (Cloudflare, Akamai,
           Fastly, …). Edge name comes from that Finding.
        2. No identifying Finding, but ≥80% of Evidence rows are 4xx
           across at least 5 probes → `edge="unknown_waf"`.

    Result shape:
        {
            "edge": "cloudflare" | "akamai" | "unknown_waf" | ...,
            "blocked_count": int,   # 4xx Evidence rows
            "total_evidence": int,  # all Evidence rows for this run
        }
    """
    from apps.evidence.models import Evidence
    from apps.findings.models import Finding

    edge: str | None = None
    for f in Finding.objects.filter(scan_run=scan_run).only("data"):
        data = f.data or {}
        for field in ("technology", "matched_header_value"):
            edge = _match_edge(str(data.get(field, "")))
            if edge:
                break
        if edge:
            break

    total = 0
    blocked = 0
    for ev in Evidence.objects.filter(scan_run=scan_run).only("data"):
        total += 1
        status = (ev.data or {}).get("status")
        if isinstance(status, int) and 400 <= status < 500:
            blocked += 1

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
