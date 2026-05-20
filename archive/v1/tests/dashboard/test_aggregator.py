"""Tests for the dashboard status aggregator."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

from earn_money import db, flags
from earn_money.dashboard import aggregator
from earn_money.triage import history
from earn_money.triage.findings import FindingState
from tests.triage.conftest import (
    engine_paths,
    register_program,
    seed_queued,
)

_NOW = "2026-05-14T09:00:00Z"


def test_empty_repo_returns_no_programs(tmp_repo: Path) -> None:
    from earn_money import config

    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    status = aggregator.build_status(paths, now=_NOW)
    assert status["generated_at"] == _NOW
    assert status["programs"] == []
    assert status["across"]["total_findings"] == 0
    assert status["across"]["total_queued"] == 0
    assert status["across"]["suppression_rate_pct"] == 0.0
    assert status["across"]["ledger_eur"] == 0
    assert status["across"]["first_verified_with_operator_note"] is False


def test_one_program_with_queued_finding(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        seed_queued(conn)
    finally:
        conn.close()

    status = aggregator.build_status(paths, now=_NOW)
    assert len(status["programs"]) == 1
    prog = status["programs"][0]
    assert prog["platform"] == "hackerone"
    assert prog["slug"] == "example"
    assert prog["policy"] == "rate-limited-OK"
    assert prog["frozen"] is False
    assert prog["frozen_reason"] is None
    assert prog["finding_states"]["queued"] == 1
    assert set(prog["finding_states"].keys()) == set(get_args(FindingState))
    # Top queue surfaces the seeded finding via promoted severity.sort_key.
    assert len(prog["top_queue"]) == 1
    assert prog["top_queue"][0]["hash"] == "h1"[:8]
    assert prog["top_queue"][0]["severity"] == "medium"
    assert status["across"]["total_findings"] == 1
    assert status["across"]["total_queued"] == 1


def test_frozen_program_reports_freeze_reason(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    reason = "scope diff: api.example.com moved OOS"
    flags.freeze_program(paths, "hackerone", "example", reason=reason)
    status = aggregator.build_status(paths, now=_NOW)
    prog = status["programs"][0]
    assert prog["frozen"] is True
    assert prog["frozen_reason"] == reason


def test_first_verified_with_operator_note_flag(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        seed_queued(conn)
    finally:
        conn.close()

    # Negative: only a queued finding => predicate is False.
    status = aggregator.build_status(paths, now=_NOW)
    assert status["across"]["first_verified_with_operator_note"] is False

    # Positive: a verified transition with an operator note flips the flag.
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        history.transition_state(
            conn,
            finding_hash="h1",
            to_state="verified",
            actor="operator",
            note="impact: account takeover via PoC",
            now="2026-05-14T08:30:00Z",
        )
    finally:
        conn.close()

    status = aggregator.build_status(paths, now=_NOW)
    assert status["across"]["first_verified_with_operator_note"] is True


def test_active_runs_surface_runs_without_finished_at(tmp_repo: Path) -> None:
    """Runs with finished_at IS NULL show up under program.active_runs
    AND in across.active_runs (with platform+slug stamped on)."""
    from earn_money.recon import runs as runs_dao
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs_dao.start_run(
            conn, run_id="in-flight", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-14T08:00:00Z",
            artifact_dir="x", input_count=1,
        )
        # Add a finished run too — should NOT appear in active_runs.
        runs_dao.start_run(
            conn, run_id="finished", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-14T07:30:00Z",
            artifact_dir="x", input_count=1,
        )
        runs_dao.finish_run(
            conn, run_id="finished", finished_at="2026-05-14T07:35:00Z",
            status="success", output_count=1, signal_count=0,
            source_failures=0, oos_drops=0,
        )
    finally:
        conn.close()

    status = aggregator.build_status(paths, now=_NOW)
    prog = status["programs"][0]
    assert len(prog["active_runs"]) == 1
    assert prog["active_runs"][0]["run_id"] == "in-flight"
    assert prog["active_runs"][0]["tool"] == "nuclei"
    assert status["across"]["active_runs"][0]["platform"] == "hackerone"
    assert status["across"]["active_runs"][0]["slug"] == "example"


def test_recent_signals_newest_first_across_programs(tmp_repo: Path) -> None:
    """across.recent_signals merges per-program signals newest-first,
    stamped with platform+slug so the UI can link back."""
    from earn_money.recon.signals import Signal, insert_signals
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        insert_signals(conn, [
            Signal(
                run_id="r1", tool="nuclei", signal_type="template_match",
                asset="api.example.com", target="https://api.example.com/",
                signature="weak-csp-detect|x|", payload="{}",
                observed_at="2026-05-14T08:00:00Z",
            ),
            Signal(
                run_id="r1", tool="subzy", signal_type="takeover_vulnerable",
                asset="mta.example.com", target="https://mta.example.com/",
                signature="subzy|heroku|mta.example.com", payload="{}",
                observed_at="2026-05-14T09:30:00Z",
            ),
        ])
    finally:
        conn.close()

    status = aggregator.build_status(paths, now=_NOW)
    sigs = status["across"]["recent_signals"]
    # Newest first.
    assert sigs[0]["observed_at"] == "2026-05-14T09:30:00Z"
    assert sigs[0]["tool"] == "subzy"
    assert sigs[1]["tool"] == "nuclei"
    # Platform/slug stamps so the UI can link.
    assert sigs[0]["platform"] == "hackerone"
    assert sigs[0]["slug"] == "example"


def test_aggregator_does_not_create_missing_db_file(tmp_repo: Path) -> None:
    paths = engine_paths(tmp_repo)
    register_program(paths, platform="hackerone", slug="example2")
    assert not paths.program_db("hackerone", "example2").exists()

    status = aggregator.build_status(paths, now=_NOW)
    # Aggregator must remain pure-read: no DB file created for example2.
    assert not paths.program_db("hackerone", "example2").exists()
    # Drift guard: the missing-DB zero block must enumerate every FindingState
    # value — adding a new state to the Literal should automatically appear
    # here without a manual edit in _zero_db_block.
    by_slug = {p["slug"]: p for p in status["programs"]}
    assert set(by_slug["example2"]["finding_states"].keys()) == set(get_args(FindingState))
