# Phase 3a — Active Runner Foundation + httpx Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the shared active-recon foundation (per-request scope enforcement, batch wrapper, kill-switch watchdog, failure taxonomy, v1→v2 schema migration) plus the first active runner — `httpx` — and an end-to-end mock-target integration smoke.

**Architecture:** Mirrors the Phase 2 passive-recon runner shape: `run_program(paths, platform, slug, *, tool_run=...) -> ActiveRunResult`, gate-checked (kill-switch → freeze → scope → policy), source-resilient. Three new modules introduce the shared active-runner discipline (`runners.active`, `runners.watchdog`, `runners.batch`), one tool wrapper (`recon.httpx_tool`), one runner (`runners.httpx_probe`), one CLI (`bin/httpx-probe`). Per-program SQLite gains `recon_runs`, `http_services`, and `signals` tables via a new migration framework.

**Tech Stack:** Python 3.12+, `sqlite3` (stdlib), `threading` (watchdog), `subprocess` (httpx invocation), `pytest` (testing), `mypy --strict`, `ruff`. The `httpx` CLI from ProjectDiscovery is shelled out — not the Python httpx HTTP client library, which is used elsewhere in this repo and is unrelated.

**Spec reference:** [`docs/superpowers/specs/2026-05-12-phase-3-design.md`](../specs/2026-05-12-phase-3-design.md) — Phase 3a-specific sections: 3 (Shared Active Runner Contract + Shared Artifact Contract + 3.1 httpx), 4 (schema migration + recon_runs + http_services + signals + finding-hash normalization), 5 (cron / systemd timer for httpx-probe).

---

## File map

**Create:**
- `src/earn_money/runners/active.py` — shared active-runner contract, `ActiveRunResult` dataclass, gate-check helper, failure taxonomy enums
- `src/earn_money/runners/watchdog.py` — `KillSwitchWatchdog` thread that polls `RECON_ENABLED` + `FROZEN` every 5s and triggers a kill callback on state change
- `src/earn_money/runners/batch.py` — `run_batches()` helper that splits a target list into bounded subprocess invocations under watchdog supervision
- `src/earn_money/runners/httpx_probe.py` — the `httpx-probe` runner with `run_program()` and `main()` entry points
- `src/earn_money/recon/httpx_tool.py` — thin subprocess wrapper around the `httpx` CLI; parses JSONL output
- `src/earn_money/recon/runs.py` — `recon_runs` DAO: `start_run`, `finish_run`, `list_untriaged`
- `src/earn_money/recon/services.py` — `http_services` DAO: `upsert_service`, `services_for_program`
- `src/earn_money/recon/signals.py` — `signals` DAO: `insert_signals`, `signals_for_run`
- `src/earn_money/migrations.py` — `migrate(conn, target_version)` + numbered migration steps
- `bin/httpx-probe` — shell wrapper for the runner (mirrors `bin/passive-recon`)
- `tests/fixtures/mock_target/server.py` — tiny stdlib HTTP server for integration tests
- `tests/fixtures/mock_target/conftest.py` — pytest fixture that starts/stops the mock server
- `tests/test_migrations.py` — migration unit + integration tests
- `tests/recon/test_runs.py`, `test_services.py`, `test_signals.py` — DAO tests
- `tests/runners/test_active.py` — active-contract tests (gate checks, failure taxonomy)
- `tests/runners/test_watchdog.py` — watchdog tests against a fake state-source
- `tests/runners/test_batch.py` — batch runner tests against a fake subprocess
- `tests/recon/test_httpx_tool.py` — tool-wrapper tests against fixture JSONL
- `tests/runners/test_httpx_probe.py` — runner unit tests with mocked tool
- `tests/runners/test_httpx_probe_e2e.py` — end-to-end integration against the mock target

