# Phase 3b — nuclei + Triage v1 Implementation Plan

> **Post-ship note (hygiene cycle 3):** `tests/runners/test_nuclei_scan.py` was split into three theme files during cycle 3: `test_nuclei_scan_gates.py`, `test_nuclei_scan_pipeline.py`, and `test_nuclei_scan_resilience.py`. References to `test_nuclei_scan.py` below are historical.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first vulnerability-signal loop — the `nuclei` active runner (limited to approved CVE + standard-misconfig templates), the expanded `findings` schema with a state machine, the finding-hash helper with deterministic normalization, and a triage engine v1 that joins recon signals against the asset DB, deduplicates by hash, and writes operator-review candidates into `findings/_queue/`.

**Architecture:** Two parallel runner shapes layered on Phase 3a primitives. `nuclei-scan` mirrors `httpx-probe`: gate-check → load live HTTP services from `http_services` → batched subprocess under the kill-switch watchdog → parse JSONL into `Signal` rows + raw artifact → record `recon_runs`. `triage` is a non-traffic runner: gate-check (kill-switch + scope only — policy gate is skipped since triage emits no target traffic) → query `recon_runs WHERE finished_at IS NOT NULL AND triaged_at IS NULL` → fetch each run's signals → compute `finding_hash` via `triage.hashing.compute_hash` → upsert into the expanded `findings` table (triage may create `queued` rows and refresh non-state fields, but cannot mutate `current_state`) → write `findings/_queue/<hash>.md` markdown candidate → mark `recon_runs.triaged_at`. The state machine is enforced by a dedicated `transition_state` helper that writes an append-only `findings_state_history` row inside the same transaction as the `findings.current_state` UPDATE; triage never calls it.

**Tech Stack:** Python 3.12+, `sqlite3` (stdlib), `subprocess` (nuclei invocation), `urllib.parse` + `idna` (URL normalization), `hashlib` (SHA-256), `pytest`, `mypy --strict`, `ruff`. The ProjectDiscovery `nuclei` CLI is shelled out. No new runtime dependencies — `idna` ships with the stdlib's `encodings.idna`; we use `idna` from PyPI only if the additional UTS-46 normalization actually needs it (see Task 2 for the decision).

**Spec reference:** [`docs/superpowers/specs/2026-05-12-phase-3-design.md`](../specs/2026-05-12-phase-3-design.md) — Phase 3b-specific sections: 3 (Shared Active Runner Contract + Shared Artifact Contract + 3.2 nuclei + 3.7 Triage Engine), 4 (schema migration v2→v3 + expanded `findings` columns + finding-hash composition + normalization rules + finding state machine + `signals` table semantics — `signals` schema already shipped in 3a), 5 (nuclei-scan timer 02:15 UTC, triage timer 05:00 UTC), 7 (open implementation questions Phase 3b must settle: migration atomic boundary already settled in 3a — confirmed; signals atomic boundary is settled here by treating the DB row as authoritative and writing `signals.jsonl` as a write-then-reconcile artifact).

---

## File map

