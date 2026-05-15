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


_V3_SCHEMA_FINDINGS_COLUMNS: tuple[tuple[str, str], ...] = (
    # (column_name, full ALTER TABLE column-def fragment)
    ("platform",            "TEXT NOT NULL DEFAULT '__legacy__'"),
    ("slug",                "TEXT NOT NULL DEFAULT '__legacy__'"),
    ("asset",               "TEXT NOT NULL DEFAULT ''"),
    ("signature",           "TEXT NOT NULL DEFAULT ''"),
    ("title",               "TEXT NOT NULL DEFAULT ''"),
    ("severity_hint",       "TEXT NOT NULL DEFAULT 'unknown'"),
    ("confidence",          "INTEGER NOT NULL DEFAULT 0"),
    ("source_tool",         "TEXT NOT NULL DEFAULT 'legacy'"),
    ("source_run_id",       "TEXT NOT NULL DEFAULT ''"),
    ("evidence_path",       "TEXT NOT NULL DEFAULT ''"),
    ("last_seen",           "TEXT NOT NULL DEFAULT ''"),
    ("occurrence_count",    "INTEGER NOT NULL DEFAULT 1"),
    ("state_changed_at",    "TEXT NOT NULL DEFAULT ''"),
    ("external_report_id",  "TEXT"),
    ("payout_amount",       "TEXT"),
    ("payout_currency",     "TEXT"),
)

_V3_SCHEMA_HISTORY = """
CREATE TABLE IF NOT EXISTS findings_state_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_hash    TEXT NOT NULL,
    from_state      TEXT,
    to_state        TEXT NOT NULL,
    actor           TEXT NOT NULL,
    note            TEXT,
    changed_at      TEXT NOT NULL,
    FOREIGN KEY(finding_hash) REFERENCES findings(finding_hash)
);
CREATE INDEX IF NOT EXISTS idx_findings_state_history_hash
    ON findings_state_history(finding_hash);
"""


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


_V4_SCHEMA = """
CREATE TABLE IF NOT EXISTS benchmark_disclosures (
    report_url          TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    severity            TEXT NOT NULL,
    disclosed_date      TEXT NOT NULL,
    bounty_usd          INTEGER,
    asset_pattern       TEXT NOT NULL,
    vuln_class          TEXT NOT NULL,
    vector_summary      TEXT NOT NULL,
    auto_detectable_hint TEXT NOT NULL,
    ingested_at         TEXT NOT NULL,
    verdict             TEXT,
    verdict_reason      TEXT,
    verdict_set_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_benchmark_disclosures_vuln_class
    ON benchmark_disclosures(vuln_class);
CREATE INDEX IF NOT EXISTS idx_benchmark_disclosures_verdict
    ON benchmark_disclosures(verdict);
"""


def _apply_v4(conn: sqlite3.Connection) -> None:
    """Add benchmark_disclosures table for the disclosure-replay benchmark."""
    _execute_script(conn, _V4_SCHEMA)


_V5_BENCHMARK_DISCLOSURE_COLUMNS: tuple[tuple[str, str], ...] = (
    # Provenance — replicated per row, denormalised for Phase A.
    ("corpus_source",         "TEXT NOT NULL DEFAULT ''"),
    ("corpus_generated_at",   "TEXT NOT NULL DEFAULT ''"),
    ("in_window_range",       "TEXT NOT NULL DEFAULT ''"),
    ("date_precision_note",   "TEXT"),
    # Reserved for Phase B scoring — captures which rubric version set the
    # verdict, so a map evolution doesn't silently invalidate old verdicts.
    ("scoring_rubric_version", "TEXT"),
)


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


_V6_BENCHMARK_DISCLOSURE_COLUMNS: tuple[tuple[str, str], ...] = (
    # Phase B preparation per docs/superpowers/specs/2026-05-15-benchmark-disclosures.md:
    # in_window_eligible defaults to 1 for fresh inserts; pre-v6 rows on the 3
    # already-onboarded programs need a re-ingest to backfill correctly. See
    # the spec's "Backfill procedure for v6" section.
    ("in_window_eligible", "INTEGER NOT NULL DEFAULT 1"),
    # Verdict provenance: 'scorer' = written by the scoring engine,
    # 'operator' = manual override. NULL when verdict is NULL.
    ("verdict_source",     "TEXT"),
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


_STEPS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _apply_v1,
    2: _apply_v2,
    3: _apply_v3,
    4: _apply_v4,
    5: _apply_v5,
    6: _apply_v6,
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
