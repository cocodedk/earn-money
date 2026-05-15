"""Per-program SQLite store. Schema is versioned via earn_money.migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import migrations

CURRENT_SCHEMA_VERSION = 5


def open_db(path: Path) -> sqlite3.Connection:
    """Open (or create) a per-program SQLite database and bring its schema
    to ``CURRENT_SCHEMA_VERSION``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    migrations.migrate(conn, target_version=CURRENT_SCHEMA_VERSION)
    return conn