**Create:**
- `src/earn_money/triage/__init__.py` — package marker
- `src/earn_money/triage/hashing.py` — `compute_hash`, `normalize_asset`, `normalize_target`, signature composition helpers (nuclei + httpx_anomaly)
- `src/earn_money/triage/findings.py` — `Finding` dataclass + DAO: `upsert_finding`, `refresh_seen`, `find_by_hash`, `findings_in_state`
- `src/earn_money/triage/history.py` — `transition_state` + `state_history_for_hash` (append-only audit DAO)
- `src/earn_money/triage/queue.py` — pure markdown formatter that turns a `Finding` + context into the body of `findings/_queue/<hash>.md`
- `src/earn_money/triage/engine.py` — `run_program(paths, platform, slug, *, now=None)` — the triage engine v1
- `src/earn_money/recon/nuclei_tool.py` — thin subprocess wrapper around the `nuclei` CLI: `build_command(targets, *, template_dirs)`, `parse_jsonl(raw, *, run_id, observed_at)` → `list[Signal]`, `APPROVED_TEMPLATE_DIRS` constant, `UnsafeTemplateProfile` exception
- `src/earn_money/runners/nuclei_scan.py` — the nuclei runner (mirrors `httpx_probe.run_program`)
- `src/earn_money/runners/triage.py` — the triage runner (cron entry point; loops over programs)
- `bin/nuclei-scan` — sh wrapper for the runner
- `bin/triage` — sh wrapper for the runner
- `tests/triage/__init__.py` — package marker
- `tests/triage/test_hashing.py` — normalization stability + collision-resistance property tests + per-tool signature tests
- `tests/triage/test_findings.py` — findings DAO unit tests
- `tests/triage/test_history.py` — state-history DAO + transition tests (allowed/forbidden transitions)
- `tests/triage/test_queue.py` — queue markdown formatter unit tests
- `tests/triage/test_engine.py` — triage engine unit tests with fake recon runs + signals
- `tests/recon/test_nuclei_tool.py` — nuclei tool wrapper unit tests
- `tests/runners/test_nuclei_scan.py` — nuclei runner unit tests with injected `tool_run`
- `tests/runners/test_nuclei_scan_e2e.py` — end-to-end nuclei smoke against the mock target with a synthetic template fixture (auto-skips when binary or templates absent)
- `tests/runners/test_triage_runner.py` — triage runner gate-check tests
- `tests/runners/test_triage_e2e.py` — full integration: seed a finished nuclei `recon_runs` row + signals, run triage, assert `findings` row + `_queue/*.md` file
- `tests/fixtures/nuclei_output.jsonl` — small fixture for parser tests
- `tests/fixtures/nuclei_templates/synthetic-200.yaml` — synthetic nuclei template used by the e2e (matches on the mock target's 200-response title)

**Modify:**
- `src/earn_money/migrations.py` — add `_V3_SCHEMA` (column additions for `findings` + new `findings_state_history` table) and `_apply_v3` step; register in `_STEPS`
- `src/earn_money/db.py` — bump `CURRENT_SCHEMA_VERSION` from 2 to 3
- `src/earn_money/config.py` — add `findings_queue_dir`, `findings_verified_dir`, `findings_submitted_dir`, `findings_resolved_dir` helpers on `Paths`
- `tests/test_migrations.py` — add the v2→v3 upgrade test, the idempotency at v=3 test, and a "v2 row backfills with sentinels" test
- `pyproject.toml` — add `idna>=3.6` if Task 2 needs UTS-46 (decision is captured inside Task 2 Step 1; default is: not needed — stdlib `idna` is sufficient for hostname encoding because Phase 3b only handles ASCII hostnames in practice)

**Touch only when justified:** anything else. Per the project's "Surgical changes" rule, every changed line must trace back to a 3b requirement.

---

## Task 1: Schema migration v2 → v3

Extend `migrations.py` with a `_apply_v3` step that:

1. Adds the new columns from spec section 4 to `findings` via `ALTER TABLE ... ADD COLUMN ...` (literal defaults supplied so Phase 2/3a rows backfill cleanly).
2. Creates the new `findings_state_history` audit table.
3. Bumps `PRAGMA user_version` to 3 inside the same transaction (3a's `migrate()` already does this — we just register the new step).

The v1 `findings` table has 6 columns: `finding_hash`, `vuln_class`, `target`, `first_seen`, `current_state`, `notes_path`. The v3 schema requires the additional columns from spec section 4. For each pre-existing row, the new columns receive the literal defaults in the `ALTER TABLE` clauses; the absence of `platform` / `slug` on legacy rows is patched by an `UPDATE` inside the same migration that copies them from the per-program directory layout (the migration is per-DB, so the migration callsite already knows which `platform`/`slug` owns the connection — but the DB doesn't, so for legacy rows the migration writes the literal `'__legacy__'` sentinel which the digest treats as a recon anomaly to surface for the operator). This keeps the migration deterministic without needing the `platform`/`slug` to be threaded through `migrate()`.

**Files:**
- Modify: `src/earn_money/migrations.py`
- Modify: `src/earn_money/db.py` (bump `CURRENT_SCHEMA_VERSION` to 3)
- Modify: `tests/test_migrations.py`

- [ ] **Step 1: Write the failing fresh-v3 test**

```python
# tests/test_migrations.py — append
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
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/test_migrations.py::test_fresh_db_migrates_to_v3 -v
```

Expected: assertion fails because v3 is not registered (or the `findings_state_history` table is missing, depending on which assertion trips first).

- [ ] **Step 3: Implement `_V3_SCHEMA` and `_apply_v3`**

```python
# src/earn_money/migrations.py — append (before _STEPS dict)

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


def _apply_v3(conn: sqlite3.Connection) -> None:
    """Widen `findings` and create `findings_state_history`."""
    # Read current columns once so we can be idempotent in the rare case
    # a partial v3 was applied earlier (e.g. crash between ALTERs).
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(findings)")
    }
    for name, definition in _V3_SCHEMA_FINDINGS_COLUMNS:
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE findings ADD COLUMN {name} {definition}")
    # Backfill `last_seen` and `state_changed_at` from `first_seen` on
    # legacy rows so the state machine has a real timestamp to work with.
    conn.execute(
        "UPDATE findings SET last_seen = first_seen "
        "WHERE last_seen = '' AND first_seen != ''"
    )
    conn.execute(
        "UPDATE findings SET state_changed_at = first_seen "
        "WHERE state_changed_at = '' AND first_seen != ''"
    )
    _execute_script(conn, _V3_SCHEMA_HISTORY)


_STEPS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _apply_v1,
    2: _apply_v2,
    3: _apply_v3,
}
```

- [ ] **Step 4: Bump the db.py constant**

```python
# src/earn_money/db.py — replace the constant line
CURRENT_SCHEMA_VERSION = 3
```

- [ ] **Step 5: Verify the fresh-v3 test GREEN + idempotency test**

```python
# tests/test_migrations.py — append
def test_v3_migration_is_idempotent(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "idem_v3.sqlite")
    migrations.migrate(conn, target_version=3)
    migrations.migrate(conn, target_version=3)
    assert _user_version(conn) == 3
```

Run:

```bash
.venv/bin/python -m pytest tests/test_migrations.py -v
```

Expected: all migration tests pass (including 3a's prior tests).

- [ ] **Step 6: Add the v2→v3 upgrade-preserving-data test**

```python
# tests/test_migrations.py — append
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
```

Run + verify GREEN.

- [ ] **Step 7: Lint**

```bash
make lint
```

Expected: ruff + mypy clean.

- [ ] **Step 8: Commit**

```bash
git add src/earn_money/migrations.py src/earn_money/db.py tests/test_migrations.py
git commit -m "feat: schema migration v2→v3 with expanded findings + state history"
```

---

## Task 2: Finding-hash helper + normalization

The finding hash composes a canonical string and SHA-256s it:

```
sha256("v1|<platform>|<slug>|<vuln_class>|<normalized_asset>|<normalized_target>|<signature>")
```

Normalization rules per spec section 4 (paraphrased):

1. Lowercase scheme + host only. Preserve case in path/query/fragment.
2. Strip default ports (`:80` for `http`, `:443` for `https`).
3. Punycode IDN labels (stdlib `encodings.idna` via `host.encode("idna").decode("ascii")` — sufficient for the ASCII + punycode-on-input case Phase 3b targets).
4. Collapse `//` to `/`, resolve `.` / `..`, strip trailing `/` except on root.
5. Drop the fragment.
6. Sort query params by `(key, value)`. Drop empty-value params unless the key is in `_QUERY_ALLOWLIST` (initially `frozenset({"debug", "trace"})` — extend as we encounter more).
7. Percent-decode unreserved characters per RFC 3986; re-encode reserved characters in canonical form (we use `urllib.parse.quote(..., safe="/?&=:@")` which matches RFC 3986's canonical form for our use).

`normalized_asset` = the hostname after steps 1 + 3 only. `normalized_target` = the full URL after all seven steps. For non-URL targets (a raw hostname passed to nuclei), `normalized_target == normalized_asset`.

Per-tool signature composition is documented in spec section 4. Phase 3b implements two:

- **nuclei**: `<template_id>|<matcher_name>|<extracted_normalized>` where `extracted_normalized` is the matcher's primary captured value normalized via rules 1-7 (or empty string when nuclei produces no extraction).
- **httpx anomaly**: `<signal_type>|<old_fingerprint_sha256_prefix12>|<new_fingerprint_sha256_prefix12>` — fingerprints are hashed and truncated so noise in jittery headers doesn't propagate into the dedup key.

The 3c plan will add katana + ffuf signature composers using the same dispatch table.

**Files:**
- Create: `src/earn_money/triage/__init__.py`
- Create: `src/earn_money/triage/hashing.py`
- Create: `tests/triage/__init__.py`
- Create: `tests/triage/test_hashing.py`

- [ ] **Step 1: Decide whether to add the PyPI `idna` dependency**

The spec calls for `idna.encode(..., uts46=True)`. The stdlib's `encodings.idna` only implements IDNA 2003. The practical difference for Phase 3b: UTS-46 maps a few codepoints (sharp-s ß, final-sigma ς, etc.) differently. Programs we currently triage have ASCII subdomains exclusively (see `programs/hackerone/security/scope.md` in the repo). We default to **stdlib** to keep the dependency surface minimal; if a real IDN scope appears, the 3c plan can add `idna>=3.6` and update the helper in a single small change.

Document the decision at the top of `hashing.py` so the trade-off is visible. The unit tests therefore pass on stdlib idna; if a future commit adopts PyPI idna, the tests must be re-verified.

**Risk note (Decision 4):** If a program ever adds an IDN scope (e.g. `xn--e1afmapc.xn--p1ai`), stdlib IDNA 2003 and PyPI `idna` (UTS-46) may produce different normalizations for edge-case codepoints. That would cause hash churn — existing findings would collide under a new hash — requiring a one-time migration. Track this in the 3c plan if any IDN program is onboarded.

- [ ] **Step 2: Write the failing test for `normalize_target`**

```python
# tests/triage/test_hashing.py
from __future__ import annotations

import pytest

from earn_money.triage import hashing


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Lowercase scheme + host; preserve path case.
        ("HTTPS://API.Example.COM/Path", "https://api.example.com/Path"),
        # Strip default https port.
        ("https://api.example.com:443/", "https://api.example.com/"),
        # Strip default http port.
        ("http://api.example.com:80/foo", "http://api.example.com/foo"),
        # Keep non-default ports.
        ("https://api.example.com:8443/foo", "https://api.example.com:8443/foo"),
        # Collapse duplicate slashes; resolve dot-segments; strip trailing slash.
        ("https://api.example.com//a/./b/../c/", "https://api.example.com/a/c"),
        # Root path keeps the slash.
        ("https://api.example.com/", "https://api.example.com/"),
        # Drop fragment.
        ("https://api.example.com/foo#bar", "https://api.example.com/foo"),
        # Sort query params.
        ("https://api.example.com/?b=2&a=1", "https://api.example.com/?a=1&b=2"),
        # Drop empty-value params not on the allowlist.
        ("https://api.example.com/?empty=&kept=1", "https://api.example.com/?kept=1"),
        # Keep allow-listed empty params.
        ("https://api.example.com/?debug", "https://api.example.com/?debug"),
    ],
)
def test_normalize_target_rules(raw: str, expected: str) -> None:
    assert hashing.normalize_target(raw) == expected


def test_normalize_asset_is_host_only() -> None:
    assert hashing.normalize_asset("API.Example.COM") == "api.example.com"
    # If a full URL is passed by accident, asset is the lowercased host part.
    assert hashing.normalize_asset("https://API.Example.COM/foo") == "api.example.com"


def test_normalize_target_non_url_falls_back_to_asset() -> None:
    # Some signals (raw hostname targets) have no scheme; the helper should
    # return the normalized asset rather than throw.
    assert hashing.normalize_target("API.Example.COM") == "api.example.com"
```

- [ ] **Step 3: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_hashing.py -v
```

Expected: `ModuleNotFoundError: No module named 'earn_money.triage'`.

- [ ] **Step 4: Implement `normalize_asset` + `normalize_target`**

```python
# src/earn_money/triage/__init__.py
"""Triage engine — reads recon signals and writes operator-review candidates."""
```

```python
# src/earn_money/triage/hashing.py
"""Finding-hash composition + URL/host normalization.

The hash is sha256 over a canonical string:

    v1|<platform>|<slug>|<vuln_class>|<asset>|<target>|<signature>

The hash deliberately omits run_id, evidence path, title, severity, and
timestamps so a re-observation of the same finding by a later run produces
the same hash and refreshes the existing row rather than creating a duplicate.

Normalization decisions (see spec section 4):
- Scheme + host: lowercased.
- Path: case preserved (many web servers route case-sensitively).
- IDN: encoded via stdlib `encodings.idna`. UTS-46 / PyPI `idna` is *not*
  pulled in because Phase 3b only handles ASCII hostnames; add when needed.
"""

from __future__ import annotations

import hashlib
from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urlsplit,
    urlunsplit,
)

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}
_QUERY_ALLOWLIST: frozenset[str] = frozenset({"debug", "trace"})
_HASH_VERSION = "v1"


def normalize_asset(raw: str) -> str:
    """Lowercase the host. Accepts either a bare hostname or a URL."""
    if "://" in raw:
        host = urlsplit(raw).hostname or ""
    else:
        host = raw
    return _encode_host(host)


def _encode_host(host: str) -> str:
    host = host.lower().strip(".")
    if not host:
        return ""
    # idna-encode ASCII unchanged; raises only for malformed input we then
    # let through unchanged (the caller's downstream check will drop it).
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def normalize_target(raw: str) -> str:
    """Apply normalization rules 1-7. Non-URL input collapses to ``normalize_asset``."""
    if "://" not in raw:
        return normalize_asset(raw)
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    host = _encode_host(parts.hostname or "")
    netloc = _build_netloc(scheme, host, parts.port)
    path = _normalize_path(parts.path)
    query = _normalize_query(parts.query)
    return urlunsplit((scheme, netloc, path, query, ""))  # fragment dropped


def _build_netloc(scheme: str, host: str, port: int | None) -> str:
    if port is None or port == _DEFAULT_PORTS.get(scheme):
        return host
    return f"{host}:{port}"


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    # Collapse duplicate slashes.
    while "//" in path:
        path = path.replace("//", "/")
    # Resolve . and .. segments.
    parts: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    cleaned = "/" + "/".join(parts)
    # Re-encode reserved-but-not-unreserved characters in canonical form.
    cleaned = quote(unquote(cleaned), safe="/")
    return cleaned


def _normalize_query(query: str) -> str:
    if not query:
        return ""
    pairs = parse_qsl(query, keep_blank_values=True)
    cleaned = [
        (k, v) for k, v in pairs
        if v != "" or k in _QUERY_ALLOWLIST
    ]
    cleaned.sort(key=lambda kv: (kv[0], kv[1]))
    return urlencode(cleaned)


def compute_hash(
    *,
    platform: str,
    slug: str,
    vuln_class: str,
    asset: str,
    target: str,
    signature: str,
) -> str:
    canonical = "|".join((
        _HASH_VERSION, platform, slug, vuln_class,
        normalize_asset(asset),
        normalize_target(target),
        signature,
    ))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 5: Verify the normalization tests GREEN**

```bash
.venv/bin/python -m pytest tests/triage/test_hashing.py -v
```

Expected: all 11 parametrized cases + 2 asset/non-URL tests pass.

- [ ] **Step 6: Write the failing test for `compute_hash`**

```python
# tests/triage/test_hashing.py — append
def test_compute_hash_is_stable_across_equivalent_inputs() -> None:
    a = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="API.Example.COM", target="HTTPS://API.Example.COM:443/foo#anchor",
        signature="cve-2023-1234|primary|",
    )
    b = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="api.example.com", target="https://api.example.com/foo",
        signature="cve-2023-1234|primary|",
    )
    assert a == b


def test_compute_hash_differs_when_vuln_class_differs() -> None:
    a = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="xss-reflected",
        asset="api.example.com", target="https://api.example.com/",
        signature="sig",
    )
    b = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="open-redirect",
        asset="api.example.com", target="https://api.example.com/",
        signature="sig",
    )
    assert a != b


def test_compute_hash_differs_when_signature_differs() -> None:
    a = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="x",
        asset="api.example.com", target="https://api.example.com/",
        signature="sig-a",
    )
    b = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="x",
        asset="api.example.com", target="https://api.example.com/",
        signature="sig-b",
    )
    assert a != b
```

Run + verify GREEN.

- [ ] **Step 7: Add strengthened collision-resistance tests**

Two tests replace the self-fulfilling 1k loop: one proves each field independently contributes to the hash, and one proves normalization-equivalent inputs produce the *same* hash.

```python
# tests/triage/test_hashing.py — append
def test_compute_hash_changes_on_each_field_independently() -> None:
    """Changing exactly one field must change the hash."""
    base = dict(
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="api.example.com", target="https://api.example.com/",
        signature="cve-2023-1234|primary|",
    )
    base_hash = hashing.compute_hash(**base)  # type: ignore[arg-type]
    for field in ["platform", "slug", "vuln_class", "asset", "target", "signature"]:
        variant = {**base, field: base[field] + "_x"}  # type: ignore[operator]
        assert hashing.compute_hash(**variant) != base_hash, (  # type: ignore[arg-type]
            f"hash did not change when {field!r} was mutated"
        )


def test_compute_hash_stable_across_normalization_variants() -> None:
    """Inputs that are semantically equivalent must hash to the same value."""
    canonical = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com", target="https://api.example.com/",
        signature="sig",
    )
    # Host case normalization.
    assert hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="API.Example.COM", target="https://API.Example.com:443/",
        signature="sig",
    ) == canonical
    # Default port stripping + trailing-slash semantics.
    assert hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com", target="https://api.example.com:443/",
        signature="sig",
    ) == canonical
    # Query param sort order.
    h_sorted = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com",
        target="https://api.example.com/?a=1&b=2",
        signature="sig",
    )
    assert hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com",
        target="https://api.example.com/?b=2&a=1",
        signature="sig",
    ) == h_sorted
```

Run + verify GREEN.

- [ ] **Step 8: Implement + test per-tool signature composers**

Signature composition is logic that varies per source tool. We put it next to `compute_hash` since they're conceptually one knot of canonicalization.

```python
# src/earn_money/triage/hashing.py — append

def signature_for_nuclei(
    *, template_id: str, matcher_name: str | None, extracted: str | None
) -> str:
    """nuclei signature: '<template_id>|<matcher_name>|<extracted_normalized>'.

    `matcher_name` and `extracted` are nullable in nuclei output. We coerce
    them to empty strings to keep the hash key length deterministic.
    """
    matcher = matcher_name or ""
    extracted_norm = normalize_target(extracted) if extracted else ""
    return f"{template_id}|{matcher}|{extracted_norm}"


def signature_for_httpx_anomaly(
    *, signal_type: str, old_fingerprint: str, new_fingerprint: str
) -> str:
    """httpx anomaly signature: <signal_type>|<old12>|<new12>.

    Fingerprints are sha256'd and truncated so noise in jittery headers
    (timestamps, request IDs) doesn't propagate to the dedup key.
    """
    return (
        f"{signal_type}|"
        f"{_short_hash(old_fingerprint)}|"
        f"{_short_hash(new_fingerprint)}"
    )


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
```

Tests:

```python
# tests/triage/test_hashing.py — append
def test_signature_for_nuclei_normalizes_extracted() -> None:
    sig = hashing.signature_for_nuclei(
        template_id="cve-2023-1234",
        matcher_name="status-200",
        extracted="HTTPS://API.Example.COM/Foo",
    )
    assert sig == "cve-2023-1234|status-200|https://api.example.com/Foo"


def test_signature_for_nuclei_handles_missing_fields() -> None:
    sig = hashing.signature_for_nuclei(
        template_id="cve-x", matcher_name=None, extracted=None
    )
    assert sig == "cve-x||"


def test_signature_for_httpx_anomaly_hashes_fingerprints() -> None:
    sig = hashing.signature_for_httpx_anomaly(
        signal_type="server_changed",
        old_fingerprint="nginx/1.18",
        new_fingerprint="nginx/1.20",
    )
    parts = sig.split("|")
    assert parts[0] == "server_changed"
    assert len(parts[1]) == 12
    assert len(parts[2]) == 12
    assert parts[1] != parts[2]
```

Run + verify GREEN.

- [ ] **Step 9: Lint**

```bash
make lint
```

Expected: ruff + mypy clean.

- [ ] **Step 10: Commit**

```bash
git add src/earn_money/triage/__init__.py src/earn_money/triage/hashing.py \
        tests/triage/__init__.py tests/triage/test_hashing.py
git commit -m "feat: finding-hash helper with normalization + per-tool signatures"
```

---

## Task 3: Findings DAO

Pure-data layer over the v3 `findings` table. The DAO owns INSERT-or-update of non-state fields. State changes go through `transition_state` (Task 4) — the DAO refuses to let callers write `current_state` directly.

The shape:

- `Finding` dataclass with the full v3 column set.
- `upsert_finding(conn, f)` — insert if new; if exists, refresh `last_seen`, increment `occurrence_count`, update `evidence_path`/`title`/`severity_hint`/`confidence` only when the new values are non-default and the row's state is not terminal. Never touches `current_state`.
- `find_by_hash(conn, finding_hash) -> Finding | None`.
- `findings_in_state(conn, *, platform, slug, state) -> list[Finding]`.

**Files:**
- Create: `src/earn_money/triage/findings.py`
- Create: `tests/triage/test_findings.py`

- [ ] **Step 1: Write the failing test (insert + read back)**

```python
# tests/triage/test_findings.py
from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.triage import findings


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def _seed_finding(**overrides: object) -> findings.Finding:
    base = dict(
        finding_hash="h1",
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="api.example.com", target="https://api.example.com/",
        signature="cve-2023-1234|primary|",
        title="CVE-2023-1234 hit on api.example.com",
        severity_hint="medium", confidence=70,
        source_tool="nuclei", source_run_id="r1",
        evidence_path="recon/outputs/.../raw.jsonl",
        notes_path="findings/_queue/h1.md",
        first_seen="2026-05-12T05:00:00Z",
        last_seen="2026-05-12T05:00:00Z",
        occurrence_count=1,
        current_state="queued",
        state_changed_at="2026-05-12T05:00:00Z",
        external_report_id=None, payout_amount=None, payout_currency=None,
    )
    base.update(overrides)
    return findings.Finding(**base)  # type: ignore[arg-type]


def test_upsert_inserts_new_finding(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    findings.upsert_finding(conn, _seed_finding())
    row = findings.find_by_hash(conn, "h1")
    assert row is not None
    assert row.title == "CVE-2023-1234 hit on api.example.com"
    assert row.current_state == "queued"
    assert row.occurrence_count == 1
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_findings.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `Finding` + the DAO**

```python
# src/earn_money/triage/findings.py
"""DAO for the v3 `findings` table.

The DAO is deliberately state-immutable: callers cannot pass a new
`current_state` through `upsert_finding`. State changes go through
`earn_money.triage.history.transition_state` which writes an audit row
inside the same transaction as the state UPDATE.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


_TERMINAL_STATES: frozenset[str] = frozenset({
    "resolved_paid", "resolved_dupe", "resolved_na",
    "resolved_info", "archived",
})


@dataclass(frozen=True)
class Finding:
    finding_hash: str
    platform: str
    slug: str
    vuln_class: str
    asset: str
    target: str
    signature: str
    title: str
    severity_hint: str
    confidence: int
    source_tool: str
    source_run_id: str
    evidence_path: str
    notes_path: str
    first_seen: str
    last_seen: str
    occurrence_count: int
    current_state: str
    state_changed_at: str
    external_report_id: str | None
    payout_amount: str | None
    payout_currency: str | None


_SELECT_COLUMNS = (
    "finding_hash, platform, slug, vuln_class, asset, target, signature, "
    "title, severity_hint, confidence, source_tool, source_run_id, "
    "evidence_path, notes_path, first_seen, last_seen, occurrence_count, "
    "current_state, state_changed_at, external_report_id, "
    "payout_amount, payout_currency"
)


def upsert_finding(conn: sqlite3.Connection, f: Finding) -> None:
    """Insert a new finding, or refresh `last_seen`, increment
    `occurrence_count`, and update evidence/title/severity_hint/confidence
    on an existing non-terminal row. Never mutates `current_state`.

    Runtime guards (enforcing the human gate in code, not just convention):
    - New rows may only be created with `current_state='queued'`.
    - Existing rows refuse a state change — use `transition_state()` instead.
    """
    existing = find_by_hash(conn, f.finding_hash)
    if existing is None:
        # New row — triage may only create `queued` rows.
        if f.current_state != "queued":
            raise ValueError(
                f"upsert_finding refuses to create finding "
                f"{f.finding_hash!r} with state={f.current_state!r}; "
                f"only 'queued' is allowed for new rows."
            )
        _insert(conn, f)
        return
    # Existing row — must not silently change current_state.
    if f.current_state != existing.current_state:
        raise ValueError(
            f"upsert_finding refuses to change current_state on "
            f"existing finding {f.finding_hash!r}: "
            f"{existing.current_state!r} -> {f.current_state!r}. "
            f"Use transition_state() to advance state."
        )
    if existing.current_state in _TERMINAL_STATES:
        # Terminal findings are immutable from triage's perspective.
        return
    conn.execute(
        "UPDATE findings SET "
        "last_seen = ?, occurrence_count = occurrence_count + 1, "
        "evidence_path = ?, title = ?, severity_hint = ?, confidence = ? "
        "WHERE finding_hash = ?",
        (
            f.last_seen, f.evidence_path, f.title, f.severity_hint,
            f.confidence, f.finding_hash,
        ),
    )
    conn.commit()


def _insert(conn: sqlite3.Connection, f: Finding) -> None:
    conn.execute(
        f"INSERT INTO findings ({_SELECT_COLUMNS}) VALUES ("
        + ", ".join("?" * 22) + ")",
        (
            f.finding_hash, f.platform, f.slug, f.vuln_class, f.asset, f.target,
            f.signature, f.title, f.severity_hint, f.confidence,
            f.source_tool, f.source_run_id, f.evidence_path, f.notes_path,
            f.first_seen, f.last_seen, f.occurrence_count,
            f.current_state, f.state_changed_at,
            f.external_report_id, f.payout_amount, f.payout_currency,
        ),
    )
    conn.commit()


def find_by_hash(conn: sqlite3.Connection, finding_hash: str) -> Finding | None:
    cursor = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM findings WHERE finding_hash = ?",
        (finding_hash,),
    )
    row = cursor.fetchone()
    return Finding(*row) if row is not None else None


def findings_in_state(
    conn: sqlite3.Connection, *, platform: str, slug: str, state: str
) -> list[Finding]:
    cursor = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM findings "
        "WHERE platform = ? AND slug = ? AND current_state = ? "
        "ORDER BY first_seen",
        (platform, slug, state),
    )
    return [Finding(*row) for row in cursor]
```

- [ ] **Step 4: Verify the insert test GREEN**

```bash
.venv/bin/python -m pytest tests/triage/test_findings.py -v
```

- [ ] **Step 5: Add the "re-upsert refreshes seen" test**

```python
# tests/triage/test_findings.py — append
def test_re_upsert_refreshes_last_seen_and_increments_count(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    findings.upsert_finding(conn, _seed_finding())
    refreshed = _seed_finding(
        last_seen="2026-05-13T05:00:00Z",
        title="CVE-2023-1234 hit on api.example.com (re-observed)",
        confidence=80,
    )
    findings.upsert_finding(conn, refreshed)
    row = findings.find_by_hash(conn, "h1")
    assert row is not None
    assert row.occurrence_count == 2
    assert row.last_seen == "2026-05-13T05:00:00Z"
    assert row.title.endswith("(re-observed)")
    assert row.confidence == 80
    # current_state must NOT have moved.
    assert row.current_state == "queued"


def test_re_upsert_on_terminal_finding_is_noop(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    findings.upsert_finding(
        conn,
        _seed_finding(current_state="resolved_dupe", occurrence_count=1),
    )
    # Triage tries to refresh a resolved finding (a stale signal arrives).
    findings.upsert_finding(
        conn,
        _seed_finding(last_seen="2026-06-01T05:00:00Z"),
    )
    row = findings.find_by_hash(conn, "h1")
    assert row is not None
    # No mutation.
    assert row.last_seen == "2026-05-12T05:00:00Z"
    assert row.occurrence_count == 1
```

Run + verify GREEN.

- [ ] **Step 6: Add `findings_in_state` test**

```python
# tests/triage/test_findings.py — append
def test_findings_in_state_filters_by_program_and_state(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    findings.upsert_finding(conn, _seed_finding(
        finding_hash="h1", current_state="queued",
    ))
    findings.upsert_finding(conn, _seed_finding(
        finding_hash="h2", current_state="verified",
    ))
    findings.upsert_finding(conn, _seed_finding(
        finding_hash="h3", platform="hackerone", slug="other",
        current_state="queued",
    ))
    queued = findings.findings_in_state(
        conn, platform="hackerone", slug="example", state="queued"
    )
    assert [f.finding_hash for f in queued] == ["h1"]
```

Run + verify GREEN.

- [ ] **Step 6b: Add the B4 state-guard tests**

```python
# tests/triage/test_findings.py — append
def test_upsert_refuses_new_finding_with_non_queued_state(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    import pytest
    with pytest.raises(ValueError, match="only 'queued' is allowed for new rows"):
        findings.upsert_finding(conn, _seed_finding(current_state="verified"))


def test_upsert_refuses_state_change_on_existing_finding(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    # Insert in queued state.
    findings.upsert_finding(conn, _seed_finding(current_state="queued"))
    # Re-upsert with a different state — must raise.
    import pytest
    with pytest.raises(ValueError, match="Use transition_state()"):
        findings.upsert_finding(conn, _seed_finding(current_state="verified"))
```

Run + verify GREEN.

- [ ] **Step 7: Lint**

```bash
make lint
```

- [ ] **Step 8: Commit**

```bash
git add src/earn_money/triage/findings.py tests/triage/test_findings.py
git commit -m "feat: findings DAO with state-immutable upsert + lookup helpers"
```

---

## Task 4: State-history DAO + `transition_state`

Three things live here:

1. The append-only `findings_state_history` audit table (already created by the migration in Task 1).
2. `transition_state(conn, *, finding_hash, to_state, actor, note, now)` — updates `findings.current_state` and `findings.state_changed_at`, AND writes an audit row, INSIDE A SINGLE TRANSACTION.
3. `IllegalStateTransition` exception raised when the transition is not in the allowed set.

Allowed transitions (spec section 4):

- `queued -> verified`
- `queued -> resolved_dupe`
- `queued -> resolved_na`
- `queued -> resolved_info`
- `verified -> submitted`
- `submitted -> resolved_paid`
- `submitted -> resolved_dupe`
- `submitted -> resolved_na`
- `submitted -> resolved_info`
- Any `resolved_*` → `archived`

Note: triage does **not** call `transition_state`. The two human gates (`_queue → _verified` and `_verified → _submitted`) are the only callers. We ship `transition_state` in Phase 3b so the state machine is in place when Phase 4 wires up `bin/submit`, but no current code path invokes it — except the tests.

**Files:**
- Create: `src/earn_money/triage/history.py`
- Create: `tests/triage/test_history.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/triage/test_history.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import db
from earn_money.triage import findings, history


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def _seed_queued(conn: sqlite3.Connection) -> None:
    findings.upsert_finding(conn, findings.Finding(
        finding_hash="h1", platform="hackerone", slug="example",
        vuln_class="cve-x", asset="api.example.com",
        target="https://api.example.com/",
        signature="sig", title="t", severity_hint="medium", confidence=60,
        source_tool="nuclei", source_run_id="r1",
        evidence_path="e", notes_path="findings/_queue/h1.md",
        first_seen="2026-05-12T05:00:00Z",
        last_seen="2026-05-12T05:00:00Z",
        occurrence_count=1, current_state="queued",
        state_changed_at="2026-05-12T05:00:00Z",
        external_report_id=None, payout_amount=None, payout_currency=None,
    ))


def test_transition_queued_to_verified_succeeds(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    _seed_queued(conn)
    history.transition_state(
        conn, finding_hash="h1", to_state="verified",
        actor="operator", note="Manually validated; reflected on /search",
        now="2026-05-13T09:00:00Z",
    )
    f = findings.find_by_hash(conn, "h1")
    assert f is not None
    assert f.current_state == "verified"
    assert f.state_changed_at == "2026-05-13T09:00:00Z"
    audit = history.state_history_for_hash(conn, "h1")
    assert [(a.from_state, a.to_state, a.actor) for a in audit] == [
        ("queued", "verified", "operator"),
    ]


def test_illegal_transition_raises(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    _seed_queued(conn)
    with pytest.raises(history.IllegalStateTransition):
        history.transition_state(
            conn, finding_hash="h1", to_state="resolved_paid",
            actor="operator", note="oops", now="t",
        )


def test_illegal_transition_does_not_partially_apply(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    _seed_queued(conn)
    with pytest.raises(history.IllegalStateTransition):
        history.transition_state(
            conn, finding_hash="h1", to_state="resolved_paid",
            actor="operator", note="oops", now="t",
        )
    f = findings.find_by_hash(conn, "h1")
    assert f is not None
    assert f.current_state == "queued"
    audit = history.state_history_for_hash(conn, "h1")
    assert audit == []


def test_missing_finding_raises(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    with pytest.raises(history.FindingNotFound):
        history.transition_state(
            conn, finding_hash="missing", to_state="verified",
            actor="operator", note="x", now="t",
        )
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_history.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `history.py`**

```python
# src/earn_money/triage/history.py
"""Finding state-machine transitions + append-only audit DAO.

Triage NEVER calls these helpers. The only callers in Phase 3b are tests;
Phase 4's `bin/submit` and the queue→verified operator workflow will
become the production callers. We ship the helper now so the state
machine is enforced from day one rather than retrofitted later.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


class IllegalStateTransition(Exception):
    """Raised when the requested (from_state, to_state) pair is not allowed."""


class FindingNotFound(Exception):
    """Raised when the target finding_hash is not present in the DB."""


@dataclass(frozen=True)
class StateChange:
    id: int
    finding_hash: str
    from_state: str | None
    to_state: str
    actor: str
    note: str | None
    changed_at: str


_ALLOWED: frozenset[tuple[str, str]] = frozenset({
    ("queued", "verified"),
    ("queued", "resolved_dupe"),
    ("queued", "resolved_na"),
    ("queued", "resolved_info"),
    ("verified", "submitted"),
    ("submitted", "resolved_paid"),
    ("submitted", "resolved_dupe"),
    ("submitted", "resolved_na"),
    ("submitted", "resolved_info"),
    # Retention paths.
    ("resolved_paid", "archived"),
    ("resolved_dupe", "archived"),
    ("resolved_na", "archived"),
    ("resolved_info", "archived"),
})


def transition_state(
    conn: sqlite3.Connection,
    *,
    finding_hash: str,
    to_state: str,
    actor: str,
    note: str | None,
    now: str,
) -> None:
    """Update findings.current_state AND write a history row atomically."""
    row = conn.execute(
        "SELECT current_state FROM findings WHERE finding_hash = ?",
        (finding_hash,),
    ).fetchone()
    if row is None:
        raise FindingNotFound(finding_hash)
    from_state = row[0]
    if (from_state, to_state) not in _ALLOWED:
        raise IllegalStateTransition(
            f"{from_state!r} -> {to_state!r} is not an allowed transition"
        )
    conn.execute("BEGIN")
    try:
        conn.execute(
            "UPDATE findings SET current_state = ?, state_changed_at = ? "
            "WHERE finding_hash = ?",
            (to_state, now, finding_hash),
        )
        conn.execute(
            "INSERT INTO findings_state_history "
            "(finding_hash, from_state, to_state, actor, note, changed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (finding_hash, from_state, to_state, actor, note, now),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def state_history_for_hash(
    conn: sqlite3.Connection, finding_hash: str
) -> list[StateChange]:
    cursor = conn.execute(
        "SELECT id, finding_hash, from_state, to_state, actor, note, changed_at "
        "FROM findings_state_history WHERE finding_hash = ? "
        "ORDER BY id",
        (finding_hash,),
    )
    return [StateChange(*row) for row in cursor]
```

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/triage/test_history.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Add a multi-step happy path test**

```python
# tests/triage/test_history.py — append
def test_queued_verified_submitted_resolved_paid(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    _seed_queued(conn)
    history.transition_state(
        conn, finding_hash="h1", to_state="verified",
        actor="operator", note=None, now="t1",
    )
    history.transition_state(
        conn, finding_hash="h1", to_state="submitted",
        actor="operator", note=None, now="t2",
    )
    history.transition_state(
        conn, finding_hash="h1", to_state="resolved_paid",
        actor="operator", note="Bounty paid: $250", now="t3",
    )
    f = findings.find_by_hash(conn, "h1")
    assert f is not None
    assert f.current_state == "resolved_paid"
    history_rows = history.state_history_for_hash(conn, "h1")
    assert [h.to_state for h in history_rows] == [
        "verified", "submitted", "resolved_paid"
    ]
```

Run + verify GREEN.

- [ ] **Step 6: Lint**

```bash
make lint
```

- [ ] **Step 7: Commit**

```bash
git add src/earn_money/triage/history.py tests/triage/test_history.py
git commit -m "feat: finding state-machine with append-only audit history"
```

---

## Task 5: nuclei tool wrapper

Thin subprocess wrapper around the `nuclei` CLI. Two surfaces:

1. `build_command(targets, *, template_dirs)` — validates `template_dirs` against `APPROVED_TEMPLATE_DIRS` and returns argv. Raises `UnsafeTemplateProfile` if any directory is not approved.
2. `parse_jsonl(raw, *, run_id, observed_at)` — parses nuclei's JSONL output (`-jsonl -silent`) into a `list[Signal]` where `signal_type="template_match"`.

Approved template directories (per CLAUDE.md hard rule: "CVE + standard misconfiguration only"):

- `cves/` — CVE proof checks
- `misconfiguration/` — server misconfiguration checks

All other directories are explicitly **not** approved for Phase 3b. Rationale:

- `default-logins/` — auth probing risk on programs that haven't authorised brute-force
- `technologies/` — fingerprinting noise that doesn't carry vuln signal
- `vulnerabilities/` — catch-all dir mixes vetted with experimental templates
- `exposures/` — data-leak templates include some that fetch and exfiltrate content
- `dast/` — would actively fuzz; out of scope for Phase 3b
- `fuzzing/` — same
- `dos/` — never
- `cnvd/` — Chinese vuln DB; rarely curated, occasionally noisy
- Custom paid templates (nuclei-templates-pro and similar)

If a future operator wants more directories, they must explicitly extend `APPROVED_TEMPLATE_DIRS` in `nuclei_tool.py` after a manual policy review; that edit then becomes a code-review event.

The runner passes each approved dir via `-t <dir>` rather than `-tags` because tag filtering is opaque and depends on template metadata; directory inclusion is a hard, auditable bound.

Safety flags on the command line:

- `-disable-redirects` (spec section 3 per-request scope enforcement)
- `-jsonl` (machine-readable output)
- `-silent` (suppress progress bar)
- `-no-color`
- `-omit-template` (the wrapper rebuilds template references from `template-id`; the full template body is in our committed template dir and doesn't need to ride along in every signal)
- `-no-interactsh` (we do not run an interactsh server; the wrapper must not rely on out-of-band callbacks)
- `-disable-update-check` (no internet template-pull at scan time)

Per spec: nuclei templates must be **pre-installed on the VPS**. The wrapper does not invoke `-update-templates` and refuses to scan if the approved template dirs are absent.

**Files:**
- Create: `src/earn_money/recon/nuclei_tool.py`
- Create: `tests/recon/test_nuclei_tool.py`
- Create: `tests/fixtures/nuclei_output.jsonl`

- [ ] **Step 1: Add the JSONL fixture**

```
# tests/fixtures/nuclei_output.jsonl
{"template-id":"http-missing-security-headers","matcher-name":"strict-transport-security","matcher-status":true,"info":{"name":"HTTP Missing Security Headers","severity":"info","tags":["misconfig","headers"]},"host":"https://api.example.com","matched-at":"https://api.example.com/","extracted-results":[],"timestamp":"2026-05-12T02:15:00Z"}
{"template-id":"CVE-2023-1234","matcher-name":"primary","matcher-status":true,"info":{"name":"Acme Web App SQLi","severity":"high","tags":["cve","cve2023","sqli"]},"host":"https://api.example.com","matched-at":"https://api.example.com/search?q=foo","extracted-results":["mysql 8.0.32"],"timestamp":"2026-05-12T02:16:00Z"}
{"template-id":"http-default-creds","matcher-name":"admin-admin","matcher-status":true,"info":{"name":"Default admin/admin","severity":"high","tags":["default-login"]},"host":"https://app.example.com","matched-at":"https://app.example.com/login","extracted-results":[],"timestamp":"2026-05-12T02:17:00Z"}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/recon/test_nuclei_tool.py
from __future__ import annotations

from pathlib import Path

import pytest

from earn_money.recon import nuclei_tool


def test_approved_template_dirs_constant_locked() -> None:
    """The approved set is the safety boundary — any change must be a
    conscious code-review event, not an accidental one. We freeze it
    here so a stray edit breaks the test.

    Only CVE and misconfiguration directories are approved for Phase 3b.
    See nuclei_tool.py for the full rationale on why other dirs are excluded.
    """
    assert nuclei_tool.APPROVED_TEMPLATE_DIRS == frozenset({
        "cves",
        "misconfiguration",
    })


def test_build_command_includes_safety_flags() -> None:
    cmd = nuclei_tool.build_command(
        ["https://api.example.com/"],
        template_dirs=("cves", "misconfiguration"),
    )
    assert "-disable-redirects" in cmd
    assert "-jsonl" in cmd
    assert "-silent" in cmd
    assert "-no-interactsh" in cmd
    assert "-disable-update-check" in cmd
    assert "-t" in cmd
    # Both template dirs appear with -t.
    t_indices = [i for i, a in enumerate(cmd) if a == "-t"]
    t_values = [cmd[i + 1] for i in t_indices]
    assert set(t_values) == {"cves", "misconfiguration"}


def test_build_command_includes_rate_and_concurrency_caps() -> None:
    """B3: nuclei must never run without per-request rate and concurrency limits."""
    cmd = nuclei_tool.build_command(
        ["https://api.example.com/"],
        template_dirs=("cves",),
    )
    assert "-rl" in cmd
    assert cmd[cmd.index("-rl") + 1] == "10"
    assert "-c" in cmd
    assert cmd[cmd.index("-c") + 1] == "10"
    assert "-bs" in cmd
    assert cmd[cmd.index("-bs") + 1] == "10"
    assert "-stats-interval" in cmd
    assert cmd[cmd.index("-stats-interval") + 1] == "60"


def test_build_command_passes_targets_via_u() -> None:
    cmd = nuclei_tool.build_command(
        ["https://api.example.com/", "https://www.example.com/"],
        template_dirs=("cves",),
    )
    assert "-u" in cmd
    u_index = cmd.index("-u")
    assert cmd[u_index + 1] == "https://api.example.com/,https://www.example.com/"


def test_build_command_rejects_unapproved_template_dir() -> None:
    with pytest.raises(nuclei_tool.UnsafeTemplateProfile):
        nuclei_tool.build_command(
            ["https://api.example.com/"],
            template_dirs=("cves", "dos"),
        )


def test_build_command_empty_targets_raises() -> None:
    with pytest.raises(ValueError):
        nuclei_tool.build_command([], template_dirs=("cves",))


def test_parse_jsonl_returns_signals(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "nuclei_output.jsonl").read_text(encoding="utf-8")
    signals = nuclei_tool.parse_jsonl(raw, run_id="r1", observed_at="2026-05-12T02:30:00Z")
    assert len(signals) == 3
    cve = next(s for s in signals if "CVE-2023-1234" in s.signature)
    assert cve.signal_type == "template_match"
    assert cve.asset == "api.example.com"
    assert cve.target == "https://api.example.com/search?q=foo"
    # Signature follows the composer in hashing.signature_for_nuclei.
    assert cve.signature.startswith("CVE-2023-1234|primary|")


def test_parse_jsonl_skips_malformed_lines(fixtures_dir: Path) -> None:
    raw = "not json\n" + (fixtures_dir / "nuclei_output.jsonl").read_text(encoding="utf-8")
    signals = nuclei_tool.parse_jsonl(raw, run_id="r1", observed_at="t")
    assert len(signals) == 3


def test_parse_jsonl_payload_carries_severity_and_template(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "nuclei_output.jsonl").read_text(encoding="utf-8")
    signals = nuclei_tool.parse_jsonl(raw, run_id="r1", observed_at="t")
    import json
    cve = next(s for s in signals if "CVE-2023-1234" in s.signature)
    payload = json.loads(cve.payload)
    assert payload["template_id"] == "CVE-2023-1234"
    assert payload["severity"] == "high"
    assert payload["matched_at"] == "https://api.example.com/search?q=foo"
```

- [ ] **Step 3: Verify RED**

```bash
.venv/bin/python -m pytest tests/recon/test_nuclei_tool.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement the wrapper**

```python
# src/earn_money/recon/nuclei_tool.py
"""Subprocess wrapper around the ProjectDiscovery `nuclei` CLI.

This wrapper is the safety boundary for nuclei. It refuses to build a
command that includes unapproved template directories (DoS, fuzzing,
DAST, paid templates), and it forces the safety flags on every
invocation (`-disable-redirects`, `-no-interactsh`,
`-disable-update-check`).

Template directories are passed as `-t <name>`. nuclei resolves them
against its local template root (~/.nuclei-templates on the VPS).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from earn_money.recon.signals import Signal
from earn_money.triage import hashing


APPROVED_TEMPLATE_DIRS: frozenset[str] = frozenset({
    "cves",
    "misconfiguration",
})


class UnsafeTemplateProfile(Exception):
    """Raised when build_command is asked to use an unapproved template dir."""


def build_command(
    targets: Sequence[str], *, template_dirs: Sequence[str],
) -> list[str]:
    if not targets:
        raise ValueError("build_command requires at least one target")
    unapproved = set(template_dirs) - APPROVED_TEMPLATE_DIRS
    if unapproved:
        raise UnsafeTemplateProfile(
            f"refusing to invoke nuclei with unapproved template "
            f"directories: {sorted(unapproved)}. "
            f"Approved: {sorted(APPROVED_TEMPLATE_DIRS)}"
        )
    argv: list[str] = [
        "nuclei",
        "-u", ",".join(targets),
        "-jsonl",
        "-silent",
        "-no-color",
        "-disable-redirects",
        "-no-interactsh",
        "-disable-update-check",
        # Rate / concurrency caps (B3 — prevent nuclei from saturating the target).
        "-rl", "10",           # max requests per second
        "-c", "10",            # max concurrent templates
        "-bs", "10",           # max concurrent hosts per template run
        "-stats-interval", "60",  # log progress at 60-second intervals
    ]
    for d in template_dirs:
        argv.extend(["-t", d])
    return argv


def parse_jsonl(
    raw: str, *, run_id: str, observed_at: str
) -> list[Signal]:
    """Parse nuclei's JSONL output into Signal rows.

    Each match becomes one Signal with `signal_type="template_match"`.
    Malformed lines are silently skipped — the runner counts source
    failures separately if it cares.
    """
    out: list[Signal] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            out.append(_to_signal(data, run_id=run_id, observed_at=observed_at))
        except (KeyError, ValueError):
            continue
    return out


def _to_signal(
    data: dict[str, Any], *, run_id: str, observed_at: str
) -> Signal:
    template_id = str(data["template-id"])
    matcher_name = data.get("matcher-name") or None
    matched_at = str(data.get("matched-at") or data.get("host") or "")
    extracted_list = data.get("extracted-results") or []
    extracted = extracted_list[0] if extracted_list else None
    info = data.get("info") or {}
    severity = str(info.get("severity") or "unknown")
    name = str(info.get("name") or template_id)

    asset = hashing.normalize_asset(matched_at)
    target = hashing.normalize_target(matched_at)
    signature = hashing.signature_for_nuclei(
        template_id=template_id, matcher_name=matcher_name, extracted=extracted,
    )
    payload = json.dumps({
        "template_id": template_id,
        "matcher_name": matcher_name,
        "matched_at": matched_at,
        "severity": severity,
        "name": name,
        "extracted": extracted,
    }, sort_keys=True)

    return Signal(
        run_id=run_id, tool="nuclei", signal_type="template_match",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
```

- [ ] **Step 5: Verify the tests GREEN**

```bash
.venv/bin/python -m pytest tests/recon/test_nuclei_tool.py -v
make lint
```

Expected: 8 passed; lint clean.

- [ ] **Step 6: Commit**

```bash
git add src/earn_money/recon/nuclei_tool.py tests/recon/test_nuclei_tool.py \
        tests/fixtures/nuclei_output.jsonl
git commit -m "feat: nuclei tool wrapper with safety flags + approved templates"
```

---

## Task 6: nuclei runner

Mirrors `httpx_probe.run_program` but reads targets from `http_services` (latest scoped roots from 3a) and writes `Signal` rows + raw artifact instead of `HttpService` rows.

Key contract differences from httpx:

1. **Prereq freshness.** Per spec section 7, "Each downstream runner ... must independently query SQLite for a recent successful prerequisite `recon_runs` row before doing work. If the prereq is stale or missing, the runner records a `prereq_missing` anomaly signal and exits cleanly." The nuclei runner therefore:
   - Queries `recon_runs` for the most recent `tool='httpx'` row with `status IN ('success', 'partial')` and `finished_at > now - 24h`.
   - If none, writes a single `Signal(signal_type='prereq_missing', ...)` row, marks `recon_runs.status='skipped'` with `error_summary='no recent httpx run'`, and returns.

2. **Targets are URLs, not bare hostnames.** We read `http_services.url` (the canonical root URL).

3. **Signal output.** Each nuclei JSONL match becomes one `Signal` row; the wrapper additionally re-filters every emitted signal through `scope.is_in_scope(asset, ...)` and drops OOS signals, incrementing `recon_runs.oos_drops`.

4. **Artifact directory.** `recon/outputs/<platform>/<slug>/nuclei/<YYYY-MM-DD>/<run_id>/`. The runner writes `manifest.json` + `signals.jsonl` (per spec section 3 "Shared Artifact Contract"; the JSONL is a write-then-reconcile artifact, the DB rows are authoritative).

The runner stays under the 200-line cap by keeping `main()` and `_build_real_tool` in this file (httpx_probe.py is ~200 lines including both; copying that shape gives us the same room here).

**Files:**
- Create: `src/earn_money/runners/nuclei_scan.py`
- Create: `tests/runners/test_nuclei_scan.py`

- [ ] **Step 1: Write the failing test (gate refusal)**

```python
# tests/runners/test_nuclei_scan.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, flags, policy, scope
from earn_money.recon import services, signals
from earn_money.runners import active, nuclei_scan


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"],
        out_of_scope=out_of_scope or [],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx_run_and_services(
    paths: config.Paths, *, services_to_insert: list[services.HttpService]
) -> None:
    """Seed a fresh successful httpx run + matching http_services rows so
    nuclei can see a recent prereq."""
    from earn_money.recon import runs
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=len(services_to_insert),
            signal_count=0, source_failures=0, oos_drops=0,
        )
        for svc in services_to_insert:
            services.upsert_service(conn, svc)
    finally:
        conn.close()


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    with pytest.raises(flags.ReconDisabled):
        nuclei_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(services=[]),
        )


def test_refuses_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only")
    with pytest.raises(policy.PolicyViolation):
        nuclei_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(services=[]),
        )
```

The injected `tool_run` for nuclei returns a different shape than httpx — it returns a list of `Signal` rows. We extend `active.ToolRunResult` to carry a generic `services` field for both runners; in the nuclei case we treat that field as `list[Signal]` rather than `list[HttpService]`. The existing `Any` type on `ActiveRunResult.ToolRunResult.services` already allows this. The runner casts after retrieval.

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_nuclei_scan.py -v
```

Expected: ModuleNotFoundError on `nuclei_scan`.

- [ ] **Step 3: Implement the runner**

```python
# src/earn_money/runners/nuclei_scan.py
"""Template-based vulnerability scan runner.

Mirrors httpx_probe but reads targets from `http_services` (the canonical
service inventory from Phase 3a) and writes `Signal` rows instead of
`HttpService` rows. Every emitted signal is re-checked against the
program's scope (`oos_drops` counts the rejects).

Per spec section 7, the runner refuses to scan if there is no recent
successful httpx run (prereq freshness check). The refusal is graceful:
a `prereq_missing` Signal is written and the recon_runs row is marked
`status='skipped'`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from urllib.parse import urlparse

from earn_money import config, db, flags, policy, scope
from earn_money.recon import runs, signals
from earn_money.recon.signals import Signal
from earn_money.runners import active

ToolRun = Callable[[list[str]], active.ToolRunResult]

_PREREQ_FRESHNESS_HOURS = 24
_APPROVED_TEMPLATE_DIRS: tuple[str, ...] = (
    "cves",
    "misconfiguration",
)


def _target_host(target: str, fallback: str) -> str:
    """Extract the hostname from a URL for OOS checking (B1).

    If `target` has no scheme or cannot be parsed, fall back to `fallback`
    (typically `sig.asset`) so callers get a consistent non-empty string.
    """
    if "://" in target:
        return urlparse(target).hostname or fallback
    return fallback


def _load_in_scope_service_urls(
    conn: sqlite3.Connection, s: scope.Scope
) -> list[str]:
    cursor = conn.execute(
        "SELECT url, subdomain FROM http_services "
        "WHERE in_scope_at_observation = 1 ORDER BY subdomain, scheme, port"
    )
    return [
        url for url, subdomain in cursor
        if scope.is_in_scope(subdomain, s.in_scope, s.out_of_scope)
    ]


def _recent_httpx_success(
    conn: sqlite3.Connection, *, platform: str, slug: str, now: datetime,
) -> bool:
    cutoff = (now - timedelta(hours=_PREREQ_FRESHNESS_HOURS)).isoformat(timespec="seconds")
    row = conn.execute(
        "SELECT 1 FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND tool = 'httpx' AND status IN ('success', 'partial') "
        "AND finished_at IS NOT NULL AND finished_at >= ? LIMIT 1",
        (platform, slug, cutoff),
    ).fetchone()
    return row is not None


def _write_manifest(artifact_dir: Path, payload: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_signals_jsonl(artifact_dir: Path, sigs: list[Signal]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with (artifact_dir / "signals.jsonl").open("w", encoding="utf-8") as fh:
        for s in sigs:
            fh.write(json.dumps({
                "tool": s.tool, "signal_type": s.signal_type,
                "asset": s.asset, "target": s.target,
                "signature": s.signature, "payload": s.payload,
                "observed_at": s.observed_at,
            }) + "\n")


def _write_required_artifacts(
    artifact_dir: Path,
    *,
    targets: list[str],
    raw_stdout: str,
    raw_stderr: str,
) -> None:
    """P1.2: write the three required Shared Artifact Contract files.

    Every nuclei run dir must contain:
    - input.txt  — newline-separated target URLs fed to nuclei
    - raw.jsonl  — captured stdout (nuclei JSONL output before parsing)
    - stderr.txt — captured stderr
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "input.txt").write_text(
        "\n".join(targets) + ("\n" if targets else ""), encoding="utf-8"
    )
    (artifact_dir / "raw.jsonl").write_text(raw_stdout, encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(raw_stderr, encoding="utf-8")


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_run: ToolRun,
    run_id: str | None = None,
) -> active.ActiveRunResult:
    s = active.check_gates(paths, platform, slug, mode="active")

    run_id = run_id or uuid.uuid4().hex
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat(timespec="seconds")
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/nuclei/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        if not _recent_httpx_success(conn, platform=platform, slug=slug, now=now_dt):
            return _record_prereq_missing(
                conn, paths, platform, slug, run_id, now, artifact_dir,
            )

        targets = _load_in_scope_service_urls(conn, s)
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="nuclei",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )

        try:
            tool_result = (
                tool_run(targets) if targets
                else active.ToolRunResult(services=[])
            )
        except Exception as exc:
            finished = datetime.now(UTC).isoformat(timespec="seconds")
            runs.finish_run(
                conn, run_id=run_id, finished_at=finished, status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        raw_signals: list[Signal] = tool_result.services
        # B1: check BOTH sig.asset (the host nuclei probed) AND sig.target
        # (the actual matched URL, which may redirect to an OOS host).
        in_scope_signals = [
            sig for sig in raw_signals
            if scope.is_in_scope(sig.asset, s.in_scope, s.out_of_scope)
            and scope.is_in_scope(
                _target_host(sig.target, sig.asset), s.in_scope, s.out_of_scope
            )
        ]
        oos_drops = len(raw_signals) - len(in_scope_signals)

        if in_scope_signals:
            signals.insert_signals(conn, in_scope_signals)
        _write_signals_jsonl(artifact_dir, in_scope_signals)
        # P1.2: write the three required Shared Artifact Contract files.
        # raw_stdout / raw_stderr are threaded from the tool_run result;
        # ToolRunResult carries them as optional str fields (default "").
        _write_required_artifacts(
            artifact_dir,
            targets=targets,
            raw_stdout=getattr(tool_result, "raw_stdout", ""),
            raw_stderr=getattr(tool_result, "raw_stderr", ""),
        )
        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "nuclei",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "signal_count": len(in_scope_signals), "oos_drops": oos_drops,
            "approved_templates": list(_APPROVED_TEMPLATE_DIRS),
        })

        terminated_reason: str | None = None
        if tool_result.aborted:
            terminated_reason = "kill_switch"
        elif tool_result.timed_out:
            terminated_reason = "timeout"
        run_status = "partial" if terminated_reason else "success"

        finished = datetime.now(UTC).isoformat(timespec="seconds")
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status=run_status,
            output_count=len(in_scope_signals),
            signal_count=len(in_scope_signals),
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            signals_emitted=len(in_scope_signals),
            source_failures=tool_result.source_failures,
            oos_drops=oos_drops,
            terminated_reason=terminated_reason,  # type: ignore[arg-type]
        )
    finally:
        conn.close()


