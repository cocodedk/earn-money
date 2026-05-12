"""Versioned SQLite schema migrations for per-program databases.

Each step bumps PRAGMA user_version by one. Steps are applied in order
inside a single transaction per step — partial failure leaves the DB
at the prior version, not at an in-between state.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

_V1_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    subdomain                TEXT PRIMARY KEY,
    ip                       TEXT,
    ports                    TEXT,
    fingerprint              TEXT,
    first_seen               TEXT NOT NULL,
    last_seen                TEXT NOT NULL,
    in_scope_at_observation  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS findings (
    finding_hash    TEXT PRIMARY KEY,
    vuln_class      TEXT NOT NULL,
    target          TEXT NOT NULL,
    first_seen      TEXT NOT NULL,
    current_state   TEXT NOT NULL,
    notes_path      TEXT NOT NULL
);
"""

_V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS recon_runs (
    run_id          TEXT PRIMARY KEY,
    platform        TEXT NOT NULL,
    slug            TEXT NOT NULL,
    tool            TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL,
    artifact_dir    TEXT NOT NULL,
    input_count     INTEGER NOT NULL DEFAULT 0,
    output_count    INTEGER NOT NULL DEFAULT 0,
    signal_count    INTEGER NOT NULL DEFAULT 0,
    source_failures INTEGER NOT NULL DEFAULT 0,
    oos_drops       INTEGER NOT NULL DEFAULT 0,
    terminated_reason TEXT,
    triaged_at      TEXT,
    error_summary   TEXT
);
CREATE TABLE IF NOT EXISTS http_services (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    subdomain                TEXT NOT NULL,
    scheme                   TEXT NOT NULL,
    port                     INTEGER NOT NULL,
    url                      TEXT NOT NULL,
    status_code              INTEGER,
    title                    TEXT,
    server                   TEXT,
    technologies             TEXT,
    redirect_to              TEXT,
    tls_summary              TEXT,
    observed_at              TEXT NOT NULL,
    last_run_id              TEXT NOT NULL,
    in_scope_at_observation  INTEGER NOT NULL DEFAULT 1,
    UNIQUE(subdomain, scheme, port)
);
CREATE TABLE IF NOT EXISTS signals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    tool         TEXT NOT NULL,
    signal_type  TEXT NOT NULL,
    asset        TEXT NOT NULL,
    target       TEXT NOT NULL,
    signature    TEXT NOT NULL,
    payload      TEXT NOT NULL,
    observed_at  TEXT NOT NULL,
    UNIQUE(run_id, signal_type, asset, target, signature)
);
"""


def _execute_script(conn: sqlite3.Connection, script: str) -> None:
    """Execute each statement in *script* individually via ``conn.execute()``.

    Unlike ``executescript()``, this does NOT issue an implicit COMMIT first,
    so statements run inside whatever transaction the caller has already opened
    and will roll back together with it on failure.
    """
    for stmt in script.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)


def _apply_v1(conn: sqlite3.Connection) -> None:
    _execute_script(conn, _V1_SCHEMA)


def _apply_v2(conn: sqlite3.Connection) -> None:
    _execute_script(conn, _V2_SCHEMA)


_STEPS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _apply_v1,
    2: _apply_v2,
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
