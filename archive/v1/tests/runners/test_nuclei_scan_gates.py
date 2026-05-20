"""Gate refusal and prereq-freshness tests for the nuclei-scan runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, flags, policy, scope
from earn_money.runners import active, nuclei_scan


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"],
        out_of_scope=out_of_scope or [],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


# ---------------------------------------------------------------------------
# Gate refusal tests
# ---------------------------------------------------------------------------

def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    with pytest.raises(flags.ReconDisabled):
        nuclei_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=[]),
        )


def test_refuses_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only")
    with pytest.raises(policy.PolicyViolation):
        nuclei_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=[]),
        )


# ---------------------------------------------------------------------------
# Prereq freshness tests
# ---------------------------------------------------------------------------

def test_writes_prereq_missing_signal_when_no_recent_httpx(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    # No httpx run seeded.
    result = nuclei_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=[]),
    )
    assert result.targets_scanned == 0
    assert result.outputs_recorded == 0
    assert result.prereq_skipped is True

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT signal_type FROM signals").fetchall()
    run_status = conn.execute(
        "SELECT status, error_summary FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchone()
    conn.close()
    assert rows == [("prereq_missing",)]
    assert run_status[0] == "skipped"
    assert "no recent httpx run" in run_status[1]


def test_partial_httpx_run_with_no_outputs_does_not_satisfy_prereq(
    tmp_repo: Path,
) -> None:
    """A partial httpx run with output_count=0 must NOT unlock nuclei."""
    from earn_money.recon import runs

    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-partial", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=3,
        )
        runs.finish_run(
            conn, run_id="httpx-partial", finished_at="2026-05-12T01:05:00Z",
            status="partial", output_count=0,
            signal_count=0, source_failures=1, oos_drops=0,
        )
    finally:
        conn.close()

    result = nuclei_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=[]),
    )
    assert result.targets_scanned == 0
    assert result.outputs_recorded == 0
    assert result.prereq_skipped is True

    conn2 = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn2.execute("SELECT signal_type FROM signals").fetchall()
    run_status = conn2.execute(
        "SELECT status FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchone()
    conn2.close()
    assert rows == [("prereq_missing",)]
    assert run_status[0] == "skipped"


def test_success_httpx_run_with_no_outputs_does_not_satisfy_prereq(
    tmp_repo: Path,
) -> None:
    """A 'success' httpx run with output_count=0 must NOT satisfy the
    nuclei prereq. The freshness predicate requires output_count > 0
    in addition to status IN (success, partial)."""
    from earn_money.recon import runs

    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=0,
            signal_count=0, source_failures=0, oos_drops=0,
        )
    finally:
        conn.close()

    result = nuclei_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=()),
    )
    # The prereq is unsatisfied — nuclei writes a prereq_missing signal.
    assert result.outputs_recorded == 0
    assert result.prereq_skipped is True

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT signal_type FROM signals WHERE tool='nuclei'"
    ).fetchall()
    conn.close()
    assert rows == [("prereq_missing",)]
