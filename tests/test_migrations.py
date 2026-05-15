"""Tests for the versioned schema migration runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import migrations


def test_fresh_db_migrates_to_target_version(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "fresh.sqlite")
    migrations.migrate(conn, target_version=2)
    assert _user_version(conn) == 2
    assert _tables(conn) == {
        "assets", "findings", "recon_runs", "http_services", "signals",
    }


def _user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    }


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "idempotent.sqlite"
    conn = sqlite3.connect(db)
    migrations.migrate(conn, target_version=2)
    migrations.migrate(conn, target_version=2)
    assert _user_version(conn) == 2


def test_migrates_phase_2_db_preserving_data(tmp_path: Path) -> None:
    db = tmp_path / "phase2.sqlite"
    conn = sqlite3.connect(db)
    # Simulate the Phase 2 schema-on-startup behaviour.
    migrations.migrate(conn, target_version=1)
    conn.execute(
        "INSERT INTO assets (subdomain, ip, first_seen, last_seen, "
        "in_scope_at_observation) VALUES (?, ?, ?, ?, 1)",
        ("api.example.com", "1.2.3.4", "2026-05-01", "2026-05-12"),
    )
    conn.commit()

    migrations.migrate(conn, target_version=2)

    assert _user_version(conn) == 2
    rows = conn.execute("SELECT subdomain, ip FROM assets").fetchall()
    assert rows == [("api.example.com", "1.2.3.4")]
    assert _tables(conn) >= {
        "assets", "findings", "recon_runs", "http_services", "signals"
    }


def test_failed_step_rolls_back_user_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a step raises mid-DDL, user_version stays at the prior version
    and partially-applied tables are rolled back."""
    db_path = tmp_path / "rollback.sqlite"
    conn = sqlite3.connect(db_path)
    migrations.migrate(conn, target_version=1)
    assert _user_version(conn) == 1

    # Monkeypatch _STEPS[2] to start writing tables, then fail mid-way.
    # (patching _apply_v2 alone wouldn't work because _STEPS holds a direct
    # reference; patching the dict entry is the correct hook point.)
    def broken_v2(c: sqlite3.Connection) -> None:
        c.execute("CREATE TABLE recon_runs (run_id TEXT)")
        raise RuntimeError("simulated mid-step failure")

    monkeypatch.setitem(migrations._STEPS, 2, broken_v2)

    with pytest.raises(RuntimeError, match="simulated"):
        migrations.migrate(conn, target_version=2)

    # user_version must still be 1, and recon_runs must NOT exist.
    assert _user_version(conn) == 1
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%'"
    )}
    assert "recon_runs" not in tables


def test_fresh_db_migrates_to_v3(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "fresh_v3.sqlite")
    migrations.migrate(conn, target_version=3)
    assert _user_version(conn) == 3
    # New tables exist.
    assert _tables(conn) >= {
        "assets", "findings", "recon_runs", "http_services", "signals",
        "findings_state_history",
    }
    # Expanded findings columns present.
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(findings)")
    }
    assert columns >= {
        "finding_hash", "platform", "slug", "vuln_class", "asset", "target",
        "signature", "title", "severity_hint", "confidence",
        "source_tool", "source_run_id", "evidence_path", "notes_path",
        "first_seen", "last_seen", "occurrence_count",
        "current_state", "state_changed_at",
        "external_report_id", "payout_amount", "payout_currency",
    }


def test_v3_migration_is_idempotent(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "idem_v3.sqlite")
    migrations.migrate(conn, target_version=3)
    migrations.migrate(conn, target_version=3)
    assert _user_version(conn) == 3


def test_fresh_db_migrates_to_v4(tmp_path: Path) -> None:
    """v4 adds benchmark_disclosures table with verdict columns."""
    conn = sqlite3.connect(tmp_path / "fresh_v4.sqlite")
    migrations.migrate(conn, target_version=4)
    assert _user_version(conn) == 4
    assert "benchmark_disclosures" in _tables(conn)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(benchmark_disclosures)")
    }
    assert columns >= {
        "report_url", "title", "severity", "disclosed_date", "bounty_usd",
        "asset_pattern", "vuln_class", "vector_summary",
        "auto_detectable_hint", "ingested_at",
        "verdict", "verdict_reason", "verdict_set_at",
    }


def test_v4_migration_is_idempotent(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "idem_v4.sqlite")
    migrations.migrate(conn, target_version=4)
    migrations.migrate(conn, target_version=4)
    assert _user_version(conn) == 4


