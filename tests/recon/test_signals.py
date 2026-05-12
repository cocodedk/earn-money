from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import signals


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def test_insert_signals_persists_rows(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    entries = [
        signals.Signal(
            run_id="r1", tool="httpx", signal_type="new_service",
            asset="api.example.com", target="https://api.example.com/",
            signature="https|443|200", payload='{"server":"nginx"}',
            observed_at="t",
        ),
        signals.Signal(
            run_id="r1", tool="httpx", signal_type="fingerprint_drift",
            asset="www.example.com", target="https://www.example.com/",
            signature="drift|abc123|def456", payload="{}",
            observed_at="t",
        ),
    ]
    signals.insert_signals(conn, entries)

    rows = conn.execute(
        "SELECT signal_type, asset FROM signals ORDER BY signal_type"
    ).fetchall()
    assert rows == [
        ("fingerprint_drift", "www.example.com"),
        ("new_service", "api.example.com"),
    ]


def test_insert_signals_dedups_on_unique_key(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    entry = signals.Signal(
        run_id="r1", tool="httpx", signal_type="new_service",
        asset="api.example.com", target="https://api.example.com/",
        signature="sig", payload="{}", observed_at="t",
    )
    signals.insert_signals(conn, [entry, entry])
    count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    assert count == 1
