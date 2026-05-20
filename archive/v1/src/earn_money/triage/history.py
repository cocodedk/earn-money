"""Finding state-machine transitions + append-only audit DAO.

Triage NEVER calls these helpers. The only callers in Phase 3b are tests;
Phase 4's `bin/submit` and the queue→verified operator workflow will
become the production callers. We ship the helper now so the state
machine is enforced from day one rather than retrofitted later.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from earn_money.triage.findings import FindingState


class IllegalStateTransition(Exception):
    """Raised when the requested (from_state, to_state) pair is not allowed."""


class FindingNotFound(Exception):
    """Raised when the target finding_hash is not present in the DB."""


@dataclass(frozen=True)
class StateChange:
    id: int
    finding_hash: str
    from_state: FindingState | None
    to_state: FindingState
    actor: str
    note: str | None
    changed_at: str


_ALLOWED: frozenset[tuple[FindingState, FindingState]] = frozenset({
    ("queued", "verified"),
    ("queued", "resolved_dupe"),
    ("queued", "resolved_na"),
    ("queued", "resolved_info"),
    ("verified", "submitted"),
    ("submitted", "resolved_paid"),
    ("submitted", "resolved_dupe"),
    ("submitted", "resolved_na"),
    ("submitted", "resolved_info"),
    ("resolved_paid", "archived"),
    ("resolved_dupe", "archived"),
    ("resolved_na", "archived"),
    ("resolved_info", "archived"),
})


def transition_state(
    conn: sqlite3.Connection,
    *,
    finding_hash: str,
    to_state: FindingState,
    actor: str,
    note: str | None,
    now: str,
) -> None:
    """Update findings.current_state AND write a history row atomically."""
    row = conn.execute(
        "SELECT current_state FROM findings WHERE finding_hash = ?",
        (finding_hash,),
    ).fetchone()
    if row is None:
        raise FindingNotFound(finding_hash)
    from_state: FindingState = row[0]
    if (from_state, to_state) not in _ALLOWED:
        raise IllegalStateTransition(
            f"{from_state!r} -> {to_state!r} is not an allowed transition"
        )
    conn.execute("BEGIN")
    try:
        conn.execute(
            "UPDATE findings SET current_state = ?, state_changed_at = ? "
            "WHERE finding_hash = ?",
            (to_state, now, finding_hash),
        )
        conn.execute(
            "INSERT INTO findings_state_history "
            "(finding_hash, from_state, to_state, actor, note, changed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (finding_hash, from_state, to_state, actor, note, now),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def state_history_for_hash(
    conn: sqlite3.Connection, finding_hash: str
) -> list[StateChange]:
    cursor = conn.execute(
        "SELECT id, finding_hash, from_state, to_state, actor, note, changed_at "
        "FROM findings_state_history WHERE finding_hash = ? "
        "ORDER BY id",
        (finding_hash,),
    )
    return [StateChange(*row) for row in cursor]
