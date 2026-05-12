from __future__ import annotations

import re

from earn_money.recon.services import HttpService
from earn_money.triage import queue
from earn_money.triage.findings import Finding


def _finding() -> Finding:
    return Finding(
        finding_hash="abc123",
        platform="hackerone", slug="example",
        vuln_class="cve-2023-1234",
        asset="api.example.com",
        target="https://api.example.com/search?q=foo",
        signature="CVE-2023-1234|primary|",
        title="CVE-2023-1234 hit on api.example.com",
        severity_hint="high", confidence=70,
        source_tool="nuclei", source_run_id="r1",
        evidence_path="recon/outputs/.../raw.jsonl",
        notes_path="findings/_queue/abc123.md",
        first_seen="2026-05-12T05:00:00Z",
        last_seen="2026-05-12T05:00:00Z",
        occurrence_count=1, current_state="queued",
        state_changed_at="2026-05-12T05:00:00Z",
        external_report_id=None, payout_amount=None, payout_currency=None,
    )


def _service() -> HttpService:
    return HttpService(
        subdomain="api.example.com", scheme="https", port=443,
        url="https://api.example.com/", status_code=200,
        title="Acme API", server="nginx",
        technologies=("nginx", "openresty"),
        redirect_to=None, tls_summary=None,
        observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
        in_scope_at_observation=True,
    )


def test_render_includes_frontmatter_and_title() -> None:
    md = queue.render(_finding(), service=_service())
    assert md.startswith("---\n")
    assert "finding_hash: abc123\n" in md
    assert "state: queued\n" in md
    assert "---\n\n# CVE-2023-1234 hit on api.example.com" in md


def test_render_lists_asset_context_when_service_provided() -> None:
    md = queue.render(_finding(), service=_service())
    assert "Status 200" in md or "status 200" in md
    assert "nginx" in md
    assert "openresty" in md
    assert "Latest observation: 2026-05-12T01:05:00Z" in md


def test_render_handles_missing_service_gracefully() -> None:
    md = queue.render(_finding(), service=None)
    assert "Asset context" in md
    assert "no recent httpx" in md.lower()


def test_render_contains_verification_checklist() -> None:
    md = queue.render(_finding(), service=_service())
    assert "Reproduce the matcher hit manually" in md
    assert "Capture one redacted screenshot" in md


def test_render_starts_with_yaml_dashes_and_ends_with_newline() -> None:
    md = queue.render(_finding(), service=_service())
    assert md.startswith("---\n")
    assert md.endswith("\n")
    frontmatter_end = md.find("\n---\n", 4)
    assert frontmatter_end > 0
    assert re.search(r"---\n\n# ", md) is not None