def _record_prereq_missing(
    conn: sqlite3.Connection,
    paths: config.Paths,
    platform: str,
    slug: str,
    run_id: str,
    now: str,
    artifact_dir: Path,
) -> active.ActiveRunResult:
    runs.start_run(
        conn, run_id=run_id, platform=platform, slug=slug, tool="nuclei",
        started_at=now, artifact_dir=str(artifact_dir), input_count=0,
    )
    prereq_sig = Signal(
        run_id=run_id, tool="nuclei", signal_type="prereq_missing",
        asset="", target="",
        signature=f"prereq|httpx|< {_PREREQ_FRESHNESS_HOURS}h",
        payload=json.dumps({"required_tool": "httpx",
                             "max_age_hours": _PREREQ_FRESHNESS_HOURS}),
        observed_at=now,
    )
    signals.insert_signals(conn, [prereq_sig])
    _write_signals_jsonl(artifact_dir, [prereq_sig])
    _write_manifest(artifact_dir, {
        "run_id": run_id, "tool": "nuclei",
        "platform": platform, "slug": slug, "started_at": now,
        "status": "skipped", "reason": "no recent httpx run",
    })
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    runs.finish_run(
        conn, run_id=run_id, finished_at=finished, status="skipped",
        output_count=0, signal_count=1, source_failures=0, oos_drops=0,
        error_summary="no recent httpx run within prereq freshness window",
    )
    return active.ActiveRunResult(
        run_id=run_id, targets_considered=0, targets_scanned=0,
        artifacts_written=1, signals_emitted=1, source_failures=0, oos_drops=0,
    )
