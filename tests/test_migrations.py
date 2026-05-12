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
