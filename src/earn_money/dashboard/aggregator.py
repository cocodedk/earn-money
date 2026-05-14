"""Assemble the dashboard status snapshot from the per-program state.

Pure read. Per-program errors are contained: if one program's DB cannot
be opened or queried, the program is still rendered (with zero counts +
an `error` field) and the rest of the response is unaffected.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from earn_money import scope
from earn_money._time import now_iso
from earn_money.config import Paths
from earn_money.dashboard import aggregator_blocks
from earn_money.registry import iter_registered_programs


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
    returned with zero counts and an `error` key. Programming bugs
    (TypeError, AttributeError, KeyError) intentionally propagate so they
    surface in tests and logs rather than being silently swallowed.

    Two try blocks make the failure domains explicit: scope-read failure
    means we have no scope fields to merge, so we fall back to a
    platform+slug-only skeleton; DB failure means scope-read succeeded so
    we can keep those fields and only zero the DB block.
    """
    try:
        base = aggregator_blocks.scope_block(paths, platform, slug)
    except (scope.InvalidScope, OSError, ValueError) as exc:
        return _error_program(platform, slug, exc), False
    try:
        block, has_op_note = aggregator_blocks.db_block(paths, platform, slug)
    except (sqlite3.Error, OSError) as exc:
        return {**base, **aggregator_blocks.zero_db_block(),
                "error": f"{type(exc).__name__}: {exc}"}, False
    return {**base, **block}, has_op_note


def _error_program(
    platform: str, slug: str, exc: BaseException
) -> dict[str, Any]:
    return {"platform": platform, "slug": slug,
            **aggregator_blocks.zero_db_block(),
            "error": f"{type(exc).__name__}: {exc}"}


def _build_across(
    programs: list[dict[str, Any]], *, operator_note_seen: bool
) -> dict[str, Any]:
    total_findings = 0
    total_queued = 0
    total_info = 0
    active_runs: list[dict[str, Any]] = []
    recent_signals: list[dict[str, Any]] = []
    for prog in programs:
        states = prog.get("finding_states", {})
        total_findings += sum(states.values())
        total_queued += states.get("queued", 0)
        total_info += states.get("resolved_info", 0)
        for r in prog.get("active_runs") or []:
            active_runs.append({**r, "platform": prog["platform"],
                                "slug": prog["slug"]})
        for s in prog.get("recent_signals") or []:
            recent_signals.append({**s, "platform": prog["platform"],
                                   "slug": prog["slug"]})
    # Newest-first across programs; cap to 20 so the panel stays readable.
    recent_signals.sort(key=lambda r: r.get("observed_at") or "", reverse=True)
    denom = total_queued + total_info
    suppression = round(100.0 * total_info / denom, 1) if denom else 0.0
    return {
        "total_findings": total_findings,
        "total_queued": total_queued,
        "suppression_rate_pct": suppression,
        "ledger_eur": 0,
        "first_verified_with_operator_note": operator_note_seen,
        "active_runs": active_runs,
        "recent_signals": recent_signals[:20],
    }