```

This file is approaching the 200-line cap. The `main()` + tool-wiring helpers go into a sibling module `runners/nuclei_scan_cli.py` to keep both files under cap.

**P1.1 note:** `httpx_probe._build_real_tool` has the same watchdog-reason bug (passes `lambda _r: abort.set()` and loses the reason string). Apply the identical `abort_reason: list[str | None]` + `on_state_change` pattern to `httpx_probe._build_real_tool` in the same commit that ships the nuclei CLI module — so both runners record the correct `terminated_reason` ("kill_switch" vs "freeze").

```python
# src/earn_money/runners/nuclei_scan_cli.py
"""CLI entry + real-tool wiring for nuclei-scan. Kept in a sibling
module so `nuclei_scan.py` itself stays under the 200-line cap."""

from __future__ import annotations

import argparse
import sys
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from earn_money import config, flags, policy
from earn_money.recon import nuclei_tool
from earn_money.recon.signals import Signal
from earn_money.runners import active, batch, nuclei_scan, watchdog


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str
) -> Callable[[list[str]], active.ToolRunResult]:
    def real_tool(targets: list[str]) -> active.ToolRunResult:
        abort = threading.Event()
        # P1.1: capture the watchdog reason so the runner can record
        # "kill_switch" vs "freeze" in terminated_reason instead of a
        # generic sentinel. Using a one-element list because nonlocal
        # assignment inside a nested def requires Python 3.x cell binding.
        abort_reason: list[str | None] = [None]

        def on_state_change(reason: str) -> None:
            abort_reason[0] = reason
            abort.set()

        wd = watchdog.KillSwitchWatchdog(
            paths, platform=platform, slug=slug,
            on_state_change=on_state_change,
            poll_interval_s=5.0,
        )
        wd.start()
        try:
            batches_result = batch.run_batches(
                targets,
                command_factory=lambda chunk: nuclei_tool.build_command(
                    chunk, template_dirs=("cves", "misconfiguration"),
                ),
                max_batch_size=50, max_batch_duration_s=300.0,
                abort=abort,
            )
        finally:
            wd.stop()
        raw_stdout = "\n".join(line for b in batches_result.batches for line in b.lines)
        raw_stderr = "\n".join(
            line for b in batches_result.batches for line in getattr(b, "stderr_lines", [])
        )
        now = datetime.now(UTC).isoformat(timespec="seconds")
        source_failures = sum(
            1 for b in batches_result.batches
            if b.timed_out or b.return_code not in (0, None)
        )
        timed_out = any(b.timed_out for b in batches_result.batches)
        return active.ToolRunResult(
            services=nuclei_tool.parse_jsonl(raw_stdout, run_id=run_id, observed_at=now),
            aborted=batches_result.aborted,
            terminated_reason=abort_reason[0],
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            source_failures=source_failures,
            timed_out=timed_out,
        )

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nuclei-scan")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex
    real_tool = _build_real_tool(paths, platform=args.platform, slug=args.program, run_id=run_id)

    try:
        result = nuclei_scan.run_program(
            paths, args.platform, args.program, tool_run=real_tool, run_id=run_id,
        )
    except flags.ReconDisabled as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 4
    except nuclei_tool.UnsafeTemplateProfile as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 5
    except Exception as e:
        print(f"nuclei-scan: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(
        f"nuclei-scan: scanned={result.targets_scanned} "
        f"signals={result.signals_emitted} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify GREEN for the gate tests**

```bash
.venv/bin/python -m pytest tests/runners/test_nuclei_scan.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Write the prereq-missing test**

```python
# tests/runners/test_nuclei_scan.py — append
def test_writes_prereq_missing_signal_when_no_recent_httpx(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    # No httpx run seeded.
    result = nuclei_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(services=[]),
    )
    assert result.targets_scanned == 0
    assert result.signals_emitted == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT signal_type FROM signals"
    ).fetchall()
    run_status = conn.execute(
        "SELECT status, error_summary FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchone()
    conn.close()
    assert rows == [("prereq_missing",)]
    assert run_status[0] == "skipped"
    assert "no recent httpx run" in run_status[1]
```

Run + verify GREEN.

- [ ] **Step 6: Write the happy-path test (writes signals + manifest)**

```python
# tests/runners/test_nuclei_scan.py — append
def test_writes_signals_for_in_scope_services(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])

    _seed_httpx_run_and_services(
        paths, services_to_insert=[
            services.HttpService(
                subdomain="api.example.com", scheme="https", port=443,
                url="https://api.example.com/", status_code=200, title=None,
                server=None, technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
            ),
        ],
    )

    captured_targets: list[list[str]] = []

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        captured_targets.append(list(targets))
        return active.ToolRunResult(services=[
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="api.example.com",
                target="https://api.example.com/search?q=foo",
                signature="CVE-2023-1234|primary|",
                payload='{"template_id":"CVE-2023-1234"}',
                observed_at="2026-05-12T02:16:00Z",
            ),
        ])

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=fake_tool,
        run_id="nuclei-r1",
    )
    assert result.signals_emitted == 1
    assert result.oos_drops == 0
    assert captured_targets == [["https://api.example.com/"]]

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset, signature FROM signals "
        "WHERE tool = 'nuclei'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchall()
    conn.close()
    assert sigs == [("template_match", "api.example.com", "CVE-2023-1234|primary|")]
    assert runs_rows == [("success",)]

    # Artifact files exist — all four required by the Shared Artifact Contract.
    nuclei_out = paths.root / "recon" / "outputs" / "hackerone" / "example" / "nuclei"
    manifest_files = list(nuclei_out.rglob("manifest.json"))
    assert len(manifest_files) == 1
    signals_files = list(nuclei_out.rglob("signals.jsonl"))
    assert len(signals_files) == 1
    # P1.2: required artifact files
    input_files = list(nuclei_out.rglob("input.txt"))
    assert len(input_files) == 1
    raw_files = list(nuclei_out.rglob("raw.jsonl"))
    assert len(raw_files) == 1
    stderr_files = list(nuclei_out.rglob("stderr.txt"))
    assert len(stderr_files) == 1
