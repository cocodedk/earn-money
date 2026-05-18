"""DAO for the recon_runs table."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from earn_money._time import now_iso, to_iso


@dataclass(frozen=True)
class ReconRun:
    run_id: str
    platform: str
    slug: str
    tool: str
    started_at: str
    finished_at: str | None
    status: str
    artifact_dir: str
    input_count: int
    output_count: int
    signal_count: int
    source_failures: int
    oos_drops: int
    terminated_reason: str | None


def start_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    platform: str,
    slug: str,
    tool: str,
    started_at: str,
    artifact_dir: str,
    input_count: int,
) -> None:
    conn.execute(
        "INSERT INTO recon_runs (run_id, platform, slug, tool, started_at, "
        "status, artifact_dir, input_count) "
        "VALUES (?, ?, ?, ?, ?, 'in_progress', ?, ?)",
        (run_id, platform, slug, tool, started_at, artifact_dir, input_count),
    )
    conn.commit()


def finish_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    finished_at: str,
    status: str,
    output_count: int,
    signal_count: int,
    source_failures: int,
    oos_drops: int,
    terminated_reason: str | None = None,
    error_summary: str | None = None,
) -> None:
    conn.execute(
        "UPDATE recon_runs SET finished_at = ?, status = ?, "
        "output_count = ?, signal_count = ?, source_failures = ?, "
        "oos_drops = ?, terminated_reason = ?, error_summary = ? "
        "WHERE run_id = ?",
        (
            finished_at, status, output_count, signal_count,
            source_failures, oos_drops, terminated_reason, error_summary, run_id,
        ),
    )
    conn.commit()


def cleanup_stale_runs(
    conn: sqlite3.Connection,
    *,
    platform: str,
    slug: str,
    before: str | None = None,
    max_age_minutes: int = 60,
) -> int:
    """Mark in_progress runs as failed when they were started before `before`.

    `before` defaults to now minus `max_age_minutes`. Returns the count updated.
    Finished runs (any status other than in_progress) are never touched.
    """
    cutoff = before or to_iso(datetime.now(UTC) - timedelta(minutes=max_age_minutes))
    cursor = conn.execute(
        "UPDATE recon_runs SET finished_at = ?, status = 'failed', "
        "error_summary = 'process killed before finish_run' "
        "WHERE platform = ? AND slug = ? AND status = 'in_progress' "
        "AND started_at < ?",
        (now_iso(), platform, slug, cutoff),
    )
    conn.commit()
    return cursor.rowcount


def list_untriaged(
    conn: sqlite3.Connection, *, platform: str, slug: str
) -> list[ReconRun]:
    cursor = conn.execute(
        "SELECT run_id, platform, slug, tool, started_at, finished_at, "
        "status, artifact_dir, input_count, output_count, signal_count, "
        "source_failures, oos_drops, terminated_reason "
        "FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND finished_at IS NOT NULL AND triaged_at IS NULL "
        "ORDER BY started_at",
        (platform, slug),
    )
    return [ReconRun(*row) for row in cursor]
