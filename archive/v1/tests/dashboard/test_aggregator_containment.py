"""Per-program error containment tests for the dashboard aggregator.

A failure in one program's scope.md or DB must not blow up the whole
`/api/status` response — the program is rendered with zero counts and
an `error` field, and every other program renders intact.
"""

from __future__ import annotations

from pathlib import Path

from earn_money import db
from earn_money.dashboard import aggregator
from tests.triage.conftest import (
    engine_paths,
    register_program,
    seed_queued,
)

_NOW = "2026-05-14T09:00:00Z"


def test_broken_program_is_contained(tmp_repo: Path) -> None:
    """Missing db.sqlite for one program: zero counts, others intact."""
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        seed_queued(conn)
    finally:
        conn.close()

    # A second program with scope.md but no db.sqlite.
    register_program(paths, platform="hackerone", slug="example2")
    assert not paths.program_db("hackerone", "example2").exists()

    status = aggregator.build_status(paths, now=_NOW)
    assert len(status["programs"]) == 2
    by_slug = {p["slug"]: p for p in status["programs"]}
    # First program data is intact.
    assert by_slug["example"]["finding_states"]["queued"] == 1
    # Second program reports zero counts but is still listed.
    example2 = by_slug["example2"]
    assert example2["finding_states"]["queued"] == 0
    assert all(v == 0 for v in example2["finding_states"].values())
    assert example2["asset_count"] == 0
    assert example2["http_service_count"] == 0
    assert example2["top_queue"] == []
    assert example2["recent_runs"] == []


def test_malformed_scope_is_contained(tmp_repo: Path) -> None:
    """A bad policy: in one scope.md must not blow up the whole response."""
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        seed_queued(conn)
    finally:
        conn.close()

    # Second program: write scope.md directly with an invalid policy so
    # scope.read_scope raises InvalidScope.
    scope_path = paths.scope_file("hackerone", "example2")
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    scope_path.write_text(
        "---\n"
        "platform: hackerone\n"
        "slug: example2\n"
        "policy: junk\n"
        "in_scope: []\n"
        "out_of_scope: []\n"
        "scope_hash: seed\n"
        "last_synced: '2026-05-12T00:00:00Z'\n"
        "---\n",
        encoding="utf-8",
    )

    status = aggregator.build_status(paths, now=_NOW)
    assert len(status["programs"]) == 2
    by_slug = {p["slug"]: p for p in status["programs"]}
    # Healthy program renders fully.
    good = by_slug["example"]
    assert good["policy"] == "rate-limited-OK"
    assert good["finding_states"]["queued"] == 1
    assert good["top_queue"][0]["hash"] == "h1"[:8]
    # Broken program appears with platform+slug+error but no scope fields.
    bad = by_slug["example2"]
    assert bad["platform"] == "hackerone"
    assert bad["slug"] == "example2"
    assert "error" in bad and "InvalidScope" in bad["error"]
    assert bad["finding_states"]["queued"] == 0


def test_malformed_yaml_scope_is_contained(tmp_repo: Path) -> None:
    """A scope.md with syntactically broken YAML must not blow up the
    whole response — scope.read_scope translates yaml.YAMLError to
    InvalidScope, which the aggregator already contains."""
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        seed_queued(conn)
    finally:
        conn.close()

    scope_path = paths.scope_file("hackerone", "example2")
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    # Unclosed list — YAML parser raises YAMLError.
    scope_path.write_text(
        "---\n"
        "platform: hackerone\n"
        "slug: example2\n"
        "policy: [unclosed\n"
        "---\n",
        encoding="utf-8",
    )

    status = aggregator.build_status(paths, now=_NOW)
    assert len(status["programs"]) == 2
    by_slug = {p["slug"]: p for p in status["programs"]}
    assert by_slug["example"]["finding_states"]["queued"] == 1
    bad = by_slug["example2"]
    assert "error" in bad and "InvalidScope" in bad["error"]
    assert bad["finding_states"]["queued"] == 0


def test_missing_required_scope_key_is_contained(tmp_repo: Path) -> None:
    """A scope.md whose YAML parses but omits a required key (here
    `platform:`) must not blow up the whole response — scope.read_scope
    translates the KeyError to InvalidScope."""
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        seed_queued(conn)
    finally:
        conn.close()

    scope_path = paths.scope_file("hackerone", "example2")
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    # YAML parses fine, but `platform:` is missing.
    scope_path.write_text(
        "---\n"
        "slug: example2\n"
        "policy: rate-limited-OK\n"
        "in_scope: []\n"
        "out_of_scope: []\n"
        "scope_hash: seed\n"
        "last_synced: '2026-05-12T00:00:00Z'\n"
        "---\n",
        encoding="utf-8",
    )

    status = aggregator.build_status(paths, now=_NOW)
    assert len(status["programs"]) == 2
    by_slug = {p["slug"]: p for p in status["programs"]}
    assert by_slug["example"]["finding_states"]["queued"] == 1
    bad = by_slug["example2"]
    assert "error" in bad and "InvalidScope" in bad["error"]
    assert bad["finding_states"]["queued"] == 0


def test_unreadable_db_is_contained(tmp_repo: Path) -> None:
    """A non-sqlite file at db.sqlite must not blow up the whole response."""
    paths = engine_paths(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        seed_queued(conn)
    finally:
        conn.close()

    register_program(paths, platform="hackerone", slug="example2")
    db_path = paths.program_db("hackerone", "example2")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("not a sqlite db", encoding="utf-8")

    status = aggregator.build_status(paths, now=_NOW)
    assert len(status["programs"]) == 2
    by_slug = {p["slug"]: p for p in status["programs"]}
    # First program data intact.
    assert by_slug["example"]["finding_states"]["queued"] == 1
    # Second program contained: zero counts, error mentions sqlite error type.
    bad = by_slug["example2"]
    assert all(v == 0 for v in bad["finding_states"].values())
    assert bad["asset_count"] == 0
    assert bad["http_service_count"] == 0
    assert bad["top_queue"] == []
    assert bad["recent_runs"] == []
    assert "error" in bad
    assert "OperationalError" in bad["error"] or "DatabaseError" in bad["error"]
