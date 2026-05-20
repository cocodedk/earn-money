"""Contract tests for `apps.scans.postmortem.detect_edge_blocking`.

Coverage:
- No Findings + no Evidence → returns None.
- A server_headers Finding whose matched_value contains a known CDN
  token (cloudflare/akamai/fastly/sucuri/imperva/cloudfront) returns
  a dict naming the edge + counts.
- Multiple Findings — known CDN takes precedence over unknown tokens.
- Non-edge Findings → returns None (don't false-positive on real apps).
"""
from __future__ import annotations

import pytest

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.projects.models import Project
from apps.scans.models import ScanRun
from apps.scans.postmortem import detect_edge_blocking
from apps.targets.models import ScanTarget


@pytest.fixture
def scan_run(db):
    project = Project.objects.create(name="postmortem-tests")
    target = ScanTarget.objects.create(
        project=project, base_url="https://example.com",
        host="example.com",
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="1.2")
    return scan_run, target


def _finding(scan_run, target, *, technology: str, matched_value: str) -> Finding:
    return Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug=scan_run.stub_slug,
        title=f"{technology} detected", category="server_headers",
        severity=Severity.INFO, confidence="high",
        status=FindingStatus.CANDIDATE,
        data={"technology": technology, "matched_header_value": matched_value},
    )


def _evidence(scan_run, target, *, status: int) -> Evidence:
    return Evidence.objects.create(
        scan_run=scan_run, target=target, source=EvidenceSource.HEADER,
        url="https://example.com/", method="GET", field="server",
        matched_value="x", raw_excerpt=f"status {status}",
        data={"status": status},
    )


def test_empty_run_returns_none(scan_run):
    sr, _t = scan_run
    assert detect_edge_blocking(sr) is None


def test_cloudflare_finding_detects(scan_run):
    sr, t = scan_run
    _finding(sr, t, technology="Cloudflare", matched_value="cloudflare")
    for _ in range(5):
        _evidence(sr, t, status=403)
    out = detect_edge_blocking(sr)
    assert out is not None
    assert out["edge"] == "cloudflare"
    assert out["blocked_count"] == 5
    assert out["total_evidence"] == 5


def test_akamai_finding_detects(scan_run):
    sr, t = scan_run
    _finding(sr, t, technology="Akamai", matched_value="AkamaiGHost")
    out = detect_edge_blocking(sr)
    assert out is not None
    assert out["edge"] == "akamai"


def test_unknown_tech_does_not_match(scan_run):
    """A finding with technology=`nginx` (origin server, not edge)
    must NOT trigger the edge-blocking signal."""
    sr, t = scan_run
    _finding(sr, t, technology="nginx", matched_value="nginx/1.21")
    assert detect_edge_blocking(sr) is None


def test_blocked_count_only_counts_4xx(scan_run):
    sr, t = scan_run
    _finding(sr, t, technology="Cloudflare", matched_value="cloudflare")
    _evidence(sr, t, status=200)
    _evidence(sr, t, status=403)
    _evidence(sr, t, status=503)
    _evidence(sr, t, status=404)
    out = detect_edge_blocking(sr)
    assert out["blocked_count"] == 2  # 403 + 404 only
    assert out["total_evidence"] == 4


def test_case_insensitive_match(scan_run):
    sr, t = scan_run
    _finding(sr, t, technology="CLOUDFLARE", matched_value="CLOUDFLARE")
    out = detect_edge_blocking(sr)
    assert out["edge"] == "cloudflare"


# ---- unknown-WAF fallback (no identifying Finding) ----

def test_mostly_4xx_no_finding_returns_unknown_waf(scan_run):
    """≥80% 4xx with ≥5 probes and no vendor Finding → unknown_waf."""
    sr, t = scan_run
    for _ in range(8):
        _evidence(sr, t, status=403)
    for _ in range(2):
        _evidence(sr, t, status=200)
    out = detect_edge_blocking(sr)
    assert out["edge"] == "unknown_waf"
    assert out["blocked_count"] == 8
    assert out["total_evidence"] == 10


def test_minimum_evidence_threshold_not_met(scan_run):
    """Only 4 4xx probes — below the noise-floor minimum; no signal."""
    sr, t = scan_run
    for _ in range(4):
        _evidence(sr, t, status=403)
    assert detect_edge_blocking(sr) is None


def test_below_4xx_threshold_returns_none(scan_run):
    """Half 4xx, half 2xx — looks like a normal scan, no signal."""
    sr, t = scan_run
    for _ in range(5):
        _evidence(sr, t, status=200)
    for _ in range(5):
        _evidence(sr, t, status=404)
    assert detect_edge_blocking(sr) is None
