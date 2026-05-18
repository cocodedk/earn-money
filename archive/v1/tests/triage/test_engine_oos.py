"""Triage engine: defensive scope re-check (queued signals dropped if scope drifted)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db, scope
from earn_money.recon import runs, signals
from earn_money.recon.signals import Signal
from earn_money.triage import engine
from tests.triage.conftest import engine_paths, seed_nuclei_run_with_signal


def test_drops_signal_that_drifted_out_of_scope_between_scan_and_triage(
    tmp_repo: Path,
) -> None:
    paths = engine_paths(tmp_repo)
    # Seed the signal with an asset that's in-scope at scan time...
    seed_nuclei_run_with_signal(paths)
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
    try:
        count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_drops_signal_with_oos_target_host_at_triage(tmp_repo: Path) -> None:
    """Defensive scope re-check covers both sig.asset AND sig.target's host.
    A signal whose asset stays in-scope but whose target URL drifted to an
    OOS host between scan and triage must be skipped."""
    paths = engine_paths(tmp_repo)
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