```

Run + verify GREEN.

- [ ] **Step 7: Write the OOS-drop test**

```python
# tests/runners/test_nuclei_scan.py — append
def test_drops_oos_signals_from_tool_output(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(services=[
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="api.example.com", target="https://api.example.com/",
                signature="ok-sig", payload="{}", observed_at="t",
            ),
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="evil.example.com", target="https://evil.example.com/",
                signature="evil-sig", payload="{}", observed_at="t",
            ),
        ])

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.signals_emitted == 1
    assert result.oos_drops == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT asset FROM signals WHERE tool = 'nuclei'"
    ).fetchall()
    conn.close()
    assert rows == [("api.example.com",)]
```

Run + verify GREEN.

- [ ] **Step 7b: Write the B5 OOS-target test (in-scope asset, OOS target URL)**

```python
# tests/runners/test_nuclei_scan.py — append
def test_drops_signals_with_oos_target_even_if_asset_in_scope(tmp_repo: Path) -> None:
    """B1/B5: a signal whose sig.asset is in-scope but sig.target resolves
    to an OOS hostname must be dropped and counted as oos_drops."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(services=[
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="api.example.com",        # in-scope asset
                target="https://evil.example.com/leaked",  # OOS target URL!
                signature="cve-2020-1234|matcher|",
                payload="{}", observed_at="t",
            ),
        ])

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.oos_drops == 1
    assert result.signals_emitted == 0

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT COUNT(*) FROM signals").fetchone()
    conn.close()
    assert rows == (0,)
```

Run + verify GREEN.

- [ ] **Step 8: Lint**

```bash
make lint
```

- [ ] **Step 9: Commit**

```bash
git add src/earn_money/runners/nuclei_scan.py src/earn_money/runners/nuclei_scan_cli.py \
        tests/runners/test_nuclei_scan.py
git commit -m "feat: nuclei-scan runner with prereq freshness + OOS re-filter"
```

---

## Task 7: `bin/nuclei-scan` CLI

Same shape as `bin/httpx-probe`. Sh script, sources `.env`, invokes the runner via the package's `cli` module.

**Files:**
- Create: `bin/nuclei-scan`

- [ ] **Step 1: Write the script**

```sh
#!/bin/sh
# Thin wrapper around the nuclei-scan runner.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "nuclei-scan: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" -m earn_money.runners.nuclei_scan_cli --root "$ROOT" "$@"
```

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x bin/nuclei-scan
bin/nuclei-scan --help
```

Expected: argparse usage line for `nuclei-scan`.

- [ ] **Step 3: Commit**

```bash
git add bin/nuclei-scan
git commit -m "feat: bin/nuclei-scan CLI wrapper"
```

---

## Task 8: Triage queue markdown writer

Pure formatting layer. Given a `Finding`, the `Signal` rows that produced it, and the latest `HttpService` row for the asset (for context), produce the body of `findings/_queue/<hash>.md`.

Per CLAUDE.md: "Reports must read as written by a human expert. Templates are starting drafts, not finished products. Substantive operator edit pass, not cosmetic." The queue note is therefore deliberately sparse — it lays out evidence and asks open questions instead of pre-writing a conclusion. The operator's job is to verify and edit; the template's job is to surface the relevant facts.

Template body:

```markdown
---
finding_hash: <hash>
platform: <platform>
slug: <slug>
vuln_class: <vuln_class>
asset: <asset>
target: <target>
signature: <signature>
severity_hint: <severity_hint>
confidence: <confidence>
source_tool: <source_tool>
source_run_id: <source_run_id>
first_seen: <first_seen>
last_seen: <last_seen>
occurrence_count: <occurrence_count>
state: queued
---

# <title>

## What the scanner said

<source_tool> matched **<signature>** on `<target>` (severity hint: <severity_hint>, confidence: <confidence>%).

Evidence: `<evidence_path>`

## Asset context

- Asset: `<asset>`
- Latest observation: <observed_at>  (status <status_code>, server `<server>`)
- Technologies: <comma_list>

## What we need to confirm before this is a finding

- [ ] Reproduce the matcher hit manually.
- [ ] Check whether the matched URL is reachable from an unauthenticated session.
- [ ] If the template is a CVE check, verify the running version actually corresponds to the vulnerable range — many CVE templates are version-sniff only and miss backported patches.
- [ ] Capture one redacted screenshot (no PII).
- [ ] Decide impact and write a one-paragraph rationale for whether this clears the program's severity bar.

## Operator notes
<!-- write your verification trail here -->
```

The writer takes a `Finding`, an optional `HttpService` (for context), and produces both the YAML frontmatter and the markdown body. It does not touch disk — `triage.engine` writes the file.

**Files:**
- Create: `src/earn_money/triage/queue.py`
- Create: `tests/triage/test_queue.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/triage/test_queue.py
from __future__ import annotations

import re

from earn_money.recon.services import HttpService
from earn_money.triage import queue
from earn_money.triage.findings import Finding


def _finding() -> Finding:
    return Finding(
        finding_hash="abc123",
        platform="hackerone", slug="example",
        vuln_class="cve-2023-1234",
        asset="api.example.com",
        target="https://api.example.com/search?q=foo",
        signature="CVE-2023-1234|primary|",
        title="CVE-2023-1234 hit on api.example.com",
        severity_hint="high", confidence=70,
        source_tool="nuclei", source_run_id="r1",
        evidence_path="recon/outputs/.../raw.jsonl",
        notes_path="findings/_queue/abc123.md",
        first_seen="2026-05-12T05:00:00Z",
        last_seen="2026-05-12T05:00:00Z",
        occurrence_count=1, current_state="queued",
        state_changed_at="2026-05-12T05:00:00Z",
        external_report_id=None, payout_amount=None, payout_currency=None,
    )


def _service() -> HttpService:
    return HttpService(
        subdomain="api.example.com", scheme="https", port=443,
        url="https://api.example.com/", status_code=200,
        title="Acme API", server="nginx",
        technologies=("nginx", "openresty"),
        redirect_to=None, tls_summary=None,
        observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
        in_scope_at_observation=True,
    )


def test_render_includes_frontmatter_and_title() -> None:
    md = queue.render(_finding(), service=_service())
    # Frontmatter present and parsable shape.
    assert md.startswith("---\n")
    assert "finding_hash: abc123\n" in md
    assert "state: queued\n" in md
    assert "---\n\n# CVE-2023-1234 hit on api.example.com" in md


def test_render_lists_asset_context_when_service_provided() -> None:
    md = queue.render(_finding(), service=_service())
    assert "Status 200" in md or "status 200" in md
    assert "nginx" in md
    assert "openresty" in md
    assert "Latest observation: 2026-05-12T01:05:00Z" in md


def test_render_handles_missing_service_gracefully() -> None:
    md = queue.render(_finding(), service=None)
    # The "Asset context" block still renders — it just says "(no recent httpx)".
    assert "Asset context" in md
    assert "no recent httpx" in md.lower()


def test_render_contains_verification_checklist() -> None:
    md = queue.render(_finding(), service=_service())
    # The checklist drives the operator's work — its presence is load-bearing.
    assert "Reproduce the matcher hit manually" in md
    assert "Capture one redacted screenshot" in md


def test_render_starts_with_yaml_dashes_and_ends_with_newline() -> None:
    md = queue.render(_finding(), service=_service())
    assert md.startswith("---\n")
    assert md.endswith("\n")
    # The frontmatter section ends before the title.
    frontmatter_end = md.find("\n---\n", 4)
    assert frontmatter_end > 0
    assert re.search(r"---\n\n# ", md) is not None
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_queue.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the renderer**

```python
# src/earn_money/triage/queue.py
"""Pure markdown rendering for `findings/_queue/<hash>.md`.

