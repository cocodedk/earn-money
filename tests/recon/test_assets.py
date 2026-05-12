from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import assets


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def test_upsert_inserts_new_assets(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    summary = assets.upsert_assets(
        conn,
        [
            assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"]),
            assets.AssetObservation(subdomain="www.example.com", ips=["5.6.7.8"]),
        ],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    assert summary.inserted == 2
    assert summary.updated == 0
    rows = conn.execute(
        "SELECT subdomain, ip, first_seen, last_seen, in_scope_at_observation "
        "FROM assets ORDER BY subdomain"
    ).fetchall()
    assert rows == [
        ("api.example.com", "1.2.3.4", "2026-05-12T08:00:00Z", "2026-05-12T08:00:00Z", 1),
        ("www.example.com", "5.6.7.8", "2026-05-12T08:00:00Z", "2026-05-12T08:00:00Z", 1),
    ]
    conn.close()


def test_upsert_updates_last_seen_for_known_assets(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    summary = assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"])],
        observed_at="2026-05-13T08:00:00Z",
        in_scope=True,
    )
    assert summary.inserted == 0
    assert summary.updated == 1
    (first_seen, last_seen) = conn.execute(
        "SELECT first_seen, last_seen FROM assets WHERE subdomain='api.example.com'"
    ).fetchone()
    assert first_seen == "2026-05-12T08:00:00Z"
    assert last_seen == "2026-05-13T08:00:00Z"
    conn.close()


def test_upsert_updates_ip_when_changed(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["9.9.9.9"])],
        observed_at="2026-05-13T08:00:00Z",
        in_scope=True,
    )
    (ip,) = conn.execute(
        "SELECT ip FROM assets WHERE subdomain='api.example.com'"
    ).fetchone()
    assert ip == "9.9.9.9"
    conn.close()


def test_upsert_records_in_scope_flag(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="oos.example.com", ips=["1.1.1.1"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=False,
    )
    (flag,) = conn.execute(
        "SELECT in_scope_at_observation FROM assets WHERE subdomain='oos.example.com'"
    ).fetchone()
    assert flag == 0
    conn.close()


def test_upsert_handles_empty_input(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    summary = assets.upsert_assets(conn, [], observed_at="2026-05-12T08:00:00Z", in_scope=True)
    assert summary.inserted == 0
    assert summary.updated == 0
    conn.close()


def test_upsert_joins_multiple_ips_with_comma(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.1.1.1", "2.2.2.2"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    (ip,) = conn.execute(
        "SELECT ip FROM assets WHERE subdomain='api.example.com'"
    ).fetchone()
    assert ip == "1.1.1.1,2.2.2.2"
    conn.close()
