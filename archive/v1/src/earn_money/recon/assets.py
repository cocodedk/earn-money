"""Asset upsert into the per-program SQLite assets table."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetObservation:
    subdomain: str
    ips: tuple[str, ...]


@dataclass(frozen=True)
class UpsertSummary:
    inserted: int
    updated: int


def upsert_assets(
    conn: sqlite3.Connection,
    observations: list[AssetObservation],
    *,
    observed_at: str,
    in_scope: bool,
) -> UpsertSummary:
    """Insert new assets, update last_seen and ip on known ones.

    Returns counts of inserted and updated rows. ``ips`` is stored as a
    comma-joined string in the ``ip`` column for grep-ability.
    """
    inserted = 0
    updated = 0
    flag = 1 if in_scope else 0

    for obs in observations:
        ip_str = ",".join(obs.ips)
        cursor = conn.execute(
            "SELECT subdomain FROM assets WHERE subdomain = ?",
            (obs.subdomain,),
        )
        if cursor.fetchone() is None:
            conn.execute(
                "INSERT INTO assets "
                "(subdomain, ip, ports, fingerprint, "
                "first_seen, last_seen, in_scope_at_observation) "
                "VALUES (?, ?, NULL, NULL, ?, ?, ?)",
                (obs.subdomain, ip_str, observed_at, observed_at, flag),
            )
            inserted += 1
        else:
            conn.execute(
                "UPDATE assets SET ip = ?, last_seen = ?, in_scope_at_observation = ? "
                "WHERE subdomain = ?",
                (ip_str, observed_at, flag, obs.subdomain),
            )
            updated += 1

    conn.commit()
    return UpsertSummary(inserted=inserted, updated=updated)
