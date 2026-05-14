"""Assemble the dashboard status snapshot from the per-program state.

Pure read. Per-program errors are contained: if one program's DB cannot
be opened or queried, the program is still rendered (with zero counts +
an `error` field) and the rest of the response is unaffected.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from earn_money import flags, scope
from earn_money._time import now_iso
from earn_money.config import Paths
from earn_money.registry import iter_registered_programs
from earn_money.triage import findings
from earn_money.triage.findings import Finding
from earn_money.triage.severity import sort_key

_TOP_QUEUE_LIMIT = 5
_RECENT_RUNS_LIMIT = 20


def build_status(paths: Paths, *, now: str | None = None) -> dict[str, Any]:
    """Return the JSON-serializable dashboard snapshot for ``paths``."""
    generated_at = now or now_iso()
    programs: list[dict[str, Any]] = []
    operator_note_seen = False
    for platform, slug in iter_registered_programs(paths):
        prog, prog_has_op_note = _build_program(paths, platform, slug)
        programs.append(prog)
        operator_note_seen = operator_note_seen or prog_has_op_note
    across = _build_across(programs, operator_note_seen=operator_note_seen)
    return {
        "generated_at": generated_at,
        "programs": programs,
        "across": across,
    }


def _build_program(
    paths: Paths, platform: str, slug: str
) -> tuple[dict[str, Any], bool]:
    """Return `(program_dict, has_operator_verified_note)`.

    A failure for one program does NOT propagate; the program is still
    returned with zero counts and an `error` key.
    """
    base = _scope_block(paths, platform, slug)
    try:
        db_block, has_op_note = _db_block(paths, platform, slug)
    except Exception as exc:
        return {**base, **_zero_db_block(), "error": f"{type(exc).__name__}: {exc}"}, False
    return {**base, **db_block}, has_op_note


def _scope_block(paths: Paths, platform: str, slug: str) -> dict[str, Any]:
    """Static, non-DB program fields: policy + freeze state."""
    s = scope.read_scope(paths.scope_file(platform, slug))
    frozen = flags.is_program_frozen(paths, platform, slug)
    frozen_reason: str | None = None
    if frozen:
        raw = flags.freeze_reason(paths, platform, slug)
        frozen_reason = _parse_freeze_reason(raw)
    return {
        "platform": platform,
        "slug": slug,
        "policy": s.policy,
        "last_synced": s.last_synced,
        "frozen": frozen,
        "frozen_reason": frozen_reason,
    }


def _db_block(
    paths: Paths, platform: str, slug: str
) -> tuple[dict[str, Any], bool]:
    """All DB-derived fields for a program. Missing DB => zero block."""
    db_path = paths.program_db(platform, slug)
    if not db_path.exists():
        return _zero_db_block(), False
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        counts = findings.count_findings_by_state(conn, platform=platform, slug=slug)
        queued = findings.findings_in_state(
            conn, platform=platform, slug=slug, state="queued",
        )
        return {
            "asset_count": _scalar(conn, "SELECT COUNT(*) FROM assets"),
            "http_service_count": _scalar(conn, "SELECT COUNT(*) FROM http_services"),
            "finding_states": dict(counts),
            "top_queue": _top_queue(queued),
            "recent_runs": _recent_runs(conn, platform, slug),
        }, _has_operator_verified_note(conn)
    finally:
        conn.close()


def _zero_db_block() -> dict[str, Any]:
    return {
        "asset_count": 0,
        "http_service_count": 0,
        "finding_states": {
            "queued": 0, "verified": 0, "submitted": 0,
            "resolved_paid": 0, "resolved_dupe": 0, "resolved_na": 0,
            "resolved_info": 0, "archived": 0,
        },
        "top_queue": [],
        "recent_runs": [],
    }


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    return int(row[0]) if row is not None else 0


def _top_queue(queued: list[Finding]) -> list[dict[str, Any]]:
    queued = sorted(queued, key=sort_key)[:_TOP_QUEUE_LIMIT]
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
        "ORDER BY started_at DESC LIMIT ?",
        (platform, slug, _RECENT_RUNS_LIMIT),
    )
    return [
        {
            "tool": row[0],
            "status": row[1],
            "started_at": row[2],
            "signal_count": row[3],
            "source_failures": row[4],
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


def _parse_freeze_reason(text: str) -> str | None:
    """Return the operator-supplied reason from a FROZEN flag file.

    Format written by ``flags.freeze_program`` is ``<timestamp>\\n<reason>\\n``,
    so the reason is everything after the first line. A single-line legacy
    file falls back to that line.
    """
    lines = text.splitlines()
    if len(lines) >= 2:
        return "\n".join(lines[1:]).strip() or None
    return lines[0].strip() if lines else None


def _build_across(
    programs: list[dict[str, Any]], *, operator_note_seen: bool
) -> dict[str, Any]:
    total_findings = 0
    total_queued = 0
    total_info = 0
    for prog in programs:
        states = prog.get("finding_states", {})
        total_findings += sum(states.values())
        total_queued += states.get("queued", 0)
        total_info += states.get("resolved_info", 0)
    denom = total_queued + total_info
    suppression = round(100.0 * total_info / denom, 1) if denom else 0.0
    return {
        "total_findings": total_findings,
        "total_queued": total_queued,
        "suppression_rate_pct": suppression,
        "ledger_eur": 0,
        "first_verified_with_operator_note": operator_note_seen,
    }
