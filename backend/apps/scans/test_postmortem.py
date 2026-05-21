"""Contract tests for `apps.scans.postmortem.detect_edge_blocking`.

Coverage:
- No Findings + no Evidence → None.
- A server_headers Finding whose `technology` field matches a CDN
  signature (cloudflare, aws_cloudfront) → dict naming the edge.
- Origin-server Findings (nginx, apache_httpd) → None — must not
  flag a normal site as edge-blocked.
- Evidence 4xx counting uses SQL aggregates (`data__status__gte=400`).
- Unknown-WAF fallback fires when ≥80% of ≥5 probes are 4xx and no
  CDN Finding identifies the vendor.
- Below the noise floor (<5 probes, or <80%) → None.
"""
from __future__ import annotations

import pytest

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.postmortem import detect_edge_blocking
from apps.stubs._test_factories import seed_target_run


@pytest.fixture
def run_pair(db):
    """One ScanRun + ScanTargetRun, the canonical seeding used by every
    other stub-related test in this repo."""
    scan_run, target_run = seed_target_run(
        stub_slug="1.2", host="x.example",
    )
    return scan_run, target_run.target


def _finding(scan_run, target, *, technology: str) -> Finding:
    return Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=scan_run.stub_slug,
        title=f"{technology} detected", category="server_headers",
        severity=Severity.INFO, confidence="high",
        status=FindingStatus.CANDIDATE,
        data={"technology": technology},
    )


def _evidence(scan_run, target, *, status: int) -> Evidence:
    return Evidence.objects.create(
        scan_run=scan_run, target=target, source=EvidenceSource.HEADER,
        url="https://x.example/", method="GET", field="server",
        matched_value="x", raw_excerpt=f"status {status}",
        data={"status": status},
    )


def test_empty_run_returns_none(run_pair):
    sr, _t = run_pair
    assert detect_edge_blocking(sr) is None


def test_cloudflare_finding_detects(run_pair):
    sr, t = run_pair
    _finding(sr, t, technology="cloudflare")
    for _ in range(5):
        _evidence(sr, t, status=403)
    out = detect_edge_blocking(sr)
    assert out == {
        "edge": "cloudflare", "blocked_count": 5, "total_evidence": 5,
    }


def test_cloudfront_finding_detects(run_pair):
    sr, t = run_pair
    _finding(sr, t, technology="aws_cloudfront")
    for _ in range(5):
        _evidence(sr, t, status=403)
    out = detect_edge_blocking(sr)
    assert out is not None
    assert out["edge"] == "aws_cloudfront"


def test_cdn_finding_without_blocking_evidence_returns_none(run_pair):
    """Codex P2.2 — a Cloudflare/CloudFront/etc Finding is no longer
    sufficient on its own. Sites behind a CDN that aren't actually
    being blocked (all evidence 200) must NOT trigger the banner."""
    sr, t = run_pair
    _finding(sr, t, technology="cloudflare")
    for _ in range(10):
        _evidence(sr, t, status=200)
    assert detect_edge_blocking(sr) is None


def test_cdn_finding_with_partial_blocking_below_threshold_none(run_pair):
    """CDN Finding + 6 evidence rows but only 1 is 4xx (below the
    80% threshold) → None. Same precondition for identified and
    unknown edges."""
    sr, t = run_pair
    _finding(sr, t, technology="cloudflare")
    for _ in range(5):
        _evidence(sr, t, status=200)
    _evidence(sr, t, status=403)
    assert detect_edge_blocking(sr) is None


def test_origin_server_does_not_match(run_pair):
    """A finding with technology=`nginx` (origin, not CDN) must NOT
    trigger the edge-blocking signal."""
    sr, t = run_pair
    _finding(sr, t, technology="nginx")
    assert detect_edge_blocking(sr) is None


def test_blocked_count_only_counts_4xx(run_pair):
    """Only 4xx counts as blocked; 5xx and 2xx don't. With 5 total
    evidence rows (4× 4xx + 1× 5xx) the 80% threshold is met → dict
    returned with the correct blocked_count."""
    sr, t = run_pair
    _finding(sr, t, technology="cloudflare")
    for _ in range(4):
        _evidence(sr, t, status=403)
    _evidence(sr, t, status=503)  # 5xx — not blocked-count
    out = detect_edge_blocking(sr)
    assert out["blocked_count"] == 4
    assert out["total_evidence"] == 5


def test_case_insensitive_match(run_pair):
    sr, t = run_pair
    _finding(sr, t, technology="CLOUDFLARE")
    for _ in range(5):
        _evidence(sr, t, status=403)
    out = detect_edge_blocking(sr)
    assert out["edge"] == "cloudflare"


# ---- unknown-WAF fallback (no identifying Finding) ----

def test_mostly_4xx_no_finding_returns_unknown_waf(run_pair):
    """≥80% 4xx with ≥5 probes and no CDN Finding → unknown_waf."""
    sr, t = run_pair
    for _ in range(8):
        _evidence(sr, t, status=403)
    for _ in range(2):
        _evidence(sr, t, status=200)
    out = detect_edge_blocking(sr)
    assert out == {
        "edge": "unknown_waf", "blocked_count": 8, "total_evidence": 10,
    }


def test_minimum_evidence_threshold_not_met(run_pair):
    """Only 4 4xx probes — below the noise-floor minimum; no signal."""
    sr, t = run_pair
    for _ in range(4):
        _evidence(sr, t, status=403)
    assert detect_edge_blocking(sr) is None


def test_below_4xx_threshold_returns_none(run_pair):
    """Half 4xx, half 2xx — looks like a normal scan, no signal."""
    sr, t = run_pair
    for _ in range(5):
        _evidence(sr, t, status=200)
    for _ in range(5):
        _evidence(sr, t, status=404)
    assert detect_edge_blocking(sr) is None
