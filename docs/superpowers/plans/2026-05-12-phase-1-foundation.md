# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation of the bug-bounty operation: a Python project with a Makefile-driven smoke check, the kill-switch and per-program freeze-flag machinery, a SQLite-backed asset/finding store, a YAML-frontmatter scope-file parser, a HackerOne API client (mocked in tests), and a `scope-sync` runner that ties it all together. By the end of this plan, an operator can run `bin/scope-sync --program <slug>` against a real HackerOne program and have the runner detect destructive scope diffs and freeze that program automatically.

**Architecture:** Python 3.12 package `earn_money` under `src/`. Each unit (config, flags, db, scope, platforms.hackerone, runners.scope_sync) lives in its own file with one responsibility. Tests under `tests/` mirror the source tree. HTTP calls are encapsulated in a thin client mocked at the HTTP layer in tests. SQLite is in-memory for tests, file-backed at runtime. CLI wrappers in `bin/` are thin shell scripts that invoke `python -m`.

**Tech Stack:** Python 3.12, `httpx` (HTTP), `python-frontmatter` (scope.md YAML+markdown parser), `pyyaml`, `pytest`, `pytest-mock`, `ruff` (lint), `mypy` (type check), SQLite (stdlib), GNU make.

---

## Prerequisites (operator, one-time, before any task)

These are operator actions. The plan can't proceed past Task 7 without them.

- Python 3.12 available on the development machine (`python3 --version`).
- HackerOne API credentials. Generate at `https://hackerone.com/<your-handle>/api-tokens` after Phase 0 KYC is complete. Store as environment variables in a local untracked `.env` file (read by `direnv` or sourced manually):

  ```bash
  HACKERONE_API_USERNAME="bb-research"        # your HackerOne handle
  HACKERONE_API_TOKEN="hai_xxxxxxxxxxxxxxxx"  # the generated token
  ```

- Pick one HackerOne program to onboard first. Criteria from the spec: low researcher density, asset class you know well, ToS permits automated scanning at low rate (so `policy: rate-limited-OK`). Record the choice in `programs/hackerone/<slug>/scope.md` after Task 7. Do **not** commit any secrets — `.env` is gitignored.

---

## File structure

This plan creates and modifies these files. Subsequent tasks reference them by exact path.

**Created:**

```
earn-money/
├── Makefile
├── pyproject.toml
├── src/
│   └── earn_money/
│       ├── __init__.py
│       ├── config.py
│       ├── flags.py
│       ├── db.py
│       ├── scope.py
│       ├── platforms/
│       │   ├── __init__.py
│       │   └── hackerone.py
│       └── runners/
│           ├── __init__.py
│           └── scope_sync.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_flags.py
│   ├── test_db.py
│   ├── test_scope.py
│   ├── fixtures/
│   │   ├── scope_example.md
│   │   ├── hackerone_program_initial.json
│   │   ├── hackerone_program_additive.json
│   │   └── hackerone_program_destructive.json
│   ├── platforms/
│   │   ├── __init__.py
│   │   └── test_hackerone.py
│   └── runners/
│       ├── __init__.py
│       └── test_scope_sync.py
├── bin/
│   └── scope-sync
└── programs/
    └── README.md
```

**Modified:**

- `.githooks/pre-commit:1-22` — replace the stub body with a call to `make smoke`, preserving the sensitive-path guard.
- `.gitignore` — append `.env*` (already covered) and `pyproject.toml` build artefacts (`build/`, `dist/`, `*.egg-info/`).

---

## Task 1 — Python project skeleton and Makefile

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `src/earn_money/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Modify: `.gitignore` (append build artefacts)
- Modify: `.githooks/pre-commit:1-22` (wire to `make smoke`)

This task gets the test loop running first so every subsequent task can follow real TDD. There is no production code here — the only thing the test suite checks is that the package imports.

- [ ] **Step 1.1 — Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "earn_money"
version = "0.0.1"
description = "Bug-bounty operations pipeline."
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.12"
mypy_path = "src"
```

- [ ] **Step 1.2 — Write `Makefile`**

```makefile
.PHONY: smoke lint test fmt install-dev clean

PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin

$(VENV_BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip

install-dev: $(VENV_BIN)/python
	$(VENV_BIN)/pip install -e ".[dev]"

lint: install-dev
	$(VENV_BIN)/ruff check src tests
	$(VENV_BIN)/mypy src

test: install-dev
	$(VENV_BIN)/pytest

fmt: install-dev
	$(VENV_BIN)/ruff format src tests
	$(VENV_BIN)/ruff check --fix src tests

smoke: lint test

clean:
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 1.3 — Write `src/earn_money/__init__.py`**

```python
"""earn_money — bug-bounty operations pipeline."""

__version__ = "0.0.1"
```

- [ ] **Step 1.4 — Write `tests/__init__.py`** (empty file)

```
```

- [ ] **Step 1.5 — Write `tests/conftest.py`**

```python
"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clean throwaway repo root for tests that touch the filesystem."""
    (tmp_path / "programs").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path