The render function is a starting draft — the operator's manual edit
pass is what turns this into a real triage note. Per CLAUDE.md, a
template that reads as "finished work" is a process smell.
"""

from __future__ import annotations

from earn_money.recon.services import HttpService
from earn_money.triage.findings import Finding


_CHECKLIST: tuple[str, ...] = (
    "Reproduce the matcher hit manually.",
    "Check whether the matched URL is reachable from an unauthenticated session.",
    "If the template is a CVE check, verify the running version actually corresponds "
    "to the vulnerable range — many CVE templates are version-sniff only and miss "
    "backported patches.",
    "Capture one redacted screenshot (no PII).",
    "Decide impact and write a one-paragraph rationale for whether this clears "
    "the program's severity bar.",
)


def render(f: Finding, *, service: HttpService | None) -> str:
    """Build the markdown body for findings/_queue/<finding_hash>.md."""
    return "".join((
        _frontmatter(f),
        _title(f),
        _scanner_block(f),
        _asset_block(service),
        _checklist_block(),
        _notes_block(),
    ))


def _frontmatter(f: Finding) -> str:
    lines = [
        "---",
        f"finding_hash: {f.finding_hash}",
        f"platform: {f.platform}",
        f"slug: {f.slug}",
        f"vuln_class: {f.vuln_class}",
        f"asset: {f.asset}",
        f"target: {f.target}",
        f"signature: {f.signature}",
        f"severity_hint: {f.severity_hint}",
        f"confidence: {f.confidence}",
        f"source_tool: {f.source_tool}",
        f"source_run_id: {f.source_run_id}",
        f"first_seen: {f.first_seen}",
        f"last_seen: {f.last_seen}",
        f"occurrence_count: {f.occurrence_count}",
        "state: queued",
        "---",
        "",
    ]
    return "\n".join(lines) + "\n"


def _title(f: Finding) -> str:
    return f"# {f.title}\n\n"


def _scanner_block(f: Finding) -> str:
    return (
        "## What the scanner said\n\n"
        f"{f.source_tool} matched **{f.signature}** on `{f.target}` "
        f"(severity hint: {f.severity_hint}, confidence: {f.confidence}%).\n\n"
        f"Evidence: `{f.evidence_path}`\n\n"
    )


def _asset_block(service: HttpService | None) -> str:
    if service is None:
        return (
            "## Asset context\n\n"
            "_no recent httpx observation for this asset — re-run httpx-probe "
            "before treating this as a real candidate._\n\n"
        )
    techs = ", ".join(service.technologies) if service.technologies else "(none reported)"
    return (
        "## Asset context\n\n"
        f"- Asset: `{service.subdomain}`\n"
        f"- Latest observation: {service.observed_at}  "
        f"(Status {service.status_code}, server `{service.server or 'unknown'}`)\n"
        f"- Technologies: {techs}\n\n"
    )


def _checklist_block() -> str:
    items = "\n".join(f"- [ ] {line}" for line in _CHECKLIST)
    return (
        "## What we need to confirm before this is a finding\n\n"
        f"{items}\n\n"
    )


def _notes_block() -> str:
    return (
        "## Operator notes\n"
        "<!-- write your verification trail here -->\n"
    )
```

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/triage/test_queue.py -v
make lint
```

Expected: 5 passed; lint clean.

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/triage/queue.py tests/triage/test_queue.py
git commit -m "feat: queue markdown renderer with starting-draft template"
```

---

## Task 9: Triage engine

Wires it all together. `run_program(paths, platform, slug, *, now=None)`:

1. Read scope (kill-switch + freeze gates only — policy is intentionally skipped because triage produces no target traffic; this also lets triage run for `manual-only` programs once the operator manually feeds signals).
2. Query `recon_runs WHERE platform=? AND slug=? AND finished_at IS NOT NULL AND triaged_at IS NULL` ordered by `started_at`.
3. For each run:
   a. Fetch all `signals` rows for that `run_id` (in DB; the JSONL is decorative).
   b. For each signal, derive `(vuln_class, title, severity_hint, confidence)` from `tool` + `signal_type` + payload via a small dispatch table.
   c. Compute `finding_hash` via `triage.hashing.compute_hash`.
   d. Look up the latest `HttpService` row for the asset (for context).
   e. Upsert `Finding` row via `triage.findings.upsert_finding`.
   f. Render the queue markdown via `triage.queue.render` and write it to `findings/_queue/<hash>.md` ONLY if the row is freshly created (re-observations don't overwrite operator edits).
4. UPDATE the `recon_runs` row's `triaged_at`.

The dispatch table for `(vuln_class, title, severity_hint, confidence)` is a small mapping that lives next to the engine. Initial values:

| tool | signal_type | vuln_class | severity hint source | confidence |
| --- | --- | --- | --- | --- |
| nuclei | template_match | `payload.template_id` (lowercased) | `payload.severity` | 70 if severity ∈ {high, critical}, 50 if medium, 30 if low/info |
| nuclei | prereq_missing | `recon-prereq-missing` | `info` | 100 (it's a fact, not a guess) |
| httpx | fingerprint_drift | `recon-fingerprint-drift` | `info` | 40 |

Prereq-missing signals get a finding row so the digest surfaces them in the Recon Anomalies block, but they're marked `source_tool='nuclei'` to make the origin obvious.

The non-overwrite rule for existing queue files matters: an operator may have edited `findings/_queue/<hash>.md` (e.g. adding context after a manual check). If triage re-runs and finds the same hash, it must not nuke the operator's work — the queue file is only written on first creation. The DB row's non-state columns are still refreshed by `upsert_finding`, so `last_seen` and `occurrence_count` reflect reality.

**Files:**
- Create: `src/earn_money/triage/engine.py`
- Create: `tests/triage/test_engine.py`

- [ ] **Step 1: Write the failing test for first-time-triage of a nuclei run**

```python
# tests/triage/test_engine.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import runs, services, signals
from earn_money.recon.signals import Signal
from earn_money.recon.services import HttpService
from earn_money.triage import engine, findings


def _paths(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    return paths


def _seed_nuclei_run_with_signal(paths: config.Paths) -> None:
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        # Add a service so the engine can render asset context.
        services.upsert_service(conn, HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200,
            title="Acme API", server="nginx",
            technologies=("nginx",),
            redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        # The nuclei run we want triaged.
        runs.start_run(
            conn, run_id="nuclei-r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T02:15:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r1", finished_at="2026-05-12T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r1", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/search?q=foo",
            signature="CVE-2023-1234|primary|",
            payload='{"template_id":"CVE-2023-1234","matcher_name":"primary",'
                    '"matched_at":"https://api.example.com/search?q=foo",'
                    '"severity":"high","name":"Acme SQLi"}',
            observed_at="2026-05-12T02:16:00Z",
        )])
    finally:
        conn.close()


def test_triages_one_nuclei_run_and_writes_queue_file(tmp_repo: Path) -> None:
    paths = _paths(tmp_repo)
    _seed_nuclei_run_with_signal(paths)

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-12T05:00:00Z",
    )
    assert result.runs_processed == 1
    assert result.findings_created == 1
    assert result.findings_refreshed == 0

    # The DB has one finding row.
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT vuln_class, title, severity_hint, source_tool, current_state "
        "FROM findings"
    ).fetchall()
    triaged_at = conn.execute(
        "SELECT triaged_at FROM recon_runs WHERE run_id = 'nuclei-r1'"
    ).fetchone()
    conn.close()

    assert len(rows) == 1
    vuln_class, title, severity_hint, source_tool, state = rows[0]
    assert vuln_class == "cve-2023-1234"
    assert "Acme SQLi" in title or "CVE-2023-1234" in title
    assert severity_hint == "high"
    assert source_tool == "nuclei"
    assert state == "queued"
    assert triaged_at[0] == "2026-05-12T05:00:00Z"

    # A queue markdown file exists.
    queue_dir = paths.root / "findings" / "_queue"
    files = list(queue_dir.glob("*.md"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "## What the scanner said" in body
    assert "CVE-2023-1234" in body
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_engine.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the engine**

```python
# src/earn_money/triage/engine.py
"""Triage engine v1.

Reads finished recon runs that have `triaged_at IS NULL`, fetches their
signals, computes finding hashes, upserts `findings` rows, and writes
`findings/_queue/<hash>.md` for freshly-created findings only.

Re-observation rules:
- A signal whose hash matches an existing non-terminal finding refreshes
  `last_seen`, increments `occurrence_count`, and updates evidence —
  but does NOT rewrite the queue markdown (operator edits are sacred).
- A signal whose hash matches a terminal finding (resolved_*) is a no-op
  at the row level. The signal still counts toward the `findings_refreshed`
  result so the digest can surface "old finding re-observed" rows.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from earn_money import config, db, scope
from earn_money.recon import services
from earn_money.recon.services import HttpService
from earn_money.recon.signals import Signal
from earn_money.triage import findings, hashing, queue
from earn_money.triage.findings import Finding


@dataclass(frozen=True)
class TriageRunResult:
    runs_processed: int
    findings_created: int
    findings_refreshed: int
    signals_skipped: int


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    now: str | None = None,
) -> TriageRunResult:
    """Triage every untriaged finished recon_runs row for this program."""
    now = now or datetime.now(UTC).isoformat(timespec="seconds")

    # Triage does NOT call active.check_gates(mode='active') because it
    # sends no target traffic. We *do* still respect kill-switch + freeze
    # so the operator can halt all per-program work in one place.
    from earn_money import flags
    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)
    s = scope.read_scope(paths.scope_file(platform, slug))

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        untriaged_rows = conn.execute(
            "SELECT run_id, tool FROM recon_runs "
            "WHERE platform = ? AND slug = ? "
            "AND finished_at IS NOT NULL AND triaged_at IS NULL "
            "ORDER BY started_at",
            (platform, slug),
        ).fetchall()

        created = 0
        refreshed = 0
        skipped = 0

        for run_id, tool in untriaged_rows:
            sigs = _signals_for_run(conn, run_id)
            for sig in sigs:
                outcome = _process_signal(
                    conn, paths, sig, scope_=s,
                    platform=platform, slug=slug, now=now,
                )
                if outcome == "created":
                    created += 1
                elif outcome == "refreshed":
                    refreshed += 1
                else:
                    skipped += 1
            conn.execute(
                "UPDATE recon_runs SET triaged_at = ? WHERE run_id = ?",
                (now, run_id),
            )
            conn.commit()

        return TriageRunResult(
            runs_processed=len(untriaged_rows),
            findings_created=created,
            findings_refreshed=refreshed,
            signals_skipped=skipped,
        )
    finally:
        conn.close()


