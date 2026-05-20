from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import runs


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def test_start_run_inserts_in_progress_row(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    runs.start_run(
        conn,
        run_id="r1",
        platform="hackerone",
        slug="example",
        tool="httpx",
        started_at="2026-05-12T08:00:00Z",
        artifact_dir="recon/outputs/hackerone/example/httpx/2026-05-12/r1",
        input_count=10,
    )
    row = conn.execute(
        "SELECT status, finished_at, input_count FROM recon_runs WHERE run_id = ?",
        ("r1",),
    ).fetchone()
    assert row == ("in_progress", None, 10)


def test_finish_run_updates_status_and_counters(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    runs.start_run(
        conn, run_id="r2", platform="hackerone", slug="example",
        tool="httpx", started_at="2026-05-12T08:00:00Z",
        artifact_dir="d", input_count=10,
    )
    runs.finish_run(
        conn, run_id="r2", finished_at="2026-05-12T08:05:00Z",
        status="success", output_count=8, signal_count=2,
        source_failures=0, oos_drops=1,
    )
    row = conn.execute(
        "SELECT status, finished_at, output_count, signal_count, "
        "source_failures, oos_drops FROM recon_runs WHERE run_id = ?",
        ("r2",),
    ).fetchone()
    assert row == ("success", "2026-05-12T08:05:00Z", 8, 2, 0, 1)


def test_cleanup_stale_runs_marks_old_in_progress_as_failed(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    # old in_progress run (2 hours ago)
    runs.start_run(
        conn, run_id="old", platform="p", slug="s", tool="nuclei",
        started_at="2026-05-16T00:00:00Z", artifact_dir="d", input_count=1,
    )
    # recent in_progress run (5 minutes ago — should not be cleaned)
    runs.start_run(
        conn, run_id="recent", platform="p", slug="s", tool="nuclei",
        started_at="2026-05-16T01:55:00Z", artifact_dir="d", input_count=1,
    )
    cleaned = runs.cleanup_stale_runs(
        conn, platform="p", slug="s",
        before="2026-05-16T01:00:00Z",
    )
    assert cleaned == 1
    rows = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT run_id, status FROM recon_runs WHERE platform='p' AND slug='s'"
        ).fetchall()
    }
    assert rows["old"] == "failed"
    assert rows["recent"] == "in_progress"


def test_cleanup_stale_runs_ignores_already_finished(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    runs.start_run(
        conn, run_id="done", platform="p", slug="s", tool="httpx",
        started_at="2026-05-16T00:00:00Z", artifact_dir="d", input_count=1,
    )
    runs.finish_run(
        conn, run_id="done", finished_at="2026-05-16T00:01:00Z", status="success",
        output_count=1, signal_count=0, source_failures=0, oos_drops=0,
    )
    cleaned = runs.cleanup_stale_runs(
        conn, platform="p", slug="s", before="2026-05-16T02:00:00Z",
    )
    assert cleaned == 0
    status = conn.execute(
        "SELECT status FROM recon_runs WHERE run_id='done'"
    ).fetchone()[0]
    assert status == "success"


def test_list_untriaged_returns_finished_runs_only(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    runs.start_run(
        conn, run_id="a", platform="p", slug="s", tool="httpx",
        started_at="t", artifact_dir="d", input_count=0,
    )
    runs.start_run(
        conn, run_id="b", platform="p", slug="s", tool="httpx",
        started_at="t", artifact_dir="d", input_count=0,
    )
    runs.finish_run(
        conn, run_id="b", finished_at="t", status="success",
        output_count=0, signal_count=0, source_failures=0, oos_drops=0,
    )
    untriaged = [r.run_id for r in runs.list_untriaged(conn, platform="p", slug="s")]
    assert untriaged == ["b"]
