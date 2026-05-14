"""Tests for triage.verify.promote()."""
from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, db
from earn_money.triage import verify
from earn_money.triage.draft import DraftAlreadyExists, draft_for
from tests.triage.conftest import register_program, seed_queued


def _paths(tmp_path: Path) -> config.Paths:
    return config.Paths.from_root(tmp_path)


def _make_template(paths: config.Paths) -> None:
    d = paths.root / "templates"
    d.mkdir(parents=True, exist_ok=True)
    (d / "report-draft.md").write_text(
        "---\nfinding_hash: {{finding_hash}}\nplatform: {{platform}}\n---\n"
        "# {{title}}\n\n## Summary\n\n[s]\n\n"
        "## Steps to Reproduce\n\n[r]\n\n## Impact\n\n[i]\n",
        encoding="utf-8",
    )


def _open(paths: config.Paths):
    return db.open_db(paths.program_db("hackerone", "example"))


def test_promote_transitions_to_verified(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open(paths)
    seed_queued(conn)

    verify.promote(
        conn, paths,
        platform="hackerone", slug="example",
        finding_hash="h1", actor="operator", note=None,
        now="2026-05-15T10:00:00Z",
    )
    conn.commit()

    row = conn.execute(
        "SELECT current_state FROM findings WHERE finding_hash='h1'"
    ).fetchone()
    assert row[0] == "verified"


def test_promote_writes_draft(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open(paths)
    seed_queued(conn)

    result = verify.promote(
        conn, paths,
        platform="hackerone", slug="example",
        finding_hash="h1", actor="operator", note=None,
        now="2026-05-15T10:00:00Z",
    )

    assert result is not None and result.exists()


def test_promote_template_missing_state_still_transitions(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    register_program(paths)
    # No template created
    conn = _open(paths)
    seed_queued(conn)

    result = verify.promote(
        conn, paths,
        platform="hackerone", slug="example",
        finding_hash="h1", actor="operator", note=None,
        now="2026-05-15T10:00:00Z",
    )
    conn.commit()

    row = conn.execute(
        "SELECT current_state FROM findings WHERE finding_hash='h1'"
    ).fetchone()
    assert row[0] == "verified"
    assert result is None


def test_promote_draft_already_exists_returns_none(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    register_program(paths)
    _make_template(paths)
    conn = _open(paths)
    seed_queued(conn)

    verify.promote(
        conn, paths,
        platform="hackerone", slug="example",
        finding_hash="h1", actor="operator", note=None,
        now="2026-05-15T10:00:00Z",
    )

    # Verify the draft file now exists and draft_for raises for it
    with pytest.raises(DraftAlreadyExists):
        draft_for(paths, platform="hackerone", slug="example", finding_hash="h1")
