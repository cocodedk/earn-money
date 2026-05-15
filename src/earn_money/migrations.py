"""Versioned SQLite schema migrations for per-program databases.

Each step bumps PRAGMA user_version by one. Steps are applied in order
inside a single transaction per step — partial failure leaves the DB
at the prior version, not at an in-between state.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from earn_money.migrations_schema import (
    _V1_SCHEMA,
    _V2_SCHEMA,
    _V3_SCHEMA_FINDINGS_COLUMNS,
    _V3_SCHEMA_HISTORY,
    _V4_SCHEMA,
    _V5_BENCHMARK_DISCLOSURE_COLUMNS,
    _V6_BENCHMARK_DISCLOSURE_COLUMNS,
    _V7_SCHEMA,
    _execute_script,
)


def _apply_v1(conn: sqlite3.Connection) -> None:
    _execute_script(conn, _V1_SCHEMA)


def _apply_v2(conn: sqlite3.Connection) -> None:
    _execute_script(conn, _V2_SCHEMA)


def _apply_v3(conn: sqlite3.Connection) -> None:
    """Widen `findings` and create `findings_state_history`."""
    # Read current columns once so we can be idempotent in the rare case
    # a partial v3 was applied earlier (e.g. crash between ALTERs).
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(findings)")
    }
    for name, definition in _V3_SCHEMA_FINDINGS_COLUMNS:
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE findings ADD COLUMN {name} {definition}")
    # Backfill `last_seen` and `state_changed_at` from `first_seen` on
    # legacy rows so the state machine has a real timestamp to work with.
    conn.execute(
        "UPDATE findings SET last_seen = first_seen "
        "WHERE last_seen = '' AND first_seen != ''"
    )
    conn.execute(
        "UPDATE findings SET state_changed_at = first_seen "
        "WHERE state_changed_at = '' AND first_seen != ''"
    )
    _execute_script(conn, _V3_SCHEMA_HISTORY)


def _apply_v4(conn: sqlite3.Connection) -> None:
    """Add benchmark_disclosures table for the disclosure-replay benchmark."""
    _execute_script(conn, _V4_SCHEMA)


def _apply_v5(conn: sqlite3.Connection) -> None:
    """Add provenance + reserved-for-Phase-B columns to benchmark_disclosures."""
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(benchmark_disclosures)")
    }
    for name, definition in _V5_BENCHMARK_DISCLOSURE_COLUMNS:
        if name in existing:
            continue
        conn.execute(
            f"ALTER TABLE benchmark_disclosures ADD COLUMN {name} {definition}"
        )


def _apply_v6(conn: sqlite3.Connection) -> None:
    """Add eligibility + verdict_source columns to benchmark_disclosures."""
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(benchmark_disclosures)")
    }
    for name, definition in _V6_BENCHMARK_DISCLOSURE_COLUMNS:
        if name in existing:
            continue
        conn.execute(
            f"ALTER TABLE benchmark_disclosures ADD COLUMN {name} {definition}"
        )


def _apply_v7(conn: sqlite3.Connection) -> None:
    """Add juice_shop_scores table for pre/post challenge tracking."""
    _execute_script(conn, _V7_SCHEMA)


_STEPS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _apply_v1,
    2: _apply_v2,
    3: _apply_v3,
    4: _apply_v4,
    5: _apply_v5,
    6: _apply_v6,
    7: _apply_v7,
}


def migrate(conn: sqlite3.Connection, *, target_version: int) -> None:
    """Bring ``conn`` up to ``target_version`` by running each pending step
    inside its own transaction. Idempotent: a DB already at or above the
    target is unchanged. A failing step leaves user_version at the prior
    successful step.

    Implementation note: ``with conn:`` does NOT open a transaction for DDL
    statements in Python's sqlite3 (it only auto-begins for DML). We therefore
    use explicit BEGIN / COMMIT / ROLLBACK so that DDL and the PRAGMA
    user_version bump are atomic together.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in sorted(_STEPS):
        if version <= current:
            continue
        if version > target_version:
            break
        conn.execute("BEGIN")
        try:
            _STEPS[version](conn)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
