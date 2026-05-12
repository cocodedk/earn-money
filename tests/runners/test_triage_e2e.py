"""End-to-end through the triage engine.

This test exercises the full triage path without any subprocesses: it
seeds a finished nuclei recon_runs row + a signal in SQLite, runs the
triage engine, and asserts the finding row, queue markdown, and
triaged_at timestamp are all correctly written.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import config, db, scope
from earn_money.recon import runs, services, signals
from earn_money.recon.services import HttpService
from earn_money.recon.signals import Signal
from earn_money.runners import triage


def _seed_repo(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        services.upsert_service(conn, HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200,
            title="Acme API", server="nginx",
            technologies=("nginx",),
            redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="nuclei-r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T02:15:00Z",
            artifact_dir="recon/outputs/hackerone/example/nuclei/2026-05-12/nuclei-r1",
            input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r1", finished_at="2026-05-12T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r1", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/search?q=foo",
            signature="CVE-2023-1234|primary|",
            payload=(
                '{"template_id":"CVE-2023-1234","matcher_name":"primary",'
                '"matched_at":"https://api.example.com/search?q=foo",'
                '"severity":"high","name":"Acme SQLi"}'
            ),
            observed_at="2026-05-12T02:16:00Z",
        )])
    finally:
        conn.close()
    return paths


def test_triage_e2e_creates_finding_and_queue_markdown(tmp_repo: Path) -> None:
    paths = _seed_repo(tmp_repo)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 0

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT vuln_class, severity_hint, current_state, occurrence_count "
        "FROM findings"
    ).fetchall()
    triaged = conn.execute(
        "SELECT triaged_at FROM recon_runs WHERE run_id = 'nuclei-r1'"
    ).fetchone()
    conn.close()
    assert rows == [("cve-2023-1234", "high", "queued", 1)]
    assert triaged[0] is not None

    files = list((paths.root / "findings" / "_queue").glob("*.md"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "CVE-2023-1234" in body
    assert "Acme SQLi" in body
    assert "## What we need to confirm before this is a finding" in body
    assert "Latest observation: 2026-05-12T01:05:00Z" in body


def test_triage_correlates_signals_across_runs(tmp_repo: Path) -> None:
    """P1.4: Two recon_runs with the same signature+asset must produce one
    finding with occurrence_count=2, not two separate finding rows."""
    paths = _seed_repo(tmp_repo)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="nuclei-r2", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-13T02:15:00Z",
            artifact_dir="recon/outputs/hackerone/example/nuclei/2026-05-13/nuclei-r2",
            input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r2", finished_at="2026-05-13T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r2", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/search?q=foo",
            signature="CVE-2023-1234|primary|",
            payload=(
                '{"template_id":"CVE-2023-1234","matcher_name":"primary",'
                '"matched_at":"https://api.example.com/search?q=foo",'
                '"severity":"high","name":"Acme SQLi"}'
            ),
            observed_at="2026-05-13T02:16:00Z",
        )])
    finally:
        conn.close()

    rc1 = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc1 == 0
    rc2 = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc2 == 0

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT finding_hash, occurrence_count FROM findings"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, f"expected 1 finding, got {len(rows)}"
    assert rows[0][1] == 2, f"expected occurrence_count=2, got {rows[0][1]}"
