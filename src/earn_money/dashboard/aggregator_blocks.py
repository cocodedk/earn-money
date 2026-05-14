"""Per-program block builders for the dashboard status payload.

Each block here is a pure read against the program's read-only SQLite
URI. `aggregator.py` orchestrates these into the full snapshot.
"""

from __future__ import annotations

import sqlite3
from typing import Any, get_args

from earn_money import flags, scope
from earn_money.config import Paths
from earn_money.triage import findings
from earn_money.triage.findings import Finding, FindingState

_TOP_QUEUE_LIMIT = 5
_RECENT_RUNS_LIMIT = 20
_RECENT_SIGNALS_LIMIT = 10


def scope_block(paths: Paths, platform: str, slug: str) -> dict[str, Any]:
    s = scope.read_scope(paths.scope_file(platform, slug))
    return {
        "platform": platform,
        "slug": slug,
        "policy": s.policy,
        "in_scope_count": len(s.in_scope),
        "last_synced": s.last_synced,
        "frozen": paths.freeze_flag(platform, slug).exists(),
        "frozen_reason": flags.freeze_reason_text(paths, platform, slug),
    }


def db_block(
    paths: Paths, platform: str, slug: str
) -> tuple[dict[str, Any], bool]:
    """All DB-derived fields for a program. Missing DB => zero block."""
    db_path = paths.program_db(platform, slug)
    if not db_path.exists():
        return zero_db_block(), False
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        counts = findings.count_findings_by_state(conn, platform=platform, slug=slug)
        top = findings.top_queued_findings(
            conn, platform=platform, slug=slug, limit=_TOP_QUEUE_LIMIT,
        )
        return {
            "asset_count": _scalar(conn, "SELECT COUNT(*) FROM assets"),
            "http_service_count": _scalar(conn, "SELECT COUNT(*) FROM http_services"),
            "finding_states": dict(counts),
            "top_queue": _top_queue(top),
            "recent_runs": _recent_runs(conn, platform, slug),
            "recent_signals": _recent_signals(conn, platform, slug),
            "active_runs": _active_runs(conn, platform, slug),
        }, _has_operator_verified_note(conn)
    finally:
        conn.close()


def zero_db_block() -> dict[str, Any]:
    """The fallback shape when a program has no DB yet — used both for
    fresh installs and for programs whose DB-open raised."""
    return {
        "asset_count": 0,
        "http_service_count": 0,
        "finding_states": {state: 0 for state in get_args(FindingState)},
        "top_queue": [],
        "recent_runs": [],
        "recent_signals": [],
        "active_runs": [],
    }


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    return int(row[0]) if row is not None else 0


def _top_queue(queued: list[Finding]) -> list[dict[str, Any]]:
    return [
        {
            "hash": f.finding_hash[:8],
            "vuln_class": f.vuln_class,
            "severity": f.severity_hint,
            "asset": f.asset,
            "first_seen": f.first_seen,
        }
        for f in queued
    ]


def _recent_runs(
    conn: sqlite3.Connection, platform: str, slug: str
) -> list[dict[str, Any]]:
    cursor = conn.execute(
        "SELECT tool, status, started_at, signal_count, source_failures "
        "FROM recon_runs WHERE platform = ? AND slug = ? "
        "ORDER BY started_at DESC, run_id DESC LIMIT ?",
        (platform, slug, _RECENT_RUNS_LIMIT),
    )
    return [
        {
            "tool": row[0], "status": row[1], "started_at": row[2],
            "signal_count": row[3], "source_failures": row[4],
        }
        for row in cursor
    ]


def _active_runs(
    conn: sqlite3.Connection, platform: str, slug: str
) -> list[dict[str, Any]]:
    """Runs with no finished_at — currently in flight from the dashboard's
    point of view. Ordered most-recent-started first."""
    cursor = conn.execute(
        "SELECT run_id, tool, started_at FROM recon_runs "
        "WHERE platform = ? AND slug = ? AND finished_at IS NULL "
        "ORDER BY started_at DESC",
        (platform, slug),
    )
    return [
        {"run_id": row[0], "tool": row[1], "started_at": row[2]}
        for row in cursor
    ]


def _recent_signals(
    conn: sqlite3.Connection, platform: str, slug: str
) -> list[dict[str, Any]]:
    """Last N signals, newest first. Useful for live ops visibility —
    the operator sees what just landed, not just aggregate counts."""
    cursor = conn.execute(
        "SELECT tool, signal_type, asset, target, signature, observed_at "
        "FROM signals ORDER BY id DESC LIMIT ?",
        (_RECENT_SIGNALS_LIMIT,),
    )
    return [
        {
            "tool": row[0],
            "signal_type": row[1],
            "asset": row[2],
            "target": row[3],
            "signature": row[4][:60] if row[4] else "",
            "observed_at": row[5],
        }
        for row in cursor
    ]


def _has_operator_verified_note(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM findings_state_history "
        "WHERE actor = 'operator' AND note IS NOT NULL AND note != '' "
        "AND to_state IN ('verified','resolved_dupe','resolved_na','resolved_paid') "
        "LIMIT 1"
    ).fetchone()
    return row is not None