def test_fresh_db_migrates_to_v5(tmp_path: Path) -> None:
    """v5 adds provenance + scoring_rubric_version columns."""
    conn = sqlite3.connect(tmp_path / "fresh_v5.sqlite")
    migrations.migrate(conn, target_version=5)
    assert _user_version(conn) == 5
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(benchmark_disclosures)")
    }
    assert columns >= {
        "corpus_source", "corpus_generated_at", "in_window_range",
        "date_precision_note", "scoring_rubric_version",
    }


def test_fresh_db_migrates_to_v6(tmp_path: Path) -> None:
    """v6 adds eligibility + verdict_source columns."""
    conn = sqlite3.connect(tmp_path / "fresh_v6.sqlite")
    migrations.migrate(conn, target_version=6)
    assert _user_version(conn) == 6
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(benchmark_disclosures)")
    }
    assert columns >= {"in_window_eligible", "verdict_source"}


def test_v6_migration_is_idempotent(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "idem_v6.sqlite")
    migrations.migrate(conn, target_version=6)
    migrations.migrate(conn, target_version=6)
    assert _user_version(conn) == 6


def test_v5_to_v6_defaults_existing_rows_eligible(tmp_path: Path) -> None:
    """Existing v5 rows must default to in_window_eligible=1 after v5→v6.
    Re-ingest then backfills correctly per the spec's deployment procedure."""
    conn = sqlite3.connect(tmp_path / "v5_to_v6.sqlite")
    migrations.migrate(conn, target_version=5)
    conn.execute(
        "INSERT INTO benchmark_disclosures "
        "(report_url, title, severity, disclosed_date, bounty_usd, "
        " asset_pattern, vuln_class, vector_summary, auto_detectable_hint, "
        " ingested_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("https://h1.com/reports/anchor", "anchor", "low", "2020", None,
         "*.example.com", "Info-Disclosure", "v", "regex-friendly",
         "2026-05-15T09:00:00Z"),
    )
    conn.commit()

    migrations.migrate(conn, target_version=6)

    row = conn.execute(
        "SELECT in_window_eligible, verdict_source FROM benchmark_disclosures "
        "WHERE report_url = ?",
        ("https://h1.com/reports/anchor",),
    ).fetchone()
    assert row == (1, None)


def test_v4_to_v5_preserves_existing_rows(tmp_path: Path) -> None:
    """An existing v4 benchmark_disclosures row must survive v5 with sensible
    defaults for the new provenance columns."""
    conn = sqlite3.connect(tmp_path / "v4_to_v5.sqlite")
    migrations.migrate(conn, target_version=4)
    conn.execute(
        "INSERT INTO benchmark_disclosures "
        "(report_url, title, severity, disclosed_date, bounty_usd, "
        " asset_pattern, vuln_class, vector_summary, auto_detectable_hint, "
        " ingested_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("https://h1.com/reports/9", "T", "high", "2024-01", 100,
         "*.example.com", "IDOR", "v", "requires-auth",
         "2026-05-15T09:00:00Z"),
    )
    conn.commit()

    migrations.migrate(conn, target_version=5)

    row = conn.execute(
        "SELECT report_url, corpus_source, corpus_generated_at, "
        "in_window_range, date_precision_note, scoring_rubric_version "
        "FROM benchmark_disclosures WHERE report_url = ?",
        ("https://h1.com/reports/9",),
    ).fetchone()
    assert row == (
        "https://h1.com/reports/9", "", "", "", None, None,
    )


def test_v2_to_v3_backfills_legacy_findings(tmp_path: Path) -> None:
    """An existing v2 row in findings (created via the legacy 6-column shape)
    must survive v3 with sensible default values for the new columns."""
    conn = sqlite3.connect(tmp_path / "legacy.sqlite")
    migrations.migrate(conn, target_version=2)
    conn.execute(
        "INSERT INTO findings "
        "(finding_hash, vuln_class, target, first_seen, current_state, notes_path) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("h1", "xss-reflected", "https://api.example.com/?q=",
         "2026-05-10T10:00:00Z", "queued", "findings/_queue/h1.md"),
    )
    conn.commit()

    migrations.migrate(conn, target_version=3)

    row = conn.execute(
        "SELECT platform, slug, severity_hint, confidence, source_tool, "
        "source_run_id, evidence_path, last_seen, occurrence_count, "
        "state_changed_at FROM findings WHERE finding_hash = 'h1'"
    ).fetchone()
    assert row == (
        "__legacy__", "__legacy__", "unknown", 0, "legacy", "", "",
        "2026-05-10T10:00:00Z", 1, "2026-05-10T10:00:00Z",
    )