```

- [ ] **Step 1.6 — Write a single import-smoke test at `tests/test_smoke.py`**

```python
def test_package_imports() -> None:
    from earn_money import __version__

    assert __version__ == "0.0.1"
```

- [ ] **Step 1.7 — Run the suite to confirm green**

Run: `make smoke`
Expected: ruff reports no issues, mypy reports no issues, pytest collects 1 test and passes.

- [ ] **Step 1.8 — Append build artefacts to `.gitignore`**

Append these lines to `.gitignore`:

```
# Build artefacts
build/
dist/
*.egg-info/
.venv/
```

- [ ] **Step 1.9 — Wire `.githooks/pre-commit` to `make smoke`**

Replace the existing stub body. The full new file is:

```sh
#!/bin/sh
set -eu

LEAK_PATTERNS='^(identity/platforms\.md|RECON_ENABLED|.*\.sqlite|.*\.db|recon/outputs/|\.env)$'

if git diff --cached --name-only | grep -E "$LEAK_PATTERNS" >/dev/null 2>&1; then
  echo "pre-commit: refusing — staged files include sensitive operational paths." >&2
  git diff --cached --name-only | grep -E "$LEAK_PATTERNS" >&2
  echo "" >&2
  echo "These paths are gitignored for a reason. If you really need to commit one," >&2
  echo "you must change .gitignore first and justify it in the commit message." >&2
  exit 1
fi

# Run the smoke check.
make smoke
```

- [ ] **Step 1.10 — Commit**

```bash
git add pyproject.toml Makefile src/earn_money/__init__.py tests/__init__.py tests/conftest.py tests/test_smoke.py .gitignore .githooks/pre-commit
git commit -m "feat: bootstrap Python package with Makefile-driven smoke check"
```

---

## Task 2 — Config module

**Files:**
- Create: `src/earn_money/config.py`
- Create: `tests/test_config.py`

The config module centralises filesystem paths and a few constants. Pure functions, no I/O. Tests verify defaults and the `with_root` override.

- [ ] **Step 2.1 — Write the failing test at `tests/test_config.py`**

```python
from __future__ import annotations

from pathlib import Path

from earn_money import config


