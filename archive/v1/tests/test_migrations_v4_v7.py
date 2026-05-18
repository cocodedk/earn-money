"""Tests for schema migrations v4-v7."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import migrations


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
