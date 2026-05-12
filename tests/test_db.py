from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db


def test_open_creates_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = db.open_db(db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cur.fetchall()]
    assert tables == ["assets", "findings"]
    conn.close()


def test_assets_table_columns(tmp_path: Path) -> None:
    conn = db.open_db(tmp_path / "test.sqlite")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(assets)").fetchall()}
    assert cols == {
        "subdomain",
        "ip",
        "ports",
        "fingerprint",
        "first_seen",
        "last_seen",
        "in_scope_at_observation",
    }
    conn.close()


def test_findings_table_columns(tmp_path: Path) -> None:
    conn = db.open_db(tmp_path / "test.sqlite")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(findings)").fetchall()}
    assert cols == {
        "finding_hash",
        "vuln_class",
        "target",
        "first_seen",
        "current_state",
        "notes_path",
    }
    conn.close()


def test_finding_hash_is_primary_key(tmp_path: Path) -> None:
    conn = db.open_db(tmp_path / "test.sqlite")
    insert_sql = (
        "INSERT INTO findings"
        " (finding_hash, vuln_class, target, first_seen, current_state, notes_path)"
        " VALUES (?, ?, ?, ?, ?, ?)"
    )
    row = (
        "abc123",
        "idor",
        "https://example.com/api",
        "2026-05-12T08:00:00Z",
        "queued",
        "findings/_queue/x.md",
    )
    conn.execute(insert_sql, row)
    try:
        conn.execute(insert_sql, row)
        raise AssertionError("expected IntegrityError on duplicate finding_hash")
    except sqlite3.IntegrityError:
        pass
    conn.close()
