"""SQL schema string constants and the script-execution helper for migrations.

Extracted from migrations.py so that migrations.py stays under 200 lines.
Each _VN_* constant is the raw SQL applied by the corresponding _apply_vN
function in migrations.py.
"""

from __future__ import annotations

import sqlite3

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

_V7_SCHEMA = """
CREATE TABLE IF NOT EXISTS juice_shop_scores (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id    TEXT NOT NULL,
    snapshot_type  TEXT NOT NULL,
    snapshot_time  TEXT NOT NULL,
    challenge_id   INTEGER NOT NULL,
    challenge_name TEXT NOT NULL,
    category       TEXT NOT NULL,
    difficulty     INTEGER NOT NULL,
    solved         INTEGER NOT NULL DEFAULT 0
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
