from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import config, db, scope
from earn_money.recon import runs, services, signals
from earn_money.recon.services import HttpService
from earn_money.recon.signals import Signal
from earn_money.triage import engine


def _paths(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    return paths


def _seed_nuclei_run_with_signal(paths: config.Paths) -> None:
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        # Add a service so the engine can render asset context.
        services.upsert_service(conn, HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200,
            title="Acme API", server="nginx",
            technologies=("nginx",),
            redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        # The nuclei run we want triaged.
        runs.start_run(
            conn, run_id="nuclei-r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T02:15:00Z",
            artifact_dir="x", input_count=1,
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
            payload='{"template_id":"CVE-2023-1234","matcher_name":"primary",'
                    '"matched_at":"https://api.example.com/search?q=foo",'
                    '"severity":"high","name":"Acme SQLi"}',
            observed_at="2026-05-12T02:16:00Z",
        )])
    finally:
        conn.close()


def test_triages_one_nuclei_run_and_writes_queue_file(tmp_repo: Path) -> None:
    paths = _paths(tmp_repo)
    _seed_nuclei_run_with_signal(paths)

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-12T05:00:00Z",
    )
    assert result.runs_processed == 1
    assert result.findings_created == 1
    assert result.findings_refreshed == 0

    # The DB has one finding row.
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT vuln_class, title, severity_hint, source_tool, current_state "
        "FROM findings"
    ).fetchall()
    triaged_at = conn.execute(
        "SELECT triaged_at FROM recon_runs WHERE run_id = 'nuclei-r1'"
    ).fetchone()
    conn.close()

    assert len(rows) == 1
    vuln_class, title, severity_hint, source_tool, state = rows[0]
    assert vuln_class == "cve-2023-1234"
    assert "Acme SQLi" in title or "CVE-2023-1234" in title
    assert severity_hint == "high"
    assert source_tool == "nuclei"
    assert state == "queued"
    assert triaged_at[0] == "2026-05-12T05:00:00Z"

    # A queue markdown file exists.
    queue_dir = paths.root / "findings" / "_queue"
    files = list(queue_dir.glob("*.md"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "## What the scanner said" in body
    assert "CVE-2023-1234" in body


def test_re_triage_refreshes_finding_but_does_not_overwrite_queue_file(
    tmp_repo: Path,
) -> None:
    paths = _paths(tmp_repo)
    _seed_nuclei_run_with_signal(paths)

    # First triage pass.
    engine.run_program(paths, "hackerone", "example", now="2026-05-12T05:00:00Z")
    queue_files = list((paths.root / "findings" / "_queue").glob("*.md"))
    assert len(queue_files) == 1
    operator_edited = queue_files[0].read_text(encoding="utf-8") + "\n## Operator: started repro\n"
    queue_files[0].write_text(operator_edited, encoding="utf-8")

    # A second nuclei run produces the *same* finding hash (same signature).
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="nuclei-r2", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-13T02:15:00Z",
            artifact_dir="x2", input_count=1,
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
            payload='{"template_id":"CVE-2023-1234","severity":"high","name":"Acme SQLi"}',
            observed_at="2026-05-13T02:16:00Z",
        )])
    finally:
        conn.close()

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-13T05:00:00Z",
    )
    assert result.findings_created == 0
    assert result.findings_refreshed == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT occurrence_count, last_seen FROM findings"
    ).fetchone()
    conn.close()
    assert row[0] == 2
    assert row[1] == "2026-05-13T02:16:00Z"
    # Operator edit survives.
    assert "## Operator: started repro" in queue_files[0].read_text(encoding="utf-8")


def test_drops_signal_that_drifted_out_of_scope_between_scan_and_triage(
    tmp_repo: Path,
) -> None:
    paths = _paths(tmp_repo)
    # Seed the signal with an asset that's in-scope at scan time...
    _seed_nuclei_run_with_signal(paths)
    # ...then tighten scope so the asset is no longer in scope.
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["www.example.com"],
        out_of_scope=["api.example.com"],
        notes="", scope_hash="updated", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-12T05:00:00Z",
    )
    assert result.findings_created == 0
    assert result.signals_skipped == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    conn.close()
    assert count == 0


def test_drops_signal_with_oos_target_host_at_triage(tmp_repo: Path) -> None:
    """Defensive scope re-check covers both sig.asset AND sig.target's host.
    A signal whose asset stays in-scope but whose target URL drifted to an
    OOS host between scan and triage must be skipped."""
    paths = _paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="t", artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="r1", finished_at="t", status="success",
            output_count=1, signal_count=1, source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="r1", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://evil.example.com/leaked",
            signature="sig", payload="{}", observed_at="t",
        )])
    finally:
        conn.close()

    # Tighten scope: api.example.com stays in-scope but evil.example.com is OOS.
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["api.example.com"], out_of_scope=["evil.example.com"],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    result = engine.run_program(paths, "hackerone", "example", now="t")
    assert result.findings_created == 0
    assert result.signals_skipped == 1


def test_triages_all_untriaged_runs_and_marks_them(tmp_repo: Path) -> None:
    paths = _paths(tmp_repo)
    _seed_nuclei_run_with_signal(paths)
    # Add a second nuclei run with a different finding.
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="nuclei-r2", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T03:15:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r2", finished_at="2026-05-12T03:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r2", tool="nuclei", signal_type="template_match",
            asset="www.example.com",
            target="https://www.example.com/login",
            signature="http-default-creds|admin-admin|",
            payload='{"template_id":"http-default-creds","severity":"high",'
                    '"name":"Default admin/admin"}',
            observed_at="2026-05-12T03:17:00Z",
        )])
    finally:
        conn.close()

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-12T05:00:00Z",
    )
    assert result.runs_processed == 2
    assert result.findings_created == 2

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    triaged = conn.execute(
        "SELECT run_id, triaged_at FROM recon_runs ORDER BY run_id"
    ).fetchall()
    conn.close()
    assert all(row[1] == "2026-05-12T05:00:00Z" for row in triaged)