def _signals_for_run(conn: sqlite3.Connection, run_id: str) -> list[Signal]:
    cursor = conn.execute(
        "SELECT run_id, tool, signal_type, asset, target, signature, "
        "payload, observed_at FROM signals WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    return [Signal(*row) for row in cursor]


def _process_signal(
    conn: sqlite3.Connection,
    paths: config.Paths,
    sig: Signal,
    *,
    scope_: scope.Scope,
    platform: str,
    slug: str,
    now: str,
) -> str:
    """Triage one signal. Returns one of: 'created', 'refreshed', 'skipped'."""
    # Defensive scope re-check: even though the runner filters, scope can
    # drift between scan and triage time. Drop OOS signals silently.
    if sig.asset and not scope.is_in_scope(sig.asset, scope_.in_scope, scope_.out_of_scope):
        return "skipped"

    vuln_class, title, severity_hint, confidence = _classify(sig)
    finding_hash = hashing.compute_hash(
        platform=platform, slug=slug, vuln_class=vuln_class,
        asset=sig.asset, target=sig.target, signature=sig.signature,
    )

    existing = findings.find_by_hash(conn, finding_hash)
    notes_path = f"findings/_queue/{finding_hash}.md"
    finding = Finding(
        finding_hash=finding_hash,
        platform=platform, slug=slug,
        vuln_class=vuln_class,
        asset=sig.asset, target=sig.target, signature=sig.signature,
        title=title, severity_hint=severity_hint, confidence=confidence,
        source_tool=sig.tool, source_run_id=sig.run_id,
        evidence_path=_evidence_path(conn, sig.run_id),
        notes_path=notes_path,
        first_seen=existing.first_seen if existing else sig.observed_at,
        last_seen=sig.observed_at,
        occurrence_count=(existing.occurrence_count if existing else 1),
        current_state=(existing.current_state if existing else "queued"),
        state_changed_at=(existing.state_changed_at if existing else now),
        external_report_id=existing.external_report_id if existing else None,
        payout_amount=existing.payout_amount if existing else None,
        payout_currency=existing.payout_currency if existing else None,
    )
    findings.upsert_finding(conn, finding)

    if existing is None:
        # Render the queue markdown — operator-editable from this point.
        svc = _latest_service_for_asset(conn, sig.asset)
        queue_path = paths.root / notes_path
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_path.write_text(queue.render(finding, service=svc), encoding="utf-8")
        return "created"
    return "refreshed"


def _classify(sig: Signal) -> tuple[str, str, str, int]:
    """Derive (vuln_class, title, severity_hint, confidence) from a signal."""
    if sig.tool == "nuclei" and sig.signal_type == "template_match":
        return _classify_nuclei_match(sig)
    if sig.tool == "nuclei" and sig.signal_type == "prereq_missing":
        return (
            "recon-prereq-missing",
            "nuclei skipped: no recent httpx run",
            "info", 100,
        )
    if sig.tool == "httpx" and sig.signal_type == "fingerprint_drift":
        return (
            "recon-fingerprint-drift",
            f"httpx fingerprint changed on {sig.asset}",
            "info", 40,
        )
    return ("recon-other", f"{sig.tool}/{sig.signal_type} on {sig.asset}", "unknown", 0)


def _classify_nuclei_match(sig: Signal) -> tuple[str, str, str, int]:
    try:
        payload: dict[str, Any] = json.loads(sig.payload)
    except json.JSONDecodeError:
        payload = {}
    template_id = str(payload.get("template_id", "unknown")).lower()
    severity = str(payload.get("severity", "unknown")).lower()
    name = str(payload.get("name") or template_id)
    confidence = {
        "critical": 80, "high": 70, "medium": 50, "low": 35, "info": 30,
    }.get(severity, 30)
    title = f"{name} on {sig.asset}"
    return (template_id, title, severity, confidence)


def _evidence_path(conn: sqlite3.Connection, run_id: str) -> str:
    row = conn.execute(
        "SELECT artifact_dir FROM recon_runs WHERE run_id = ?", (run_id,),
    ).fetchone()
    if not row:
        return ""
    return f"{row[0]}/raw.jsonl"


def _latest_service_for_asset(
    conn: sqlite3.Connection, asset: str
) -> HttpService | None:
    rows = services.services_for_subdomains(conn, [asset])
    if not rows:
        return None
    # If multiple (scheme,port) exist, prefer HTTPS:443 then highest status.
    rows.sort(
        key=lambda r: (
            0 if (r.scheme == "https" and r.port == 443) else 1,
            -(r.status_code or 0),
            r.observed_at,
        )
    )
    return rows[0]
```

- [ ] **Step 4: Verify the first test GREEN**

```bash
.venv/bin/python -m pytest tests/triage/test_engine.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Add the re-observation test**

```python
# tests/triage/test_engine.py — append
def test_re_triage_refreshes_finding_but_does_not_overwrite_queue_file(
    tmp_repo: Path,
) -> None:
    paths = _paths(tmp_repo)
    _seed_nuclei_run_with_signal(paths)

    # First triage pass.
    engine.run_program(paths, "hackerone", "example", now="2026-05-12T05:00:00Z")
    queue_files = list((paths.root / "findings" / "_queue").glob("*.md"))
    assert len(queue_files) == 1
    operator_edited = queue_files[0].read_text(encoding="utf-8") + "\n## Operator: started repro\n"
    queue_files[0].write_text(operator_edited, encoding="utf-8")

    # A second nuclei run produces the *same* finding hash (same signature).
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="nuclei-r2", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-13T02:15:00Z",
            artifact_dir="x2", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r2", finished_at="2026-05-13T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r2", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/search?q=foo",
            signature="CVE-2023-1234|primary|",
            payload='{"template_id":"CVE-2023-1234","severity":"high","name":"Acme SQLi"}',
            observed_at="2026-05-13T02:16:00Z",
        )])
    finally:
        conn.close()

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-13T05:00:00Z",
    )
    assert result.findings_created == 0
    assert result.findings_refreshed == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT occurrence_count, last_seen FROM findings"
    ).fetchone()
    conn.close()
    assert row[0] == 2
    assert row[1] == "2026-05-13T02:16:00Z"
    # Operator edit survives.
    assert "## Operator: started repro" in queue_files[0].read_text(encoding="utf-8")
```

Run + verify GREEN.

- [ ] **Step 6: Add the OOS-drift skip test**

```python
# tests/triage/test_engine.py — append
def test_drops_signal_that_drifted_out_of_scope_between_scan_and_triage(
    tmp_repo: Path,
) -> None:
    paths = _paths(tmp_repo)
    # Seed the signal with an asset that's in-scope at scan time...
    _seed_nuclei_run_with_signal(paths)
    # ...then tighten scope so the asset is no longer in scope.
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["www.example.com"],
        out_of_scope=["api.example.com"],
        notes="", scope_hash="updated", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-12T05:00:00Z",
    )
    assert result.findings_created == 0
    assert result.signals_skipped == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    conn.close()
    assert count == 0
```

Run + verify GREEN.

- [ ] **Step 7: Add the multi-run triage test**

```python
# tests/triage/test_engine.py — append
def test_triages_all_untriaged_runs_and_marks_them(tmp_repo: Path) -> None:
    paths = _paths(tmp_repo)
    _seed_nuclei_run_with_signal(paths)
    # Add a second nuclei run with a different finding.
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="nuclei-r2", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T03:15:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r2", finished_at="2026-05-12T03:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r2", tool="nuclei", signal_type="template_match",
            asset="www.example.com",
            target="https://www.example.com/login",
            signature="http-default-creds|admin-admin|",
            payload='{"template_id":"http-default-creds","severity":"high",'
                    '"name":"Default admin/admin"}',
            observed_at="2026-05-12T03:17:00Z",
        )])
    finally:
        conn.close()

    result = engine.run_program(
        paths, "hackerone", "example", now="2026-05-12T05:00:00Z",
    )
    assert result.runs_processed == 2
    assert result.findings_created == 2

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    triaged = conn.execute(
        "SELECT run_id, triaged_at FROM recon_runs ORDER BY run_id"
    ).fetchall()
    conn.close()
    assert all(row[1] == "2026-05-12T05:00:00Z" for row in triaged)
```

Run + verify GREEN.

- [ ] **Step 8: Lint**

```bash
make lint
```

- [ ] **Step 9: Commit**

```bash
git add src/earn_money/triage/engine.py tests/triage/test_engine.py
git commit -m "feat: triage engine v1 with finding upsert + queue render"
```

---

## Task 10: Triage runner (cron entry point)

`runners/triage.py` is the cron entry point. It:

1. Parses argv (`--platform`, `--program`, `--root`).
2. Calls `triage.engine.run_program`.
3. Prints a one-line summary to stdout; exits 0 on success, non-zero on infrastructure error.

This mirrors `runners/nuclei_scan_cli.py` but is far smaller because triage has no subprocess + no watchdog.

**Files:**
- Create: `src/earn_money/runners/triage.py`
- Create: `tests/runners/test_triage_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_triage_runner.py
from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, scope
from earn_money.runners import triage


def _seed(tmp_repo: Path, *, recon_enabled: bool = True) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    if recon_enabled:
        paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    return paths


def test_returns_zero_when_no_runs_to_triage(tmp_repo: Path) -> None:
    _seed(tmp_repo)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 0


def test_returns_kill_switch_code_when_recon_disabled(tmp_repo: Path) -> None:
    _seed(tmp_repo, recon_enabled=False)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 2


def test_runs_for_manual_only_program(tmp_repo: Path) -> None:
    """Triage produces no target traffic, so it MUST run for manual-only programs
    (the operator may have hand-fed signals into the DB)."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="manual-only",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 0
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_triage_runner.py -v
```

Expected: ModuleNotFoundError on `triage`.

- [ ] **Step 3: Implement the runner**

```python
# src/earn_money/runners/triage.py
"""Cron entry point for the triage engine.

Triage produces no target traffic and therefore intentionally skips the
policy gate — a `manual-only` program can still have findings triaged
from operator-fed signals. The kill-switch and per-program freeze flag
ARE still respected so the operator can halt all per-program work in
one place.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from earn_money import config, flags, scope
from earn_money.triage import engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="triage")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    try:
        result = engine.run_program(paths, args.platform, args.program)
    except flags.ReconDisabled as e:
        print(f"triage: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"triage: {e}", file=sys.stderr)
        return 3
    except scope.InvalidScope as e:
        print(f"triage: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(f"triage: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(
        f"triage: runs={result.runs_processed} "
        f"created={result.findings_created} "
        f"refreshed={result.findings_refreshed} "
        f"skipped={result.signals_skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/runners/test_triage_runner.py -v
make lint
```

Expected: 3 passed; lint clean.

- [ ] **Step 5: Commit**

```bash
git add src/earn_money/runners/triage.py tests/runners/test_triage_runner.py
git commit -m "feat: triage runner with kill-switch + freeze gates"
```

---

## Task 11: `bin/triage` CLI

**Files:**
- Create: `bin/triage`

- [ ] **Step 1: Write the script**

```sh
#!/bin/sh
# Thin wrapper around the triage runner.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "triage: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" -m earn_money.runners.triage --root "$ROOT" "$@"
```

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x bin/triage
bin/triage --help
```

Expected: argparse usage line for `triage`.

- [ ] **Step 3: Commit**

```bash
git add bin/triage
git commit -m "feat: bin/triage CLI wrapper"
```

---

## Task 12: End-to-end triage + nuclei integration tests

Two tests:

1. **`test_triage_e2e.py`** — pure end-to-end through the triage engine with a hand-seeded nuclei run. No subprocess. Asserts: finding row created, queue markdown rendered with expected fields, `recon_runs.triaged_at` set.

2. **`test_nuclei_scan_e2e.py`** — invoke the real nuclei binary against the mock target with a synthetic template. Auto-skips when binary or templates absent. Asserts: `signals` row created, `signals.jsonl` artifact written, manifest written.

The synthetic nuclei template fixture is a minimal YAML file that matches on the mock target's static `<title>` text. We commit it under `tests/fixtures/nuclei_templates/synthetic-200.yaml`. To use it we pass an absolute path via `-t` (nuclei accepts absolute paths in addition to template-directory names) — but `nuclei_tool.build_command` only accepts approved *names*, not paths. We resolve this by:

- Adding a private test-only seam: `nuclei_tool.build_command` already takes `template_dirs` as a tuple; for the e2e test we use a separate `build_command_unsafe` builder that the test imports directly and that bypasses the approved-list check. This keeps the production code's safety boundary intact (the fixture is in `tests/`, not `src/`).

Alternative considered: install the fixture into the nuclei templates root at `~/.nuclei-templates/` during test setup. Rejected because it mutates the developer's home directory.

**Files:**
- Create: `tests/runners/test_triage_e2e.py`
- Create: `tests/runners/test_nuclei_scan_e2e.py`
- Create: `tests/fixtures/nuclei_templates/synthetic-200.yaml`

- [ ] **Step 1: Write the synthetic nuclei template**

```yaml
# tests/fixtures/nuclei_templates/synthetic-200.yaml
id: synthetic-200-title-match

info:
  name: Synthetic — title match on mock target
  author: earn-money-tests
  severity: low
  tags: [test, synthetic]

http:
  - method: GET
    path:
      - "{{BaseURL}}/"

    matchers-condition: and
    matchers:
      - type: status
        status:
          - 200
      - type: word
        part: body
        words:
          - "In-Scope A"
```

- [ ] **Step 2: Write the triage-only end-to-end test**

```python
# tests/runners/test_triage_e2e.py
"""End-to-end through the triage engine.

This test exercises the full triage path without any subprocesses: it
seeds a finished nuclei recon_runs row + a signal in SQLite, runs the
triage engine, and asserts the finding row, queue markdown, and
triaged_at timestamp are all correctly written.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import runs, services, signals
from earn_money.recon.services import HttpService
from earn_money.recon.signals import Signal
from earn_money.runners import triage


def _seed_repo(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["*.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        services.upsert_service(conn, HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200,
            title="Acme API", server="nginx",
            technologies=("nginx",),
            redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="nuclei-r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T02:15:00Z",
            artifact_dir="recon/outputs/hackerone/example/nuclei/2026-05-12/nuclei-r1",
            input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r1", finished_at="2026-05-12T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r1", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/search?q=foo",
            signature="CVE-2023-1234|primary|",
            payload=(
                '{"template_id":"CVE-2023-1234","matcher_name":"primary",'
                '"matched_at":"https://api.example.com/search?q=foo",'
                '"severity":"high","name":"Acme SQLi"}'
            ),
            observed_at="2026-05-12T02:16:00Z",
        )])
    finally:
        conn.close()
    return paths


def test_triage_e2e_creates_finding_and_queue_markdown(tmp_repo: Path) -> None:
    paths = _seed_repo(tmp_repo)
    rc = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc == 0

    # Finding row.
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT vuln_class, severity_hint, current_state, occurrence_count "
        "FROM findings"
    ).fetchall()
    triaged = conn.execute(
        "SELECT triaged_at FROM recon_runs WHERE run_id = 'nuclei-r1'"
    ).fetchone()
    conn.close()
    assert rows == [("cve-2023-1234", "high", "queued", 1)]
    assert triaged[0] is not None

    # Queue markdown.
    files = list((paths.root / "findings" / "_queue").glob("*.md"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "CVE-2023-1234" in body
    assert "Acme SQLi" in body
    assert "## What we need to confirm before this is a finding" in body
    assert "Latest observation: 2026-05-12T01:05:00Z" in body


def test_triage_correlates_signals_across_runs(tmp_repo: Path) -> None:
    """P1.4: Two recon_runs with the same signature+asset must produce one
    finding with occurrence_count=2, not two separate finding rows."""
    paths = _seed_repo(tmp_repo)

    # Second nuclei run — same signature, same asset.
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="nuclei-r2", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-13T02:15:00Z",
            artifact_dir="recon/outputs/hackerone/example/nuclei/2026-05-13/nuclei-r2",
            input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r2", finished_at="2026-05-13T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r2", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/search?q=foo",
            signature="CVE-2023-1234|primary|",  # identical to nuclei-r1
            payload=(
                '{"template_id":"CVE-2023-1234","matcher_name":"primary",'
                '"matched_at":"https://api.example.com/search?q=foo",'
                '"severity":"high","name":"Acme SQLi"}'
            ),
            observed_at="2026-05-13T02:16:00Z",
        )])
    finally:
        conn.close()

    # Triage both runs in sequence.
    rc1 = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc1 == 0
    rc2 = triage.main([
        "--platform", "hackerone", "--program", "example",
        "--root", str(tmp_repo),
    ])
    assert rc2 == 0

    # Exactly one finding row — second run refreshed it rather than creating a new one.
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT finding_hash, occurrence_count FROM findings"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, f"expected 1 finding, got {len(rows)}"
    assert rows[0][1] == 2, f"expected occurrence_count=2, got {rows[0][1]}"
```

- [ ] **Step 3: Verify the triage e2e test GREEN**

```bash
.venv/bin/python -m pytest tests/runners/test_triage_e2e.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Write the nuclei-binary smoke test**

```python
# tests/runners/test_nuclei_scan_e2e.py
"""End-to-end nuclei smoke against the mock target.

Auto-skips when:
- The nuclei binary is not on PATH at ~/go/bin/nuclei
- The synthetic template fixture is absent

We use a private unsafe builder that takes an absolute -t path so the
fixture template doesn't need to be installed into ~/.nuclei-templates/.
The production code path's approved-list check is unaffected.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import nuclei_tool, runs, services
from earn_money.recon.services import HttpService
from earn_money.runners import active, nuclei_scan

_PD_NUCLEI = Path.home() / "go" / "bin" / "nuclei"
_TEMPLATE = (
    Path(__file__).parent.parent
    / "fixtures" / "nuclei_templates" / "synthetic-200.yaml"
)

pytestmark = pytest.mark.skipif(
    not _PD_NUCLEI.exists() or not _TEMPLATE.exists(),
    reason="ProjectDiscovery nuclei binary or synthetic template not present",
)


def _seed(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["127.0.0.1"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        services.upsert_service(conn, HttpService(
            subdomain="127.0.0.1", scheme="http", port=18081,
            url="http://127.0.0.1:18081/", status_code=200,
            title="In-Scope A", server="mock-target/1.0",
            technologies=(),
            redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=1, signal_count=0,
            source_failures=0, oos_drops=0,
        )
    finally:
        conn.close()
    return paths


def _make_tool_run(monkeypatch: pytest.MonkeyPatch):  # type: ignore[type-arg]
    """Build a tool_run that invokes the real nuclei binary against the
    fixture template, returning a ToolRunResult with parsed signals."""
    from earn_money.runners import batch

    pd_bin_dir = str(_PD_NUCLEI.parent)
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{pd_bin_dir}:{current_path}")

    def build_unsafe(chunk: list[str]) -> list[str]:
        return [
            "nuclei",
            "-u", ",".join(chunk),
            "-t", str(_TEMPLATE),
            "-jsonl", "-silent", "-no-color",
            "-disable-redirects", "-no-interactsh",
            "-disable-update-check",
        ]

    # B6: use a single run_id generated once so parser and runner agree.
    e2e_run_id = uuid.uuid4().hex

    def tool_run(targets: list[str]) -> active.ToolRunResult:
        result = batch.run_batches(
            targets,
            command_factory=build_unsafe,
            max_batch_size=50, max_batch_duration_s=60.0,
        )
        raw = "\n".join(line for b in result.batches for line in b.lines)
        return active.ToolRunResult(
            services=nuclei_tool.parse_jsonl(raw, run_id=e2e_run_id, observed_at="t"),
            aborted=result.aborted,
        )

    return tool_run, e2e_run_id


def test_e2e_nuclei_scan_writes_signal_against_mock_target(
    tmp_repo: Path, mock_target: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _seed(tmp_repo)
    tool_run, e2e_run_id = _make_tool_run(monkeypatch)

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=tool_run, run_id=e2e_run_id,
    )
    assert result.signals_emitted >= 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset, signature FROM signals WHERE tool = 'nuclei'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchall()
    conn.close()
    assert runs_rows == [("success",)]
    # The synthetic template fires on the mock target's title.
    assert any("synthetic-200-title-match" in sig for _, _, sig in sigs)

    # Artifact files exist.
    manifests = list(
        (paths.root / "recon" / "outputs" / "hackerone" / "example" / "nuclei").rglob("manifest.json")
    )
    assert len(manifests) == 1
    sig_files = list(
        (paths.root / "recon" / "outputs" / "hackerone" / "example" / "nuclei").rglob("signals.jsonl")
    )
    assert len(sig_files) == 1
    sig_lines = [ln for ln in sig_files[0].read_text(encoding="utf-8").splitlines() if ln]
    assert any(
        json.loads(ln)["signal_type"] == "template_match" for ln in sig_lines
    )
```

- [ ] **Step 5: Run the nuclei e2e**

```bash
.venv/bin/python -m pytest tests/runners/test_nuclei_scan_e2e.py -v
```

Expected (in dev without nuclei installed): 1 skipped. On the VPS with nuclei installed: 1 passed.

- [ ] **Step 6: Run the full suite + lint**

```bash
make smoke
```

Expected: ruff + mypy clean, every prior test still passing, all new tests passing. Roughly: ~107 from 3a + 3 (v3 migration) + 16 (hashing — strengthened) + 7 (findings — +2 B4 guards) + 5 (history) + 9 (nuclei tool — +1 B3 rate caps) + 6 (nuclei runner — +1 B5 OOS-target) + 5 (queue) + 4 (engine) + 3 (triage runner) + 2 (triage e2e — +1 P1.4 correlation) + 1 nuclei e2e (skipped without binary) ≈ **168 passing / 1 skipped**.

- [ ] **Step 7: Commit**

```bash
git add tests/runners/test_triage_e2e.py tests/runners/test_nuclei_scan_e2e.py \
        tests/fixtures/nuclei_templates/synthetic-200.yaml
git commit -m "test: end-to-end triage + nuclei smoke with synthetic template"
```

---

## Self-review

### Spec coverage

| Spec item | Where covered |
| --- | --- |
| Section 3 — Shared Active Runner Contract: prereq freshness check (section 7 nit) | Task 6 step 3 (`_recent_httpx_success`), Task 6 step 5 (`prereq_missing` test) |
| Section 3 — Shared Artifact Contract: manifest + signals.jsonl + raw artifact dir | Task 6 step 3 (`_write_manifest`, `_write_signals_jsonl`), Task 6 step 6 (asserts both files exist) |
| Section 3.2 — nuclei runner safety flags + approved templates | Task 5 (build_command, UnsafeTemplateProfile, APPROVED_TEMPLATE_DIRS), Task 6 step 3 (run_program wiring) |
| Section 3.7 — Triage engine: read recon_runs, correlate signals, dedupe by hash, write _queue/ | Task 9 (engine.run_program), Task 12 (e2e) |
| Section 4 — Schema migration v2→v3 (additive columns + new table) | Task 1 |
| Section 4 — Expanded findings columns | Task 1 (migration), Task 3 (DAO) |
| Section 4 — findings_state_history table | Task 1 (migration), Task 4 (DAO + transition_state) |
| Section 4 — Finding hash composition (`v1|platform|slug|vuln_class|asset|target|signature`) | Task 2 (`compute_hash`) |
| Section 4 — Normalization rules 1-7 | Task 2 (`normalize_target`, `normalize_asset`, `_normalize_path`, `_normalize_query`) |
| Section 4 — Signature composition for nuclei + httpx anomaly | Task 2 (`signature_for_nuclei`, `signature_for_httpx_anomaly`) |
| Section 4 — Finding state machine: allowed transitions, triage may not change current_state | Task 3 (DAO refuses to write current_state via upsert), Task 4 (`transition_state` with `_ALLOWED`) |
| Section 5 — nuclei-scan timer at 02:15 UTC, triage at 05:00 UTC | Documented in spec section 5; timer unit files are 3d's deliverable. Phase 3b only ships the CLIs that the timer units invoke. |
| Section 7 — Signals atomic boundary (DB row authoritative; JSONL write-then-reconcile) | Task 6 step 3 (`signals.insert_signals` is called before `_write_signals_jsonl`); manifest documents the artifact schema. Explicit reconcile-from-DB logic is not built in Phase 3b — it's listed in the umbrella spec section 7 as a future hardening item and called out below in "Items deferred from 3b". |
| Section 7 — Migration atomic boundary (per-step transaction) | Already settled in 3a (`migrations.migrate` uses `BEGIN`/`COMMIT`/`ROLLBACK` per step); Task 1 step 6 re-verifies with the v2→v3 rollback path. |

### Items deferred from 3b (intentional)

- **Signals JSONL reconcile-from-DB.** The DB is authoritative; the JSONL is decorative. If the JSONL is missing or short relative to the DB rows, the operator can regenerate it from the DB. We do *not* build the reconcile tooling in 3b — it's a 3d hardening item if it ever becomes needed in practice.
- **Triage v2 cross-tool correlation.** Phase 3b's engine processes signals one-by-one; correlating an httpx fingerprint drift with a same-host nuclei hit to raise confidence is explicitly 3c's territory.
- **Daily digest / phone ping consumption of new findings.** Phase 3d.
- **`bin/submit` and the `verified → submitted` transition.** Phase 4.

### Post-cursor-review fixes (2026-05-12)

| Issue | Fix location |
| --- | --- |
| B1: post-tool OOS filter only checked `sig.asset`, not `sig.target` | Task 6 — `_target_host` helper + dual-check in `run_program` |
| B2: approved template dirs too broad | Task 5 — `APPROVED_TEMPLATE_DIRS` restricted to `cves` + `misconfiguration`; Task 6 CLI updated |
| B3: nuclei command lacked rate/concurrency caps | Task 5 — `-rl 10 -c 10 -bs 10 -stats-interval 60` added to `build_command`; test locked |
| B4: `upsert_finding` didn't enforce queued-only for new rows or refuse state changes | Task 3 — runtime guards added; two new tests |
| B5: OOS-drop test didn't cover in-scope-asset/OOS-target case | Task 6 — new `test_drops_signals_with_oos_target_even_if_asset_in_scope` |
| B6: nuclei e2e used mismatched `run_id` between parser and runner | Task 12 — `uuid.uuid4().hex` generated once, threaded through both |
| P1.1: watchdog `on_state_change` swallowed reason string | Task 6 (`nuclei_scan_cli.py`) — `abort_reason` list + named `on_state_change`; same fix noted for `httpx_probe` |
| P1.2: required artifact files (`input.txt`, `raw.jsonl`, `stderr.txt`) not written | Task 6 — `_write_required_artifacts` helper; happy-path test asserts all four files |
| P1.3: hash collision test was self-fulfilling | Task 2 — replaced with per-field independence test + normalization-stability test |
| P1.4: triage e2e didn't prove cross-run correlation | Task 12 — `test_triage_correlates_signals_across_runs` added |
| Decision 4 risk note | Task 2 Step 1 — IDN hash-churn risk documented inline |

### Placeholder scan

Grep the plan for the strings `TBD`, `TODO`, `pseudocode`, `[fill in]`, `[example]`. Expected: zero matches. Every code block contains real Python or shell or YAML; every command shows a literal command line; every "expected" assertion describes the actual output the runner produces.

### Type consistency

- `Finding` (Task 3) — 22 fields. Referenced in Task 4 (`_seed_queued`), Task 8 (`_finding`), Task 9 (`Finding(...)` construction in `_process_signal`), Task 12 (`_seed_repo`). Field names match across all sites.
- `Signal` (Phase 3a, re-imported in Task 5, 6, 9, 12). Schema is the existing `signals` table; no changes.
- `HttpService` (Phase 3a, re-imported in Task 6, 8, 9, 12). No changes.
- `ActiveRunResult` / `ToolRunResult` (Phase 3a; `services: list[Any]` makes nuclei's signal-list reuse legal without a new dataclass).
- `TriageRunResult` (Task 9) — 4 fields. Used by Task 10 to print the summary; field names match.
- `StateChange` (Task 4) — 7 fields. Used by Task 4 tests; field names match the `findings_state_history` columns from Task 1.
- `_ALLOWED` (Task 4) is `frozenset[tuple[str, str]]`; cross-checked against `Finding.current_state` allowed values which are documented in spec section 4 and shadowed in `findings._TERMINAL_STATES`.

### Plan-policy compliance

- Each new source file stays under the 200-line cap. `nuclei_scan.py` is the closest call; CLI + tool-wiring lives in `nuclei_scan_cli.py` precisely to keep both under the limit.
- TDD discipline: every task writes the failing test FIRST, runs it to confirm RED, then minimal impl, then GREEN, then commits. No exceptions.
- Each task ends with a Conventional Commits-compliant `feat:` / `test:` line.
- No new runtime dependencies. The `idna` PyPI package decision (Task 2 step 1) is captured and rejected in favor of stdlib for Phase 3b.
- No mocked findings. The synthetic nuclei template (Task 12 step 1) is gated to the mock target only; it never points at a real program.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-phase-3b-nuclei-triage.md`. Two execution options:

1. **Subagent-Driven** (recommended) — a fresh subagent per task. Tasks 2, 3, 4, 5, 8 have no inter-task dependencies on the same files and can run in parallel; Tasks 1, 6, 9 must precede their downstream tests. Review between tasks; fast iteration on the finding-hash + state-machine corners (Tasks 2 + 4) where the bugs will hide.

2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints between Tasks 4 / 7 / 10 / 12.

Which approach?