**Modify:**
- `src/earn_money/db.py` — `open_db()` now calls `migrations.migrate(conn, target_version=2)` instead of running raw SCHEMA
- `src/earn_money/config.py` — add `paths.recon_outputs_dir(platform, slug, tool, date, run_id)` helper (if a similar helper isn't already present)
- `pyproject.toml` — bump the project description / add no new deps

**Touch only when justified:** anything else. Per the project's "Surgical changes" rule, every changed line must trace back to a 3a requirement.

---

## Task 1: Schema migration framework + v1→v2

Replaces `db.py`'s raw `executescript(SCHEMA)` with a versioned migration runner. Phase 2's existing schema becomes v1. Phase 3a adds v2.

**Files:**
- Create: `src/earn_money/migrations.py`
- Create: `tests/test_migrations.py`
- Modify: `src/earn_money/db.py` (replace SCHEMA + open_db body)

- [ ] **Step 1: Write the first failing test (fresh DB lands at v2)**

```python
# tests/test_migrations.py
from __future__ import annotations

import sqlite3
from pathlib import Path

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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_migrations.py::test_fresh_db_migrates_to_target_version -v
```

Expected: `ModuleNotFoundError: No module named 'earn_money.migrations'`.

- [ ] **Step 3: Write the minimal migrations module**

```python
# src/earn_money/migrations.py
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


def _apply_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(_V1_SCHEMA)


def _apply_v2(conn: sqlite3.Connection) -> None:
    conn.executescript(_V2_SCHEMA)


_STEPS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _apply_v1,
    2: _apply_v2,
}


def migrate(conn: sqlite3.Connection, *, target_version: int) -> None:
    """Bring ``conn`` up to ``target_version`` by running each pending step
    inside its own transaction. Idempotent: a DB already at or above the
    target is unchanged. A failing step leaves user_version at the prior
    successful step."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in sorted(_STEPS):
        if version <= current:
            continue
        if version > target_version:
            break
        with conn:  # auto-commit / rollback on exception
            _STEPS[version](conn)
            conn.execute(f"PRAGMA user_version = {version}")
```

- [ ] **Step 4: Run the test to verify GREEN**

```bash
.venv/bin/python -m pytest tests/test_migrations.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Add idempotency test**

```python
# tests/test_migrations.py — append
def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "idempotent.sqlite"
    conn = sqlite3.connect(db)
    migrations.migrate(conn, target_version=2)
    migrations.migrate(conn, target_version=2)
    assert _user_version(conn) == 2
```

Run: `.venv/bin/python -m pytest tests/test_migrations.py -v` → PASS.

- [ ] **Step 6: Add Phase-2-DB upgrade test**

```python
# tests/test_migrations.py — append
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
    assert _tables(conn) >= {"assets", "findings", "recon_runs", "http_services", "signals"}
```

Run: PASS.

- [ ] **Step 7: Wire `db.open_db` to use migrations**

```python
# src/earn_money/db.py — replace SCHEMA + open_db body
"""Per-program SQLite store. Schema is versioned via earn_money.migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import migrations

CURRENT_SCHEMA_VERSION = 2


def open_db(path: Path) -> sqlite3.Connection:
    """Open (or create) a per-program SQLite database and bring its schema
    to ``CURRENT_SCHEMA_VERSION``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    migrations.migrate(conn, target_version=CURRENT_SCHEMA_VERSION)
    return conn
```

- [ ] **Step 8: Run the full test suite + lint**

```bash
make lint
.venv/bin/python -m pytest -v 2>&1 | tail -10
```

Expected: ruff + mypy clean, all 76+ existing tests still passing, 3 new migration tests passing.

- [ ] **Step 9: Commit**

```bash
git add src/earn_money/migrations.py src/earn_money/db.py tests/test_migrations.py
git commit -m "feat: schema migration framework v0→v2 with new recon tables"
```

---

## Task 2: `recon_runs` DAO

Wraps `recon_runs` inserts/updates behind a small typed API. Every active runner uses it.

**Files:**
- Create: `src/earn_money/recon/runs.py`
- Create: `tests/recon/test_runs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/recon/test_runs.py
from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import runs


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def test_start_run_inserts_in_progress_row(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    runs.start_run(
        conn,
        run_id="r1",
        platform="hackerone",
        slug="example",
        tool="httpx",
        started_at="2026-05-12T08:00:00Z",
        artifact_dir="recon/outputs/hackerone/example/httpx/2026-05-12/r1",
        input_count=10,
    )
    row = conn.execute(
        "SELECT status, finished_at, input_count FROM recon_runs WHERE run_id = ?",
        ("r1",),
    ).fetchone()
    assert row == ("in_progress", None, 10)


def test_finish_run_updates_status_and_counters(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    runs.start_run(
        conn, run_id="r2", platform="hackerone", slug="example",
        tool="httpx", started_at="2026-05-12T08:00:00Z",
        artifact_dir="d", input_count=10,
    )
    runs.finish_run(
        conn, run_id="r2", finished_at="2026-05-12T08:05:00Z",
        status="success", output_count=8, signal_count=2,
        source_failures=0, oos_drops=1,
    )
    row = conn.execute(
        "SELECT status, finished_at, output_count, signal_count, "
        "source_failures, oos_drops FROM recon_runs WHERE run_id = ?",
        ("r2",),
    ).fetchone()
    assert row == ("success", "2026-05-12T08:05:00Z", 8, 2, 0, 1)


def test_list_untriaged_returns_finished_runs_only(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    runs.start_run(
        conn, run_id="a", platform="p", slug="s", tool="httpx",
        started_at="t", artifact_dir="d", input_count=0,
    )
    runs.start_run(
        conn, run_id="b", platform="p", slug="s", tool="httpx",
        started_at="t", artifact_dir="d", input_count=0,
    )
    runs.finish_run(
        conn, run_id="b", finished_at="t", status="success",
        output_count=0, signal_count=0, source_failures=0, oos_drops=0,
    )
    untriaged = [r.run_id for r in runs.list_untriaged(conn, platform="p", slug="s")]
    assert untriaged == ["b"]
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/recon/test_runs.py -v
```

Expected: `ModuleNotFoundError: No module named 'earn_money.recon.runs'`.

- [ ] **Step 3: Implement the DAO**

```python
# src/earn_money/recon/runs.py
"""DAO for the recon_runs table."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ReconRun:
    run_id: str
    platform: str
    slug: str
    tool: str
    started_at: str
    finished_at: str | None
    status: str
    artifact_dir: str
    input_count: int
    output_count: int
    signal_count: int
    source_failures: int
    oos_drops: int
    terminated_reason: str | None


def start_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    platform: str,
    slug: str,
    tool: str,
    started_at: str,
    artifact_dir: str,
    input_count: int,
) -> None:
    conn.execute(
        "INSERT INTO recon_runs (run_id, platform, slug, tool, started_at, "
        "status, artifact_dir, input_count) "
        "VALUES (?, ?, ?, ?, ?, 'in_progress', ?, ?)",
        (run_id, platform, slug, tool, started_at, artifact_dir, input_count),
    )
    conn.commit()


def finish_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    finished_at: str,
    status: str,
    output_count: int,
    signal_count: int,
    source_failures: int,
    oos_drops: int,
    terminated_reason: str | None = None,
    error_summary: str | None = None,
) -> None:
    conn.execute(
        "UPDATE recon_runs SET finished_at = ?, status = ?, "
        "output_count = ?, signal_count = ?, source_failures = ?, "
        "oos_drops = ?, terminated_reason = ?, error_summary = ? "
        "WHERE run_id = ?",
        (finished_at, status, output_count, signal_count,
         source_failures, oos_drops, terminated_reason, error_summary, run_id),
    )
    conn.commit()


def list_untriaged(
    conn: sqlite3.Connection, *, platform: str, slug: str
) -> list[ReconRun]:
    cursor = conn.execute(
        "SELECT run_id, platform, slug, tool, started_at, finished_at, "
        "status, artifact_dir, input_count, output_count, signal_count, "
        "source_failures, oos_drops, terminated_reason "
        "FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND finished_at IS NOT NULL AND triaged_at IS NULL "
        "ORDER BY started_at",
        (platform, slug),
    )
    return [ReconRun(*row) for row in cursor]
```

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/recon/test_runs.py -v
make lint
```

Expected: 3 passed; lint clean.

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/recon/runs.py tests/recon/test_runs.py
git commit -m "feat: recon_runs DAO with start/finish/list_untriaged"
```

---

## Task 3: `http_services` DAO

Normalized service inventory keyed by `(subdomain, scheme, port)`. Read by every later active runner.

**Files:**
- Create: `src/earn_money/recon/services.py`
- Create: `tests/recon/test_services.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/recon/test_services.py
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import services


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def test_upsert_inserts_first_observation(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    obs = services.HttpService(
        subdomain="api.example.com", scheme="https", port=443,
        url="https://api.example.com/", status_code=200,
        title="Example API", server="nginx",
        technologies=("nginx", "openresty"),
        redirect_to=None, tls_summary='{"issuer":"LE"}',
        observed_at="2026-05-12T08:00:00Z", last_run_id="r1",
        in_scope_at_observation=True,
    )
    services.upsert_service(conn, obs)
    row = conn.execute(
        "SELECT subdomain, scheme, port, status_code, technologies "
        "FROM http_services"
    ).fetchone()
    assert row[:4] == ("api.example.com", "https", 443, 200)
    assert json.loads(row[4]) == ["nginx", "openresty"]


def test_upsert_replaces_existing_row_for_same_key(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    first = services.HttpService(
        subdomain="api.example.com", scheme="https", port=443,
        url="https://api.example.com/", status_code=200, title=None,
        server="nginx", technologies=(),
        redirect_to=None, tls_summary=None,
        observed_at="2026-05-12T08:00:00Z", last_run_id="r1",
        in_scope_at_observation=True,
    )
    services.upsert_service(conn, first)
    second = services.HttpService(
        **{**first.__dict__, "status_code": 503, "last_run_id": "r2",
           "observed_at": "2026-05-12T14:00:00Z"},
    )
    services.upsert_service(conn, second)
    rows = conn.execute(
        "SELECT status_code, last_run_id FROM http_services"
    ).fetchall()
    assert rows == [(503, "r2")]


def test_services_for_program_filters_by_subdomain(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    # Insert two subdomains; the test asks for one.
    for sd in ("api.example.com", "www.example.com"):
        services.upsert_service(conn, services.HttpService(
            subdomain=sd, scheme="https", port=443, url=f"https://{sd}/",
            status_code=200, title=None, server=None, technologies=(),
            redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="r", in_scope_at_observation=True,
        ))
    rows = services.services_for_subdomains(conn, ["api.example.com"])
    assert [s.subdomain for s in rows] == ["api.example.com"]
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/recon/test_services.py -v
```

Expected: `ModuleNotFoundError: ... services`.

- [ ] **Step 3: Implement the DAO**

```python
# src/earn_money/recon/services.py
"""DAO for the http_services table — the canonical HTTP service inventory."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class HttpService:
    subdomain: str
    scheme: str
    port: int
    url: str
    status_code: int | None
    title: str | None
    server: str | None
    technologies: tuple[str, ...]
    redirect_to: str | None
    tls_summary: str | None
    observed_at: str
    last_run_id: str
    in_scope_at_observation: bool


def upsert_service(conn: sqlite3.Connection, s: HttpService) -> None:
    """Replace the row for ``(subdomain, scheme, port)`` with ``s``."""
    conn.execute(
        "INSERT INTO http_services "
        "(subdomain, scheme, port, url, status_code, title, server, "
        " technologies, redirect_to, tls_summary, observed_at, last_run_id, "
        " in_scope_at_observation) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(subdomain, scheme, port) DO UPDATE SET "
        "url=excluded.url, status_code=excluded.status_code, "
        "title=excluded.title, server=excluded.server, "
        "technologies=excluded.technologies, redirect_to=excluded.redirect_to, "
        "tls_summary=excluded.tls_summary, observed_at=excluded.observed_at, "
        "last_run_id=excluded.last_run_id, "
        "in_scope_at_observation=excluded.in_scope_at_observation",
        (
            s.subdomain, s.scheme, s.port, s.url, s.status_code,
            s.title, s.server, json.dumps(list(s.technologies)),
            s.redirect_to, s.tls_summary, s.observed_at, s.last_run_id,
            1 if s.in_scope_at_observation else 0,
        ),
    )
    conn.commit()


def services_for_subdomains(
    conn: sqlite3.Connection, subdomains: Iterable[str]
) -> list[HttpService]:
    """Return all `http_services` rows for the given subdomains, in stable order."""
    sd_list = list(subdomains)
    if not sd_list:
        return []
    placeholders = ",".join("?" * len(sd_list))
    cursor = conn.execute(
        "SELECT subdomain, scheme, port, url, status_code, title, server, "
        "technologies, redirect_to, tls_summary, observed_at, last_run_id, "
        "in_scope_at_observation "
        f"FROM http_services WHERE subdomain IN ({placeholders}) "
        "ORDER BY subdomain, scheme, port",
        sd_list,
    )
    return [_row_to_service(row) for row in cursor]


def _row_to_service(row: tuple) -> HttpService:
    return HttpService(
        subdomain=row[0], scheme=row[1], port=row[2], url=row[3],
        status_code=row[4], title=row[5], server=row[6],
        technologies=tuple(json.loads(row[7])),
        redirect_to=row[8], tls_summary=row[9],
        observed_at=row[10], last_run_id=row[11],
        in_scope_at_observation=bool(row[12]),
    )
```

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/recon/test_services.py -v
make lint
```

Expected: 3 passed; lint clean.

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/recon/services.py tests/recon/test_services.py
git commit -m "feat: http_services DAO with upsert and per-subdomain query"
```

---

## Task 4: `signals` DAO

Stores normalized weak signals from every active runner. Read by the triage engine in 3b. Tiny DAO; the schema is the load-bearing part.

**Files:**
- Create: `src/earn_money/recon/signals.py`
- Create: `tests/recon/test_signals.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/recon/test_signals.py
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
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/recon/test_signals.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the DAO**

```python
# src/earn_money/recon/signals.py
"""DAO for the signals table — durable weak-signal index used by triage."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    run_id: str
    tool: str
    signal_type: str
    asset: str
    target: str
    signature: str
    payload: str
    observed_at: str


def insert_signals(conn: sqlite3.Connection, entries: Iterable[Signal]) -> int:
    """Insert each signal; silently skip rows that collide on the unique key.
    Returns the count of rows actually inserted."""
    rows = [
        (s.run_id, s.tool, s.signal_type, s.asset, s.target,
         s.signature, s.payload, s.observed_at)
        for s in entries
    ]
    if not rows:
        return 0
    cursor = conn.executemany(
        "INSERT OR IGNORE INTO signals "
        "(run_id, tool, signal_type, asset, target, signature, payload, observed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return cursor.rowcount


def signals_for_run(conn: sqlite3.Connection, run_id: str) -> list[Signal]:
    cursor = conn.execute(
        "SELECT run_id, tool, signal_type, asset, target, signature, "
        "payload, observed_at FROM signals WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    return [Signal(*row) for row in cursor]
```

- [ ] **Step 4: Verify GREEN + lint**

```bash
.venv/bin/python -m pytest tests/recon/test_signals.py -v
make lint
```

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/recon/signals.py tests/recon/test_signals.py
git commit -m "feat: signals DAO with idempotent insert and per-run lookup"
```

---

## Task 5: Active-runner contract

Shared dataclass + gate-check helper + failure taxonomy. Used by every active runner that lands after this point.

**Files:**
- Create: `src/earn_money/runners/active.py`
- Create: `tests/runners/test_active.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_active.py
from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, flags, policy, scope
from earn_money.runners import active


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def test_check_gates_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    with pytest.raises(flags.ReconDisabled):
        active.check_gates(paths, "hackerone", "example", mode="active")


def test_check_gates_refuses_manual_only_policy(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only")
    with pytest.raises(policy.PolicyViolation):
        active.check_gates(paths, "hackerone", "example", mode="active")


def test_check_gates_returns_scope_on_success(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    s = active.check_gates(paths, "hackerone", "example", mode="active")
    assert s.policy == "rate-limited-OK"
    assert s.in_scope == ["*.example.com"]


def test_run_result_defaults_are_zero() -> None:
    r = active.ActiveRunResult(run_id="r")
    assert r.targets_considered == 0
    assert r.targets_scanned == 0
    assert r.artifacts_written == 0
    assert r.outputs_recorded == 0
    assert r.source_failures == 0
    assert r.oos_drops == 0
    assert r.terminated_reason is None
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_active.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the contract module**

```python
# src/earn_money/runners/active.py
"""Shared contract for Phase 3 active-recon runners.

Every active runner imports the result dataclass and the gate-check
helper from this module, so the gate order is identical across runners
and the result shape stays consistent for the digest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from earn_money import config, flags, policy, scope


@dataclass(frozen=True)
class ActiveRunResult:
    run_id: str
    targets_considered: int = 0
    targets_scanned: int = 0
    artifacts_written: int = 0
    outputs_recorded: int = 0
    source_failures: int = 0
    oos_drops: int = 0
    terminated_reason: Literal["kill_switch", "freeze", "timeout"] | None = None


def check_gates(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    mode: Literal["passive", "active"],
) -> scope.Scope:
    """Run the four pre-flight gates in canonical order and return the
    program's resolved scope on success. Any failure raises a typed
    exception that the runner's main() translates to an exit code."""
    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)
    s = scope.read_scope(paths.scope_file(platform, slug))
    policy.require_policy_allows(s, mode=mode)
    return s
```

- [ ] **Step 4: Verify GREEN + lint**

```bash
.venv/bin/python -m pytest tests/runners/test_active.py -v
make lint
```

Expected: 4 passed; lint clean.

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/runners/active.py tests/runners/test_active.py
git commit -m "feat: shared active-runner contract with gate-check helper"
```

---

## Task 6: Kill-switch watchdog

A background thread that polls `RECON_ENABLED` and `FROZEN` every 5 seconds and triggers a kill callback on state change. The wrapper passes a callback that SIGTERMs the in-flight subprocess.

**Files:**
- Create: `src/earn_money/runners/watchdog.py`
- Create: `tests/runners/test_watchdog.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_watchdog.py
from __future__ import annotations

import threading
import time
from pathlib import Path

from earn_money import config
from earn_money.runners import watchdog


def test_watchdog_fires_when_recon_disabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    fired = threading.Event()
    reason_holder: dict[str, str | None] = {"reason": None}

    def on_state_change(reason: str) -> None:
        reason_holder["reason"] = reason
        fired.set()

    wd = watchdog.KillSwitchWatchdog(
        paths, platform="hackerone", slug="example",
        on_state_change=on_state_change, poll_interval_s=0.05,
    )
    wd.start()
    try:
        paths.recon_enabled_flag.unlink()
        assert fired.wait(timeout=1.0), "watchdog never fired"
        assert reason_holder["reason"] == "kill_switch"
    finally:
        wd.stop()


def test_watchdog_fires_when_program_frozen(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    fired = threading.Event()
    reason_holder: dict[str, str | None] = {"reason": None}

    def on_state_change(reason: str) -> None:
        reason_holder["reason"] = reason
        fired.set()

    wd = watchdog.KillSwitchWatchdog(
        paths, platform="hackerone", slug="example",
        on_state_change=on_state_change, poll_interval_s=0.05,
    )
    wd.start()
    try:
        paths.program_dir("hackerone", "example").mkdir(parents=True, exist_ok=True)
        (paths.program_dir("hackerone", "example") / "FROZEN").write_text("test")
        assert fired.wait(timeout=1.0), "watchdog never fired"
        assert reason_holder["reason"] == "freeze"
    finally:
        wd.stop()


def test_watchdog_does_not_fire_when_state_stable(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    fired = threading.Event()

    wd = watchdog.KillSwitchWatchdog(
        paths, platform="hackerone", slug="example",
        on_state_change=lambda _: fired.set(),
        poll_interval_s=0.05,
    )
    wd.start()
    try:
        time.sleep(0.3)
        assert not fired.is_set()
    finally:
        wd.stop()
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_watchdog.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the watchdog**

```python
# src/earn_money/runners/watchdog.py
"""Background thread that polls RECON_ENABLED and the per-program FROZEN
flag every few seconds during a subprocess. On state change it calls a
kill callback so the wrapper can SIGTERM the in-flight tool."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Literal

from earn_money import config


Reason = Literal["kill_switch", "freeze"]


class KillSwitchWatchdog:
    """Thread that watches kill-switch + freeze state and fires a callback
    on change. ``start()`` begins polling; ``stop()`` joins cleanly. The
    callback is fired at most once per watchdog lifetime."""

    def __init__(
        self,
        paths: config.Paths,
        *,
        platform: str,
        slug: str,
        on_state_change: Callable[[Reason], None],
        poll_interval_s: float = 5.0,
    ) -> None:
        self._paths = paths
        self._platform = platform
        self._slug = slug
        self._on_state_change = on_state_change
        self._poll_interval = poll_interval_s
        self._stop = threading.Event()
        self._fired = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _frozen(self) -> bool:
        freeze_path = self._paths.program_dir(self._platform, self._slug) / "FROZEN"
        return freeze_path.exists()

    def _recon_enabled(self) -> bool:
        return self._paths.recon_enabled_flag.exists()

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._fired:
                return
            if not self._recon_enabled():
                self._fire("kill_switch")
                return
            if self._frozen():
                self._fire("freeze")
                return
            self._stop.wait(self._poll_interval)

    def _fire(self, reason: Reason) -> None:
        if self._fired:
            return
        self._fired = True
        self._on_state_change(reason)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self._poll_interval * 2)
```

- [ ] **Step 4: Verify GREEN + lint**

```bash
.venv/bin/python -m pytest tests/runners/test_watchdog.py -v
make lint
```

Expected: 3 passed; lint clean. (`config.Paths` may need a `program_dir()` helper if not present — add it under "Modify" in the same commit if so.)

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/runners/watchdog.py tests/runners/test_watchdog.py
git commit -m "feat: KillSwitchWatchdog polls RECON_ENABLED+FROZEN per 5s"
```

---

## Task 7: Batch subprocess wrapper

Splits a target list into bounded subprocess invocations, runs each under watchdog supervision, and returns aggregated results. This is where the per-batch SIGTERM/SIGKILL logic lives.

**Files:**
- Create: `src/earn_money/runners/batch.py`
- Create: `tests/runners/test_batch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_batch.py
from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from earn_money.runners import batch


def _fake_tool_script() -> list[str]:
    """A tiny Python one-liner that echoes its argv targets as JSONL."""
    return [
        sys.executable, "-c",
        "import sys, json\n"
        "for a in sys.argv[1:]:\n"
        "    print(json.dumps({'target': a}))",
    ]


def test_batches_split_targets_by_size() -> None:
    targets = [f"t{i}" for i in range(7)]
    calls: list[list[str]] = []

    def factory(chunk: list[str]) -> list[str]:
        calls.append(chunk)
        return _fake_tool_script() + chunk

    result = batch.run_batches(
        targets, command_factory=factory,
        max_batch_size=3, max_batch_duration_s=10.0,
    )
    assert [len(c) for c in calls] == [3, 3, 1]
    assert sum(len(b.lines) for b in result.batches) == 7


def test_batch_timeout_terminates_subprocess() -> None:
    def factory(_chunk: list[str]) -> list[str]:
        return [sys.executable, "-c", "import time; time.sleep(10)"]

    result = batch.run_batches(
        ["x"], command_factory=factory,
        max_batch_size=1, max_batch_duration_s=0.2,
    )
    assert result.batches[0].timed_out is True
    assert result.batches[0].lines == []


def test_watchdog_signal_terminates_in_flight() -> None:
    abort = threading.Event()

    def factory(_chunk: list[str]) -> list[str]:
        return [sys.executable, "-c", "import time; time.sleep(10)"]

    def trigger_abort_soon() -> None:
        time.sleep(0.1)
        abort.set()

    threading.Thread(target=trigger_abort_soon, daemon=True).start()
    result = batch.run_batches(
        ["x"], command_factory=factory,
        max_batch_size=1, max_batch_duration_s=10.0,
        abort=abort,
    )
    assert result.aborted is True
    assert result.batches[0].lines == []
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_batch.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the batch wrapper**

```python
# src/earn_money/runners/batch.py
"""Bounded subprocess batches for active-recon tools.

Each batch is one subprocess invocation. The wrapper splits the input
target list into chunks of ``max_batch_size``, runs each via
``command_factory``, captures stdout JSONL line-by-line, and enforces
``max_batch_duration_s``. A watchdog ``abort`` event terminates the
in-flight subprocess immediately."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field


CommandFactory = Callable[[list[str]], Sequence[str]]


@dataclass(frozen=True)
class BatchResult:
    chunk_size: int
    lines: tuple[str, ...]
    timed_out: bool
    return_code: int | None
    stderr: str


@dataclass(frozen=True)
class BatchesResult:
    batches: tuple[BatchResult, ...] = field(default_factory=tuple)
    aborted: bool = False


def run_batches(
    targets: Sequence[str],
    *,
    command_factory: CommandFactory,
    max_batch_size: int,
    max_batch_duration_s: float,
    abort: threading.Event | None = None,
) -> BatchesResult:
    if max_batch_size <= 0:
        raise ValueError("max_batch_size must be positive")
    abort_event = abort or threading.Event()
    results: list[BatchResult] = []
    aborted = False

    for chunk in _chunks(targets, max_batch_size):
        if abort_event.is_set():
            aborted = True
            break
        result = _run_one(
            command_factory(chunk), max_batch_duration_s, abort_event,
            chunk_size=len(chunk),
        )
        results.append(result)
        if abort_event.is_set():
            aborted = True
            break

    return BatchesResult(batches=tuple(results), aborted=aborted)


def _chunks(targets: Sequence[str], size: int) -> list[list[str]]:
    return [list(targets[i : i + size]) for i in range(0, len(targets), size)]


def _run_one(
    command: Sequence[str],
    timeout_s: float,
    abort: threading.Event,
    *,
    chunk_size: int,
) -> BatchResult:
    proc = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

    def kill_if_aborted() -> None:
        if abort.wait(timeout_s):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    abort_thread = threading.Thread(target=kill_if_aborted, daemon=True)
    abort_thread.start()

    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        timed_out = False
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        timed_out = True
    finally:
        abort.set()  # ensure the abort thread exits
        abort_thread.join(timeout=1)

    return BatchResult(
        chunk_size=chunk_size,
        lines=tuple(line for line in stdout.splitlines() if line),
        timed_out=timed_out,
        return_code=proc.returncode,
        stderr=stderr,
    )
```

- [ ] **Step 4: Verify GREEN + lint**

```bash
.venv/bin/python -m pytest tests/runners/test_batch.py -v
make lint
```

Expected: 3 passed; lint clean.

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/runners/batch.py tests/runners/test_batch.py
git commit -m "feat: bounded-batch subprocess wrapper with timeout+abort"
```

---

## Task 8: httpx tool wrapper

Thin shell around the `httpx` CLI from ProjectDiscovery. Invokes with safety flags (`-no-follow-redirects`, JSON output), parses JSONL into `HttpService` rows.

**Files:**
- Create: `src/earn_money/recon/httpx_tool.py`
- Create: `tests/recon/test_httpx_tool.py`
- Create: `tests/fixtures/httpx_output.jsonl`

- [ ] **Step 1: Add the JSONL fixture**

```
# tests/fixtures/httpx_output.jsonl
{"url":"https://api.example.com","host":"api.example.com","port":"443","scheme":"https","status_code":200,"title":"Example API","webserver":"nginx","tech":["nginx","openresty"],"location":"","tls":{"issuer_org":["Let's Encrypt"]}}
{"url":"http://www.example.com","host":"www.example.com","port":"80","scheme":"http","status_code":301,"title":"","webserver":"nginx","tech":["nginx"],"location":"https://www.example.com/","tls":{}}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/recon/test_httpx_tool.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from earn_money.recon import httpx_tool


def test_parse_jsonl_returns_services(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "httpx_output.jsonl").read_text(encoding="utf-8")
    services = httpx_tool.parse_jsonl(raw, run_id="r1", observed_at="t1")
    assert len(services) == 2
    api = services[0]
    assert api.subdomain == "api.example.com"
    assert api.scheme == "https"
    assert api.port == 443
    assert api.status_code == 200
    assert api.title == "Example API"
    assert api.server == "nginx"
    assert tuple(api.technologies) == ("nginx", "openresty")
    assert api.redirect_to is None
    assert api.tls_summary is not None


def test_parse_jsonl_captures_redirect_target(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "httpx_output.jsonl").read_text(encoding="utf-8")
    services = httpx_tool.parse_jsonl(raw, run_id="r1", observed_at="t1")
    www = services[1]
    assert www.redirect_to == "https://www.example.com/"
    assert www.status_code == 301


def test_command_includes_safety_flags() -> None:
    cmd = httpx_tool.build_command(["api.example.com", "www.example.com"])
    assert "-no-follow-redirects" in cmd
    assert "-json" in cmd
    assert "-silent" in cmd
    assert cmd[-1] == "-"  # read targets from stdin


def test_parse_skips_malformed_lines(fixtures_dir: Path) -> None:
    raw = "not-json\n" + (fixtures_dir / "httpx_output.jsonl").read_text(encoding="utf-8")
    services = httpx_tool.parse_jsonl(raw, run_id="r1", observed_at="t1")
    # The "not-json" line is skipped; the two real lines remain.
    assert len(services) == 2
```

- [ ] **Step 3: Verify RED**

```bash
.venv/bin/python -m pytest tests/recon/test_httpx_tool.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement the wrapper**

```python
# src/earn_money/recon/httpx_tool.py
"""Subprocess wrapper around the ProjectDiscovery ``httpx`` CLI.

Not to be confused with the Python ``httpx`` library — this module
shells out to the binary. Parsing is forgiving: a malformed line is
logged-and-skipped rather than abort the parse."""

from __future__ import annotations

import json
from collections.abc import Sequence

from earn_money.recon.services import HttpService


def build_command(targets: Sequence[str]) -> list[str]:
    """Return argv for an httpx invocation. Targets are fed via stdin so
    the command line stays bounded regardless of input size."""
    return [
        "httpx",
        "-silent",
        "-json",
        "-no-follow-redirects",
        "-status-code",
        "-title",
        "-tech-detect",
        "-tls-grab",
        "-web-server",
        "-",
    ]


def parse_jsonl(
    raw: str, *, run_id: str, observed_at: str
) -> list[HttpService]:
    """Parse the JSONL output of httpx into HttpService rows. Lines
    that don't decode are silently skipped — the runner counts them
    via parse_failures separately if it cares."""
    services: list[HttpService] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            services.append(_to_service(data, run_id=run_id, observed_at=observed_at))
        except (KeyError, ValueError):
            continue
    return services


def _to_service(data: dict, *, run_id: str, observed_at: str) -> HttpService:
    techs = tuple(data.get("tech") or ())
    tls = data.get("tls") or {}
    location = data.get("location") or None
    return HttpService(
        subdomain=str(data["host"]),
        scheme=str(data["scheme"]),
        port=int(data["port"]),
        url=str(data["url"]),
        status_code=int(data["status_code"]) if "status_code" in data else None,
        title=(data.get("title") or None),
        server=(data.get("webserver") or None),
        technologies=techs,
        redirect_to=location,
        tls_summary=json.dumps(tls) if tls else None,
        observed_at=observed_at,
        last_run_id=run_id,
        in_scope_at_observation=True,
    )
```

- [ ] **Step 5: Verify GREEN + lint**

```bash
.venv/bin/python -m pytest tests/recon/test_httpx_tool.py -v
make lint
```

Expected: 4 passed; lint clean.

- [ ] **Step 6: Commit**

```bash
git add src/earn_money/recon/httpx_tool.py tests/recon/test_httpx_tool.py tests/fixtures/httpx_output.jsonl
git commit -m "feat: httpx tool wrapper with safety flags + JSONL parser"
```

---

## Task 9: `httpx_probe` runner module

Wires it all together: gate check → load assets → scope filter → batch + watchdog → parse → upsert services → record run.

**Files:**
- Create: `src/earn_money/runners/httpx_probe.py`
- Create: `tests/runners/test_httpx_probe.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_httpx_probe.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, flags, policy, scope
from earn_money.recon import services
from earn_money.runners import httpx_probe


def _seed(paths: config.Paths, *, in_scope: list[str], out_of_scope: list[str] | None = None) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=in_scope, out_of_scope=out_of_scope or [], notes="",
        scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_assets(paths: config.Paths, subdomains: list[str]) -> None:
    from earn_money import db
    from earn_money.recon import assets
    conn = db.open_db(paths.program_db("hackerone", "example"))
    obs = [assets.AssetObservation(subdomain=sd, ips=()) for sd in subdomains]
    assets.upsert_assets(conn, obs, observed_at="2026-05-12T07:00:00Z", in_scope=True)
    conn.close()


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com"])
    with pytest.raises(flags.ReconDisabled):
        httpx_probe.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: [],
        )


def test_refuses_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="manual-only",
        in_scope=["*.example.com"], out_of_scope=[], notes="",
        scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    with pytest.raises(policy.PolicyViolation):
        httpx_probe.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: [],
        )


def test_writes_services_for_in_scope_assets(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["*.example.com"])
    _seed_assets(paths, ["api.example.com", "www.example.com"])

    def fake_tool(targets: list[str]) -> list[services.HttpService]:
        return [
            services.HttpService(
                subdomain=t, scheme="https", port=443,
                url=f"https://{t}/", status_code=200, title="ok",
                server="nginx", technologies=("nginx",),
                redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            )
            for t in targets
        ]

    result = httpx_probe.run_program(
        paths, "hackerone", "example",
        tool_run=fake_tool,
    )
    assert result.targets_scanned == 2
    assert result.artifacts_written == 1  # one manifest written

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM http_services ORDER BY subdomain").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com", "www.example.com"]


def test_drops_out_of_scope_targets_from_tool_output(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, in_scope=["api.example.com"])
    _seed_assets(paths, ["api.example.com"])

    def leaky_tool(_targets: list[str]) -> list[services.HttpService]:
        # Simulates httpx returning an OOS host (which the wrapper must drop).
        return [
            services.HttpService(
                subdomain="api.example.com", scheme="https", port=443,
                url="https://api.example.com/", status_code=200, title="",
                server="nginx", technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            ),
            services.HttpService(
                subdomain="evil.example.com", scheme="https", port=443,
                url="https://evil.example.com/", status_code=200, title="",
                server="nginx", technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="r", in_scope_at_observation=True,
            ),
        ]

    result = httpx_probe.run_program(
        paths, "hackerone", "example",
        tool_run=leaky_tool,
    )
    assert result.oos_drops == 1
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM http_services").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com"]
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_httpx_probe.py -v
```

Expected: ModuleNotFoundError on `httpx_probe`.

- [ ] **Step 3: Implement the runner**

```python
# src/earn_money/runners/httpx_probe.py
"""Active HTTP probing runner — converts in-scope assets to live HTTP
service observations using the ProjectDiscovery httpx CLI."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from earn_money import config, db, flags, policy, scope
from earn_money.recon import runs, services
from earn_money.recon.services import HttpService
from earn_money.runners import active

ToolRun = Callable[[list[str]], list[HttpService]]


def _load_in_scope_assets(conn, s: scope.Scope) -> list[str]:
    cursor = conn.execute(
        "SELECT subdomain FROM assets WHERE in_scope_at_observation = 1 "
        "ORDER BY subdomain"
    )
    return [row[0] for row in cursor if scope.is_in_scope(row[0], s.in_scope, s.out_of_scope)]


def _write_manifest(artifact_dir: Path, payload: dict) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_run: ToolRun,
) -> active.ActiveRunResult:
    """Run httpx for one program. Gates are checked before any target
    traffic. The ``tool_run`` callable is injected so tests can swap
    in a deterministic fake."""
    s = active.check_gates(paths, platform, slug, mode="active")

    run_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat(timespec="seconds")
    artifact_dir = paths.repo_root / (
        f"recon/outputs/{platform}/{slug}/httpx/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        targets = _load_in_scope_assets(conn, s)
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="httpx",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )
        raw_services = tool_run(targets) if targets else []

        in_scope = [
            svc for svc in raw_services
            if scope.is_in_scope(svc.subdomain, s.in_scope, s.out_of_scope)
        ]
        oos_drops = len(raw_services) - len(in_scope)

        for svc in in_scope:
            services.upsert_service(conn, svc.__class__(
                **{**svc.__dict__, "last_run_id": run_id, "observed_at": now},
            ))

        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "httpx",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "output_count": len(in_scope), "oos_drops": oos_drops,
        })

        finished = datetime.now(UTC).isoformat(timespec="seconds")
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status="success",
            output_count=len(in_scope), signal_count=0,
            source_failures=0, oos_drops=oos_drops,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            outputs_recorded=0,
            source_failures=0,
            oos_drops=oos_drops,
        )
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="httpx-probe")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)

    # Wire the real tool wrapper as a default tool_run. The kill-switch
    # watchdog runs alongside the subprocess and sets the abort event
    # immediately if RECON_ENABLED is removed or FROZEN appears — so
    # active traffic stops within ~10s of operator intervention, not at
    # the next batch boundary.
    import threading
    from earn_money.recon import httpx_tool
    from earn_money.runners import batch, watchdog

    def real_tool(targets: list[str]) -> list[HttpService]:
        abort = threading.Event()
        wd = watchdog.KillSwitchWatchdog(
            paths, platform=args.platform, slug=args.program,
            on_state_change=lambda _reason: abort.set(),
            poll_interval_s=5.0,
        )
        wd.start()
        try:
            result = batch.run_batches(
                targets,
                command_factory=lambda chunk: httpx_tool.build_command(chunk),
                max_batch_size=50, max_batch_duration_s=300.0,
                abort=abort,
            )
        finally:
            wd.stop()
        raw = "\n".join(line for b in result.batches for line in b.lines)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        return httpx_tool.parse_jsonl(raw, run_id="pending", observed_at=now)

    try:
        result = run_program(
            paths, args.platform, args.program, tool_run=real_tool,
        )
    except flags.ReconDisabled as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"httpx-probe: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(
        f"httpx-probe: scanned={result.targets_scanned} "
        f"services={result.targets_scanned - result.oos_drops} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify GREEN + lint**

```bash
.venv/bin/python -m pytest tests/runners/test_httpx_probe.py -v
make lint
```

Expected: 4 passed; lint clean. Note: this task may push `httpx_probe.py` toward the 200-line cap. If it exceeds, extract `main()` and tool-wiring helpers into a separate `httpx_probe_cli.py` and re-run.

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/runners/httpx_probe.py tests/runners/test_httpx_probe.py
git commit -m "feat: httpx-probe runner with scope-aware service upsert"
```

---

## Task 10: `bin/httpx-probe` CLI

Mirrors `bin/passive-recon`. Sources `.env`, exports tokens (none needed for httpx today, but symmetric structure helps future runners), invokes the runner module.

**Files:**
- Create: `bin/httpx-probe`

- [ ] **Step 1: Write the script**

```sh
#!/bin/sh
# Thin wrapper around the httpx-probe runner.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "httpx-probe: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" -m earn_money.runners.httpx_probe --root "$ROOT" "$@"
```

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x bin/httpx-probe
bin/httpx-probe --help
```

Expected: argparse usage output for `httpx-probe`.

- [ ] **Step 3: Commit**

```bash
git add bin/httpx-probe
git commit -m "feat: bin/httpx-probe CLI wrapper"
```

---

## Task 11: Mock-target fixture for integration tests

A tiny stdlib HTTP server serving a deterministic surface: two in-scope hosts, one OOS host, a 302 redirect from in-scope to OOS, all on different ports of `127.0.0.1`. Used by Task 12's end-to-end test.

**Files:**
- Create: `tests/fixtures/mock_target/server.py`
- Create: `tests/fixtures/mock_target/conftest.py`

- [ ] **Step 1: Write the server**

```python
# tests/fixtures/mock_target/server.py
"""Deterministic HTTP fixture for active-recon integration tests.

Runs three handlers on three local ports so a single host header maps
to a distinct in-scope / out-of-scope identity:

- 127.0.0.1:18081  — in-scope host A. Returns 200 with title.
- 127.0.0.1:18082  — in-scope host B. Returns 200 with a 301 redirect
                     to the OOS host (tests --no-follow-redirects).
- 127.0.0.1:18083  — OOS host. Returns 200; should never be probed by
                     the wrapper post-scope-filter."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _InScopeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Server", "mock-target/1.0")
        self.end_headers()
        self.wfile.write(b"<title>In-Scope A</title>")

    def log_message(self, *_a: object, **_k: object) -> None:
        pass


class _RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(301)
        self.send_header("Location", "http://127.0.0.1:18083/")
        self.end_headers()

    def log_message(self, *_a: object, **_k: object) -> None:
        pass


class _OosHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Server", "should-not-be-probed/1.0")
        self.end_headers()
        self.wfile.write(b"<title>OOS</title>")

    def log_message(self, *_a: object, **_k: object) -> None:
        pass


def _serve(port: int, handler_cls: type[BaseHTTPRequestHandler]) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def start_mock_target() -> tuple[HTTPServer, HTTPServer, HTTPServer]:
    return (
        _serve(18081, _InScopeHandler),
        _serve(18082, _RedirectHandler),
        _serve(18083, _OosHandler),
    )


def stop_mock_target(servers: tuple[HTTPServer, ...]) -> None:
    for s in servers:
        s.shutdown()
        s.server_close()
```

- [ ] **Step 2: Write the pytest fixture**

```python
# tests/fixtures/mock_target/conftest.py
from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.fixtures.mock_target.server import start_mock_target, stop_mock_target


@pytest.fixture
def mock_target() -> Iterator[None]:
    servers = start_mock_target()
    try:
        yield
    finally:
        stop_mock_target(servers)
```

- [ ] **Step 3: Verify the fixture starts/stops cleanly**

```bash
.venv/bin/python -c "
from tests.fixtures.mock_target.server import start_mock_target, stop_mock_target
import urllib.request
servers = start_mock_target()
try:
    resp = urllib.request.urlopen('http://127.0.0.1:18081/').read()
    assert b'In-Scope A' in resp
    print('mock target up')
finally:
    stop_mock_target(servers)
print('mock target down')
"
```

Expected output:
```
mock target up
mock target down
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/mock_target/
git commit -m "test: mock-target HTTP fixture with in-scope/OOS hosts"
```

---

## Task 12: End-to-end integration test

Runs the real httpx binary against the mock target via the full runner code path. Asserts: in-scope rows persisted, OOS host never reached the DB (wrapper's post-tool scope filter caught it), `recon_runs` row present with status=success, kill-switch arming actually halts the run.

**Files:**
- Create: `tests/runners/test_httpx_probe_e2e.py`

- [ ] **Step 1: Skip-marker logic for missing httpx binary**

We do not want CI to fail if the dev hasn't installed `httpx` yet. The test self-skips when the binary is absent.

```python
# tests/runners/test_httpx_probe_e2e.py — header
from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import assets, services
from earn_money.runners import httpx_probe

pytestmark = pytest.mark.skipif(
    shutil.which("httpx") is None,
    reason="ProjectDiscovery httpx binary not on PATH",
)
```

- [ ] **Step 2: Write the happy-path e2e test**

```python
# tests/runners/test_httpx_probe_e2e.py — append

pytest_plugins = ["tests.fixtures.mock_target.conftest"]


def _seed(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["127.0.0.1"],  # fake "domain" so the runner accepts our IPs
        out_of_scope=[], notes="",
        scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="127.0.0.1", ips=("127.0.0.1",))],
        observed_at="2026-05-12T07:00:00Z", in_scope=True,
    )
    conn.close()
    return paths


def test_e2e_probes_in_scope_target(tmp_repo: Path, mock_target: None) -> None:
    paths = _seed(tmp_repo)
    # Real httpx wrapper, but we feed it only the in-scope mock port.
    # We use the test-facing run_program path to inject a tool_run that
    # invokes the real binary against the fixture.
    from earn_money.recon import httpx_tool

    def tool_run(_targets: list[str]) -> list[services.HttpService]:
        from earn_money.runners import batch
        result = batch.run_batches(
            ["http://127.0.0.1:18081/"],  # explicit URL with mock port
            command_factory=lambda chunk: httpx_tool.build_command(chunk),
            max_batch_size=1, max_batch_duration_s=10.0,
        )
        raw = "\n".join(line for b in result.batches for line in b.lines)
        return httpx_tool.parse_jsonl(raw, run_id="e2e", observed_at="t")

    result = httpx_probe.run_program(
        paths, "hackerone", "example", tool_run=tool_run,
    )
    assert result.targets_scanned >= 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT subdomain, status_code FROM http_services"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs"
    ).fetchall()
    conn.close()

    assert any(r[0] == "127.0.0.1" and r[1] == 200 for r in rows)
    assert runs_rows == [("success",)]
```

- [ ] **Step 3: Write the redirect-without-following test**

The OOS-drop behaviour is already proven in Task 9's `test_drops_out_of_scope_targets_from_tool_output` (synthetic `tool_run` returning a real OOS observation, verifying the wrapper filters it). Trying to re-prove it end-to-end against the real httpx binary requires injecting an OOS-named observation post-parse, which produces a false-positive test that passes whether the wrapper filters or not.

The e2e test should instead cover what only an end-to-end run can prove: the **real httpx subprocess does not follow redirects** (because the wrapper passes `-no-follow-redirects`), and the redirect target is captured in `redirect_to` without any traffic to the OOS host.

```python
# tests/runners/test_httpx_probe_e2e.py — append

def test_e2e_captures_redirect_without_following(
    tmp_repo: Path, mock_target: None
) -> None:
    """Port 18082 serves a 301 to port 18083 (the OOS host). The real
    httpx must record the 301 + redirect_to without following — proving
    the -no-follow-redirects flag is wired correctly. We then assert
    that no row exists for the OOS host (no traffic was sent to it)."""
    paths = _seed(tmp_repo)
    from earn_money.recon import httpx_tool

    def tool_run(_targets: list[str]) -> list[services.HttpService]:
        from earn_money.runners import batch
        result = batch.run_batches(
            ["http://127.0.0.1:18082/"],
            command_factory=lambda chunk: httpx_tool.build_command(chunk),
            max_batch_size=1, max_batch_duration_s=10.0,
        )
        raw = "\n".join(line for b in result.batches for line in b.lines)
        return httpx_tool.parse_jsonl(raw, run_id="e2e-redirect", observed_at="t")

    httpx_probe.run_program(
        paths, "hackerone", "example", tool_run=tool_run,
    )

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    redirect_rows = conn.execute(
        "SELECT status_code, redirect_to FROM http_services "
        "WHERE port = 18082"
    ).fetchall()
    oos_port_rows = conn.execute(
        "SELECT port FROM http_services WHERE port = 18083"
    ).fetchall()
    conn.close()

    assert redirect_rows == [(301, "http://127.0.0.1:18083/")]
    # If httpx had followed the redirect, port 18083 would also have a row.
    # The mock target's port-18083 handler returns 200, so any row there
    # proves the wrapper failed to disable redirect-following.
    assert oos_port_rows == []
```

- [ ] **Step 4: Verify GREEN + lint**

```bash
.venv/bin/python -m pytest tests/runners/test_httpx_probe_e2e.py -v
make lint
```

Expected: 2 passed (or skipped if `httpx` is not installed); lint clean.

- [ ] **Step 5: Final full-suite verification**

```bash
make smoke
```

Expected: ruff + mypy clean, every prior test still passing, all new tests passing. Roughly: 76 (pre-3a) + 3 (migrations) + 3 (runs) + 3 (services) + 2 (signals) + 4 (active) + 3 (watchdog) + 3 (batch) + 4 (httpx tool) + 4 (httpx probe unit) + 2 (e2e) ≈ **107 passing**.

- [ ] **Step 6: Commit**

```bash
git add tests/runners/test_httpx_probe_e2e.py
git commit -m "test: end-to-end httpx-probe smoke against mock target"
```

---

## Self-review

Spec coverage:

| Spec item (section 3a) | Task |
|---|---|
| Artifact directory layout | Task 9 (`_write_manifest`, paths construction) |
| `manifest.json` contract | Task 9 |
| `recon_runs` schema and tests | Task 1, Task 2 |
| Thin subprocess wrapper pattern | Task 7, Task 8 |
| `httpx` runner and CLI | Task 9, Task 10 |
| Scope test | Task 9 step 2 + Task 12 |
| Policy test | Task 9 step 2 + Task 5 |
| Kill-switch test | Task 5 + Task 6 |
| Freeze test | Task 5 + Task 6 |
| Source-failure tests | Task 9 (tool failure path) + Task 7 (batch timeout) |

Plus spec section 4 items covered by 3a: schema migration (Task 1), `http_services` table (Task 1, Task 3), `signals` table (Task 1, Task 4), per-request scope enforcement (Task 9 post-tool re-check), failure taxonomy (Task 5, Task 7).

Spec items NOT covered in 3a (intentional, per umbrella roadmap):
- Finding-hash normalization rules → 3b (no findings yet)
- nuclei + triage v1 → 3b
- katana + ffuf → 3c
- digest + phone ping + freeze-ack → 3d

Placeholder scan: no TBD / TODO / "fill in" tokens in this plan. Every code step shows actual code; every command shows the actual invocation and the expected output.

Type consistency: `ActiveRunResult` defined in Task 5 with eight fields; referenced in Task 9 with the same field names. `HttpService` defined in Task 3; consumed identically in Tasks 8 and 9. `Signal` defined in Task 4. `BatchResult` defined in Task 7, not referenced elsewhere in the plan (its purpose is the batch wrapper's own contract). `recon_runs` columns added by the migration in Task 1 match the queries in Tasks 2 and 9.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-phase-3a-active-runner-foundation.md`. Two execution options:

1. **Subagent-Driven** (recommended) — a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