def test_default_root_is_cwd(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    assert paths.root == tmp_repo
    assert paths.programs == tmp_repo / "programs"
    assert paths.recon_outputs == tmp_repo / "recon" / "outputs"
    assert paths.recon_enabled_flag == tmp_repo / "RECON_ENABLED"


def test_program_dir_layout(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    program_dir = paths.program_dir("hackerone", "example")
    assert program_dir == tmp_repo / "programs" / "hackerone" / "example"
    assert paths.scope_file("hackerone", "example") == program_dir / "scope.md"
    assert paths.freeze_flag("hackerone", "example") == program_dir / "FROZEN"
    assert paths.program_db("hackerone", "example") == program_dir / "db.sqlite"
```

- [ ] **Step 2.2 — Run test to verify it fails**

Run: `make test`
Expected: ImportError or AttributeError — `config.Paths` does not exist yet.

- [ ] **Step 2.3 — Write `src/earn_money/config.py`**

```python
"""Filesystem paths and operational constants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    programs: Path
    recon_outputs: Path
    recon_enabled_flag: Path

    @classmethod
    def from_root(cls, root: Path) -> Paths:
        root = root.resolve()
        return cls(
            root=root,
            programs=root / "programs",
            recon_outputs=root / "recon" / "outputs",
            recon_enabled_flag=root / "RECON_ENABLED",
        )

    def program_dir(self, platform: str, slug: str) -> Path:
        return self.programs / platform / slug

    def scope_file(self, platform: str, slug: str) -> Path:
        return self.program_dir(platform, slug) / "scope.md"

    def freeze_flag(self, platform: str, slug: str) -> Path:
        return self.program_dir(platform, slug) / "FROZEN"

    def program_db(self, platform: str, slug: str) -> Path:
        return self.program_dir(platform, slug) / "db.sqlite"
```

- [ ] **Step 2.4 — Run test to verify it passes**

Run: `make test`
Expected: 2 tests pass (3 total with smoke test).

- [ ] **Step 2.5 — Commit**

```bash
git add src/earn_money/config.py tests/test_config.py
git commit -m "feat: add Paths config object for filesystem layout"
```

---

## Task 3 — Flags module (kill-switch + per-program freeze)

**Files:**
- Create: `src/earn_money/flags.py`
- Create: `tests/test_flags.py`

This module implements two safety mechanisms from the spec:

1. The `RECON_ENABLED` master kill-switch. Every runner must call `require_recon_enabled()` before doing anything.
2. Per-program `FROZEN` flag files written by the scope-sync runner when a destructive scope diff is detected.

- [ ] **Step 3.1 — Write the failing tests at `tests/test_flags.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, flags


def test_require_recon_enabled_raises_when_flag_absent(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    with pytest.raises(flags.ReconDisabled):
        flags.require_recon_enabled(paths)


def test_require_recon_enabled_passes_when_flag_present(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    flags.require_recon_enabled(paths)  # no raise


def test_program_freeze_flag_roundtrip(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.program_dir("hackerone", "example").mkdir(parents=True)
    assert not flags.is_program_frozen(paths, "hackerone", "example")
    flags.freeze_program(paths, "hackerone", "example", reason="scope drift: 2 assets removed")
    assert flags.is_program_frozen(paths, "hackerone", "example")
    assert "scope drift" in flags.freeze_reason(paths, "hackerone", "example")


def test_unfreeze_program_removes_flag(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.program_dir("hackerone", "example").mkdir(parents=True)
    flags.freeze_program(paths, "hackerone", "example", reason="test")
    flags.unfreeze_program(paths, "hackerone", "example")
    assert not flags.is_program_frozen(paths, "hackerone", "example")


def test_require_program_not_frozen_raises(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.program_dir("hackerone", "example").mkdir(parents=True)
    flags.freeze_program(paths, "hackerone", "example", reason="test")
    with pytest.raises(flags.ProgramFrozen):
        flags.require_program_not_frozen(paths, "hackerone", "example")
```

- [ ] **Step 3.2 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `flags` module does not exist.

- [ ] **Step 3.3 — Write `src/earn_money/flags.py`**

```python
"""Operational safety flags: kill-switch and per-program freeze."""

from __future__ import annotations

from datetime import UTC, datetime

from earn_money.config import Paths


class ReconDisabled(Exception):
    """Raised when RECON_ENABLED flag is absent."""


class ProgramFrozen(Exception):
    """Raised when a program has an active FROZEN flag."""


def require_recon_enabled(paths: Paths) -> None:
    if not paths.recon_enabled_flag.exists():
        raise ReconDisabled(
            f"RECON_ENABLED flag absent at {paths.recon_enabled_flag}. "
            "Create the file to enable recon; remove it to halt."
        )


def is_program_frozen(paths: Paths, platform: str, slug: str) -> bool:
    return paths.freeze_flag(platform, slug).exists()


def freeze_program(paths: Paths, platform: str, slug: str, *, reason: str) -> None:
    flag = paths.freeze_flag(platform, slug)
    flag.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    flag.write_text(f"{timestamp}\n{reason}\n", encoding="utf-8")


def unfreeze_program(paths: Paths, platform: str, slug: str) -> None:
    flag = paths.freeze_flag(platform, slug)
    if flag.exists():
        flag.unlink()


def freeze_reason(paths: Paths, platform: str, slug: str) -> str:
    flag = paths.freeze_flag(platform, slug)
    return flag.read_text(encoding="utf-8") if flag.exists() else ""


def require_program_not_frozen(paths: Paths, platform: str, slug: str) -> None:
    if is_program_frozen(paths, platform, slug):
        reason = freeze_reason(paths, platform, slug).strip()
        raise ProgramFrozen(
            f"Program {platform}/{slug} is frozen.\n{reason}\n"
            "Resolve the underlying issue and remove the FROZEN file to resume."
        )
```

- [ ] **Step 3.4 — Run tests to verify they pass**

Run: `make test`
Expected: all 5 flag tests pass.

- [ ] **Step 3.5 — Commit**

```bash
git add src/earn_money/flags.py tests/test_flags.py
git commit -m "feat: add RECON_ENABLED kill-switch and per-program freeze flags"
```

---

## Task 4 — Database module (SQLite schema)

**Files:**
- Create: `src/earn_money/db.py`
- Create: `tests/test_db.py`

Per-program SQLite database with two tables: `assets` and `findings`. The schema lives in `db.py`; runtime code uses `open_program_db()` to get a connection that creates the schema on first use.

- [ ] **Step 4.1 — Write the failing tests at `tests/test_db.py`**

```python
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
    conn.execute(
        "INSERT INTO findings (finding_hash, vuln_class, target, first_seen, current_state, notes_path) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("abc123", "idor", "https://example.com/api", "2026-05-12T08:00:00Z", "queued", "findings/_queue/x.md"),
    )
    try:
        conn.execute(
            "INSERT INTO findings (finding_hash, vuln_class, target, first_seen, current_state, notes_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("abc123", "idor", "https://example.com/api", "2026-05-12T08:00:00Z", "queued", "findings/_queue/x.md"),
        )
        raise AssertionError("expected IntegrityError on duplicate finding_hash")
    except sqlite3.IntegrityError:
        pass
    conn.close()
```

- [ ] **Step 4.2 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `db` module does not exist.

- [ ] **Step 4.3 — Write `src/earn_money/db.py`**

```python
"""Per-program SQLite store for assets and findings."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
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


def open_db(path: Path) -> sqlite3.Connection:
    """Open (or create) a per-program SQLite database with schema applied."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
```

- [ ] **Step 4.4 — Run tests to verify they pass**

Run: `make test`
Expected: all 4 db tests pass.

- [ ] **Step 4.5 — Commit**

```bash
git add src/earn_money/db.py tests/test_db.py
git commit -m "feat: add SQLite schema for assets and findings"
```

---

## Task 5 — Scope file parser and writer

**Files:**
- Create: `src/earn_money/scope.py`
- Create: `tests/test_scope.py`
- Create: `tests/fixtures/scope_example.md`

The `scope.md` file uses YAML frontmatter for machine-readable fields plus a markdown body for operator notes. The `Scope` dataclass round-trips cleanly. The `scope_hash` is the SHA-256 of the sorted in-scope + out-of-scope list — stable across reorderings.

- [ ] **Step 5.1 — Write the fixture at `tests/fixtures/scope_example.md`**

```markdown
---
platform: hackerone
slug: example
policy: rate-limited-OK
scope_hash: ""
last_synced: ""
in_scope:
  - "*.example.com"
  - "api.example.org"
out_of_scope:
  - "blog.example.com"
---

# Example program

Target intuition lives in this body.
```

- [ ] **Step 5.2 — Write the failing tests at `tests/test_scope.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import scope


def test_read_scope_from_fixture(fixtures_dir: Path) -> None:
    s = scope.read_scope(fixtures_dir / "scope_example.md")
    assert s.platform == "hackerone"
    assert s.slug == "example"
    assert s.policy == "rate-limited-OK"
    assert s.in_scope == ["*.example.com", "api.example.org"]
    assert s.out_of_scope == ["blog.example.com"]
    assert "Target intuition" in s.notes


def test_hash_is_stable_under_reordering() -> None:
    a = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["a", "b", "c"], out_of_scope=["d"], notes="",
        scope_hash="", last_synced="",
    )
    b = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["c", "a", "b"], out_of_scope=["d"], notes="",
        scope_hash="", last_synced="",
    )
    assert scope.compute_hash(a) == scope.compute_hash(b)


def test_hash_changes_when_in_scope_changes() -> None:
    a = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["a"], out_of_scope=[], notes="",
        scope_hash="", last_synced="",
    )
    b = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["a", "b"], out_of_scope=[], notes="",
        scope_hash="", last_synced="",
    )
    assert scope.compute_hash(a) != scope.compute_hash(b)


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["a.example.com"], out_of_scope=[], notes="hello",
        scope_hash="deadbeef", last_synced="2026-05-12T08:00:00Z",
    )
    path = tmp_path / "scope.md"
    scope.write_scope(path, s)
    loaded = scope.read_scope(path)
    assert loaded == s


def test_invalid_policy_rejected(tmp_path: Path) -> None:
    path = tmp_path / "scope.md"
    path.write_text(
        "---\nplatform: x\nslug: y\npolicy: bogus\nscope_hash: ''\nlast_synced: ''\n"
        "in_scope: []\nout_of_scope: []\n---\nbody",
        encoding="utf-8",
    )
    with pytest.raises(scope.InvalidScope):
        scope.read_scope(path)
```

- [ ] **Step 5.3 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `scope` module does not exist.

- [ ] **Step 5.4 — Write `src/earn_money/scope.py`**

```python
"""Parse, validate, write, and hash scope.md files (YAML frontmatter + markdown body)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import frontmatter

Policy = Literal["rate-limited-OK", "manual-only", "ambiguous"]
_ALLOWED_POLICIES: frozenset[str] = frozenset({"rate-limited-OK", "manual-only", "ambiguous"})


class InvalidScope(Exception):
    """Raised when scope.md is malformed or has an unrecognised policy."""


@dataclass(frozen=True)
class Scope:
    platform: str
    slug: str
    policy: Policy
    in_scope: list[str]
    out_of_scope: list[str]
    notes: str
    scope_hash: str
    last_synced: str


def read_scope(path: Path) -> Scope:
    post = frontmatter.load(path)
    meta = post.metadata
    policy = meta.get("policy", "")
    if policy not in _ALLOWED_POLICIES:
        raise InvalidScope(
            f"{path}: unknown policy {policy!r}. "
            f"Allowed: {sorted(_ALLOWED_POLICIES)}"
        )
    return Scope(
        platform=str(meta["platform"]),
        slug=str(meta["slug"]),
        policy=policy,
        in_scope=list(meta.get("in_scope") or []),
        out_of_scope=list(meta.get("out_of_scope") or []),
        notes=post.content,
        scope_hash=str(meta.get("scope_hash") or ""),
        last_synced=str(meta.get("last_synced") or ""),
    )


def write_scope(path: Path, s: Scope) -> None:
    post = frontmatter.Post(
        content=s.notes,
        platform=s.platform,
        slug=s.slug,
        policy=s.policy,
        scope_hash=s.scope_hash,
        last_synced=s.last_synced,
        in_scope=list(s.in_scope),
        out_of_scope=list(s.out_of_scope),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(frontmatter.dumps(post).encode("utf-8") + b"\n")


def compute_hash(s: Scope) -> str:
    joined = "\n".join(sorted(s.in_scope)) + "\n--\n" + "\n".join(sorted(s.out_of_scope))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
```

- [ ] **Step 5.5 — Run tests to verify they pass**

Run: `make test`
Expected: all 5 scope tests pass.

- [ ] **Step 5.6 — Commit**

```bash
git add src/earn_money/scope.py tests/test_scope.py tests/fixtures/scope_example.md
git commit -m "feat: add Scope dataclass with frontmatter parser and stable hash"
```

---

## Task 6 — HackerOne API client

**Files:**
- Create: `src/earn_money/platforms/__init__.py`
- Create: `src/earn_money/platforms/hackerone.py`
- Create: `tests/platforms/__init__.py`
- Create: `tests/platforms/test_hackerone.py`
- Create: `tests/fixtures/hackerone_program_initial.json`

Thin HTTP client. One method: `fetch_structured_scope(handle) -> tuple[list[str], list[str]]` returning `(in_scope, out_of_scope)`. Tests mock the HTTP transport using `httpx.MockTransport`.

- [ ] **Step 6.1 — Create the package init files**

`src/earn_money/platforms/__init__.py`:
```python
"""Platform API clients."""
```

`tests/platforms/__init__.py`:
```
```
(empty)

- [ ] **Step 6.2 — Write the fixture at `tests/fixtures/hackerone_program_initial.json`**

This is a minimal slice of HackerOne's `structured_scopes` response shape.

```json
{
  "data": [
    {
      "id": "1",
      "type": "structured-scope",
      "attributes": {
        "asset_identifier": "*.example.com",
        "asset_type": "WILDCARD",
        "eligible_for_bounty": true,
        "eligible_for_submission": true,
        "instruction": null
      }
    },
    {
      "id": "2",
      "type": "structured-scope",
      "attributes": {
        "asset_identifier": "api.example.org",
        "asset_type": "URL",
        "eligible_for_bounty": true,
        "eligible_for_submission": true,
        "instruction": null
      }
    },
    {
      "id": "3",
      "type": "structured-scope",
      "attributes": {
        "asset_identifier": "blog.example.com",
        "asset_type": "URL",
        "eligible_for_bounty": false,
        "eligible_for_submission": false,
        "instruction": "out of scope"
      }
    }
  ]
}
```

- [ ] **Step 6.3 — Write the failing tests at `tests/platforms/test_hackerone.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from earn_money.platforms import hackerone


def _mock_transport(fixture_path: Path) -> httpx.MockTransport:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.hackerone.com"
        assert request.url.path == "/v1/hackers/programs/example/structured_scopes"
        assert request.headers["accept"] == "application/json"
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def test_fetch_structured_scope_partitions_in_and_oos(fixtures_dir: Path) -> None:
    transport = _mock_transport(fixtures_dir / "hackerone_program_initial.json")
    client = hackerone.Client(
        username="bb-research", token="hai_test", transport=transport
    )
    in_scope, out_of_scope = client.fetch_structured_scope("example")
    assert in_scope == ["*.example.com", "api.example.org"]
    assert out_of_scope == ["blog.example.com"]


def test_fetch_raises_on_non_200(fixtures_dir: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"errors": [{"title": "Forbidden"}]})

    transport = httpx.MockTransport(handler)
    client = hackerone.Client(
        username="bb-research", token="hai_test", transport=transport
    )
    with pytest.raises(hackerone.HackerOneAPIError):
        client.fetch_structured_scope("example")


def test_missing_credentials_raises() -> None:
    with pytest.raises(hackerone.HackerOneAPIError):
        hackerone.Client(username="", token="")
```

- [ ] **Step 6.4 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `platforms.hackerone` does not exist.

- [ ] **Step 6.5 — Write `src/earn_money/platforms/hackerone.py`**

```python
"""HackerOne API client. Scope-fetch only in Phase 1."""

from __future__ import annotations

import httpx

_BASE_URL = "https://api.hackerone.com/v1"


class HackerOneAPIError(Exception):
    """Raised on HTTP failure or missing credentials."""


class Client:
    def __init__(
        self,
        *,
        username: str,
        token: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not username or not token:
            raise HackerOneAPIError(
                "HackerOne credentials missing — set HACKERONE_API_USERNAME "
                "and HACKERONE_API_TOKEN."
            )
        self._client = httpx.Client(
            base_url=_BASE_URL,
            auth=(username, token),
            headers={"Accept": "application/json"},
            transport=transport,
            timeout=timeout,
        )

    def fetch_structured_scope(self, handle: str) -> tuple[list[str], list[str]]:
        """Return (in_scope, out_of_scope) asset identifiers for a program handle."""
        response = self._client.get(f"/hackers/programs/{handle}/structured_scopes")
        if response.status_code != 200:
            raise HackerOneAPIError(
                f"HackerOne API returned {response.status_code} for {handle}: "
                f"{response.text}"
            )
        in_scope: list[str] = []
        out_of_scope: list[str] = []
        for item in response.json().get("data", []):
            attrs = item.get("attributes") or {}
            asset = attrs.get("asset_identifier")
            if not asset:
                continue
            if attrs.get("eligible_for_submission"):
                in_scope.append(asset)
            else:
                out_of_scope.append(asset)
        return in_scope, out_of_scope

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 6.6 — Run tests to verify they pass**

Run: `make test`
Expected: all 3 HackerOne tests pass.

- [ ] **Step 6.7 — Commit**

```bash
git add src/earn_money/platforms/ tests/platforms/ tests/fixtures/hackerone_program_initial.json
git commit -m "feat: add HackerOne API client with structured-scope fetch"
```

---

## Task 7 — Scope-sync runner

**Files:**
- Create: `src/earn_money/runners/__init__.py`
- Create: `src/earn_money/runners/scope_sync.py`
- Create: `tests/runners/__init__.py`
- Create: `tests/runners/test_scope_sync.py`
- Create: `tests/fixtures/hackerone_program_additive.json`
- Create: `tests/fixtures/hackerone_program_destructive.json`

The runner ties everything together. It:

1. Requires `RECON_ENABLED` to exist (kill-switch).
2. Reads `programs/hackerone/<slug>/scope.md`.
3. Refuses to run if the program is already frozen.
4. Fetches current scope from HackerOne.
5. Computes a new hash.
6. Compares against the stored hash:
   - Same hash → updates `last_synced` only.
   - New assets only (additive) → updates `scope.md` with new lists, hash, and timestamp.
   - Any removed assets (destructive) → writes `FROZEN` flag with a reason, leaves `scope.md` untouched.

The runner exposes a `sync_program(paths, platform, slug, client)` function and an `argparse`-driven `main()` for the CLI.

- [ ] **Step 7.1 — Create package init files**

`src/earn_money/runners/__init__.py`:
```python
"""Runners — cron-invoked pipelines."""
```

`tests/runners/__init__.py`:
```
```
(empty)

- [ ] **Step 7.2 — Write the additive fixture at `tests/fixtures/hackerone_program_additive.json`**

```json
{
  "data": [
    {"id":"1","type":"structured-scope","attributes":{"asset_identifier":"*.example.com","asset_type":"WILDCARD","eligible_for_bounty":true,"eligible_for_submission":true,"instruction":null}},
    {"id":"2","type":"structured-scope","attributes":{"asset_identifier":"api.example.org","asset_type":"URL","eligible_for_bounty":true,"eligible_for_submission":true,"instruction":null}},
    {"id":"4","type":"structured-scope","attributes":{"asset_identifier":"new.example.com","asset_type":"URL","eligible_for_bounty":true,"eligible_for_submission":true,"instruction":null}},
    {"id":"3","type":"structured-scope","attributes":{"asset_identifier":"blog.example.com","asset_type":"URL","eligible_for_bounty":false,"eligible_for_submission":false,"instruction":"out of scope"}}
  ]
}
```

- [ ] **Step 7.3 — Write the destructive fixture at `tests/fixtures/hackerone_program_destructive.json`**

```json
{
  "data": [
    {"id":"2","type":"structured-scope","attributes":{"asset_identifier":"api.example.org","asset_type":"URL","eligible_for_bounty":true,"eligible_for_submission":true,"instruction":null}},
    {"id":"3","type":"structured-scope","attributes":{"asset_identifier":"blog.example.com","asset_type":"URL","eligible_for_bounty":false,"eligible_for_submission":false,"instruction":"out of scope"}}
  ]
}
```

(`*.example.com` removed from in-scope — destructive diff.)

- [ ] **Step 7.4 — Write the failing tests at `tests/runners/test_scope_sync.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from earn_money import config, flags, scope
from earn_money.platforms import hackerone
from earn_money.runners import scope_sync


def _client(fixture_path: Path) -> hackerone.Client:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return hackerone.Client(
        username="u", token="t", transport=httpx.MockTransport(handler)
    )


def _seed_scope(paths: config.Paths, slug: str, *, in_scope: list[str], out_of_scope: list[str], scope_hash: str = "") -> scope.Scope:
    s = scope.Scope(
        platform="hackerone", slug=slug, policy="rate-limited-OK",
        in_scope=in_scope, out_of_scope=out_of_scope, notes="seed",
        scope_hash=scope_hash, last_synced="",
    )
    scope.write_scope(paths.scope_file("hackerone", slug), s)
    return s


def test_refuses_without_recon_enabled(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])
    with pytest.raises(flags.ReconDisabled):
        scope_sync.sync_program(paths, "hackerone", "example", _client(fixtures_dir / "hackerone_program_initial.json"))


def test_refuses_when_program_already_frozen(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])
    flags.freeze_program(paths, "hackerone", "example", reason="prior")
    with pytest.raises(flags.ProgramFrozen):
        scope_sync.sync_program(paths, "hackerone", "example", _client(fixtures_dir / "hackerone_program_initial.json"))


def test_initial_sync_records_hash_and_assets(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_initial.json"),
    )

    assert result.action == "updated"
    s = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert sorted(s.in_scope) == ["*.example.com", "api.example.org"]
    assert s.out_of_scope == ["blog.example.com"]
    assert s.scope_hash  # populated
    assert s.last_synced  # populated
    assert not flags.is_program_frozen(paths, "hackerone", "example")


def test_additive_diff_updates_scope(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths, "example",
        in_scope=["*.example.com", "api.example.org"],
        out_of_scope=["blog.example.com"],
    )
    # First sync to establish hash.
    scope_sync.sync_program(paths, "hackerone", "example", _client(fixtures_dir / "hackerone_program_initial.json"))

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_additive.json"),
    )

    assert result.action == "updated"
    s = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert "new.example.com" in s.in_scope
    assert not flags.is_program_frozen(paths, "hackerone", "example")


def test_destructive_diff_freezes_program(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths, "example",
        in_scope=["*.example.com", "api.example.org"],
        out_of_scope=["blog.example.com"],
    )
    scope_sync.sync_program(paths, "hackerone", "example", _client(fixtures_dir / "hackerone_program_initial.json"))

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_destructive.json"),
    )

    assert result.action == "frozen"
    assert flags.is_program_frozen(paths, "hackerone", "example")
    reason = flags.freeze_reason(paths, "hackerone", "example")
    assert "*.example.com" in reason
    # scope.md must NOT be rewritten on a destructive diff.
    s = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert "*.example.com" in s.in_scope


def test_no_change_only_updates_last_synced(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths, "example",
        in_scope=["*.example.com", "api.example.org"],
        out_of_scope=["blog.example.com"],
    )
    scope_sync.sync_program(paths, "hackerone", "example", _client(fixtures_dir / "hackerone_program_initial.json"))
    first = scope.read_scope(paths.scope_file("hackerone", "example"))

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_initial.json"),
    )

    assert result.action == "unchanged"
    second = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert first.scope_hash == second.scope_hash
    assert first.in_scope == second.in_scope
```

- [ ] **Step 7.5 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `runners.scope_sync` does not exist.

- [ ] **Step 7.6 — Write `src/earn_money/runners/scope_sync.py`**

```python
"""Scope-sync runner. Hourly cron entry point."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from earn_money import config, flags, scope
from earn_money.platforms import hackerone

Action = Literal["unchanged", "updated", "frozen"]


@dataclass(frozen=True)
class SyncResult:
    action: Action
    detail: str


def sync_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    client: hackerone.Client,
) -> SyncResult:
    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)

    if platform != "hackerone":
        raise ValueError(f"platform {platform!r} not supported in Phase 1")

    current = scope.read_scope(paths.scope_file(platform, slug))
    fetched_in, fetched_oos = client.fetch_structured_scope(slug)
    fetched = replace(
        current,
        in_scope=fetched_in,
        out_of_scope=fetched_oos,
        scope_hash="",  # recomputed below
    )
    new_hash = scope.compute_hash(fetched)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")

    if new_hash == current.scope_hash:
        scope.write_scope(
            paths.scope_file(platform, slug),
            replace(current, last_synced=timestamp),
        )
        return SyncResult("unchanged", "scope hash unchanged")

    removed_in_scope = sorted(set(current.in_scope) - set(fetched_in))
    if removed_in_scope and current.scope_hash:
        reason = (
            "Destructive scope diff: assets removed from in-scope. "
            f"Removed: {', '.join(removed_in_scope)}. "
            "Operator must verify before resuming."
        )
        flags.freeze_program(paths, platform, slug, reason=reason)
        return SyncResult("frozen", reason)

    scope.write_scope(
        paths.scope_file(platform, slug),
        replace(fetched, scope_hash=new_hash, last_synced=timestamp),
    )
    return SyncResult("updated", f"scope updated, hash={new_hash[:12]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scope-sync")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True, help="program slug")
    parser.add_argument(
        "--root",
        default=Path.cwd(),
        type=Path,
        help="repository root (defaults to CWD)",
    )
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    client = hackerone.Client(
        username=os.environ.get("HACKERONE_API_USERNAME", ""),
        token=os.environ.get("HACKERONE_API_TOKEN", ""),
    )
    try:
        result = sync_program(paths, args.platform, args.program, client)
    except flags.ReconDisabled as e:
        print(f"scope-sync: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"scope-sync: {e}", file=sys.stderr)
        return 3
    finally:
        client.close()
    print(f"scope-sync: {result.action} — {result.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7.7 — Run tests to verify they pass**

Run: `make test`
Expected: all 6 scope-sync tests pass.

- [ ] **Step 7.8 — Commit**

```bash
git add src/earn_money/runners/ tests/runners/ tests/fixtures/hackerone_program_additive.json tests/fixtures/hackerone_program_destructive.json
git commit -m "feat: add scope-sync runner with kill-switch, freeze on destructive diffs"
```

---

## Task 8 — CLI wrapper and operator onboarding docs

**Files:**
- Create: `bin/scope-sync`
- Create: `programs/README.md`

The shell wrapper is a thin shim so cron can call `bin/scope-sync --program <slug>` without needing to know the venv path. `programs/README.md` documents how the operator onboards their first program by hand.

- [ ] **Step 8.1 — Write `bin/scope-sync`**

```sh
#!/bin/sh
# Thin wrapper around the scope-sync runner.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  export HACKERONE_API_USERNAME HACKERONE_API_TOKEN
fi

exec "$ROOT/.venv/bin/python" -m earn_money.runners.scope_sync --root "$ROOT" "$@"
```

- [ ] **Step 8.2 — Make `bin/scope-sync` executable**

Run: `chmod +x bin/scope-sync`

- [ ] **Step 8.3 — Smoke-test the wrapper (sanity)**

Run: `bin/scope-sync --help`
Expected: argparse help text printed; exit 0. (No network call, no scope.md read.)

- [ ] **Step 8.4 — Write `programs/README.md`**

```markdown
# Programs

One subdirectory per onboarded program: `programs/<platform>/<slug>/`.

## Onboarding a new HackerOne program — operator workflow

1. **Pick the program.** Criteria from the design spec: low researcher density, asset class you know well, ToS permits the desired scanning tier.

2. **Decide the policy tier.** Read the program's ToS carefully:
   - `rate-limited-OK` — automated scanning permitted within rate limits. Full pipeline.
   - `manual-only` — automated scanning prohibited. Operator scans by hand; recon runners refuse to start.
   - `ambiguous` — ToS unclear. Send a written clarification request; record the reply in `notes.md`. Use `ambiguous` until the program replies; passive recon only.

3. **Create the program directory and seed `scope.md`** (replace `<slug>` with the program handle):

   ```bash
   mkdir -p programs/hackerone/<slug>
   cat > programs/hackerone/<slug>/scope.md <<'EOF'
   ---
   platform: hackerone
   slug: <slug>
   policy: rate-limited-OK
   scope_hash: ""
   last_synced: ""
   in_scope: []
   out_of_scope: []
   ---

   # <slug>

   Operator notes go here.
   EOF
   ```

4. **Set credentials** in the untracked `.env` file at the repo root:

   ```
   HACKERONE_API_USERNAME="<your handle>"
   HACKERONE_API_TOKEN="hai_xxxxxxxxxxxxxxxx"
   ```

5. **Enable recon** with `touch RECON_ENABLED` (also gitignored).

6. **First sync** to populate the scope from the HackerOne API:

   ```bash
   bin/scope-sync --program <slug>
   ```

   Expected output: `scope-sync: updated — scope updated, hash=<12-char hash>`.

7. **Inspect** `programs/hackerone/<slug>/scope.md`. The `in_scope` and `out_of_scope` lists should now reflect the program's structured scope.

## What happens on subsequent syncs

- No change → `unchanged` action, only `last_synced` is updated.
- New assets added by the program → `updated` action, `scope.md` rewritten.
- Assets removed from in-scope → `frozen` action. A `FROZEN` file is written in the program directory with the reason. Recon for that program halts until the operator reviews the diff and removes `FROZEN`.

## Resuming after a freeze

1. Inspect the diff yourself in the HackerOne program page.
2. Update `programs/hackerone/<slug>/scope.md` to match the new scope (or leave as-is if the removed asset wasn't being scanned).
3. Delete the `FROZEN` file: `rm programs/hackerone/<slug>/FROZEN`.
4. Re-run `bin/scope-sync --program <slug>` to confirm a clean sync.
```

- [ ] **Step 8.5 — Run the smoke check one more time**

Run: `make smoke`
Expected: lint and 21 tests pass.

- [ ] **Step 8.6 — Commit**

```bash
git add bin/scope-sync programs/README.md
git commit -m "feat: add bin/scope-sync wrapper and programs onboarding docs"
```

---

## End-of-plan check

By this point the following should all be true. Run each check before declaring Phase 1 done:

- [ ] `make smoke` exits 0 (lint clean, mypy clean, all tests pass).
- [ ] `bin/scope-sync --help` prints help and exits 0.
- [ ] The pre-commit hook runs `make smoke` and a deliberate sensitive-path stage (`echo > .env; git add -f .env; git commit -m 'x'`) is blocked. (Remove the staged file after the test.)
- [ ] No file in the repo exceeds 200 lines except `docs/superpowers/specs/2026-05-12-earn-money-design.md` (the spec is exempt).
- [ ] `git status` shows a clean working tree.
- [ ] `git push` succeeds (pre-push hook accepts the push because origin is `cocodedk/earn-money`).
- [ ] `RECON_ENABLED` is NOT tracked by git (`git ls-files RECON_ENABLED` is empty), and creating it locally has no commit effect.

If everything above is green, Phase 1 is done. Phase 2 (passive recon: subfinder + httpx + SQLite asset writes) gets its own plan and starts from this foundation.
