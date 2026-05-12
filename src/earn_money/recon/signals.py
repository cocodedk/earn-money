"""DAO for the signals table — durable weak-signal index used by triage."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    run_id: str
    tool: str
    signal_type: str
    asset: str
    target: str
    signature: str
    payload: str
    observed_at: str


def insert_signals(conn: sqlite3.Connection, entries: Iterable[Signal]) -> int:
    """Insert each signal; silently skip rows that collide on the unique key.

    Returns the count of rows actually inserted.
    """
    rows = [
        (s.run_id, s.tool, s.signal_type, s.asset, s.target,
         s.signature, s.payload, s.observed_at)
        for s in entries
    ]
    if not rows:
        return 0
    cursor = conn.executemany(
        "INSERT OR IGNORE INTO signals "
        "(run_id, tool, signal_type, asset, target, signature, payload, observed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return cursor.rowcount


def signals_for_run(conn: sqlite3.Connection, run_id: str) -> list[Signal]:
    """Return all signals for a given run, ordered by insertion id."""
    cursor = conn.execute(
        "SELECT run_id, tool, signal_type, asset, target, signature, "
        "payload, observed_at FROM signals WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    return [Signal(*row) for row in cursor]
