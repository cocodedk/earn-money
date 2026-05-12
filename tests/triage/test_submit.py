"""Tests for earn_money.triage.submit — TDD first-pass (RED before GREEN)."""

from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, db
from earn_money.triage import findings, history, submit
from tests.triage.conftest import register_program, seed_queued, seed_verified

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paths(tmp_path: Path) -> config.Paths:
    return config.Paths.from_root(tmp_path)


def _open_db(paths: config.Paths, platform: str, slug: str):
    return db.open_db(paths.program_db(platform, slug))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_happy_path_verified_to_submitted(tmp_path: Path) -> None:
    """verified → submitted transitions state and writes history row."""
    paths = _paths(tmp_path)
    register_program(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_queued(conn)
    history.transition_state(
        conn, finding_hash="h1", to_state="verified",
        actor="operator", note="manual check passed", now="2026-05-12T09:00:00Z",
    )
    conn.close()

    submit.submit(
        paths,
        platform="hackerone", slug="example",
        finding_hash="h1",
        external_report_id=None,
        note="Filed on HackerOne",
        now="2026-05-12T10:00:00Z",
    )

    conn2 = _open_db(paths, "hackerone", "example")
    f = findings.find_by_hash(conn2, "h1")
    assert f is not None
    assert f.current_state == "submitted"
    assert f.state_changed_at == "2026-05-12T10:00:00Z"

    rows = history.state_history_for_hash(conn2, "h1")
    states = [(r.from_state, r.to_state, r.actor) for r in rows]
    assert ("verified", "submitted", "operator") in states
    conn2.close()


def test_illegal_transition_queued_to_submitted_raises(tmp_path: Path) -> None:
    """Jumping from queued directly to submitted must raise IllegalStateTransition."""
    paths = _paths(tmp_path)
    register_program(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_queued(conn)
    conn.close()

    with pytest.raises(history.IllegalStateTransition):
        submit.submit(
            paths,
            platform="hackerone", slug="example",
            finding_hash="h1",
            external_report_id=None, note=None,
            now="2026-05-12T10:00:00Z",
        )


def test_external_report_id_stored(tmp_path: Path) -> None:
    """external_report_id is persisted to the findings row when supplied."""
    paths = _paths(tmp_path)
    register_program(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_queued(conn)
    history.transition_state(
        conn, finding_hash="h1", to_state="verified",
        actor="operator", note="manual check passed", now="2026-05-12T09:00:00Z",
    )
    conn.close()

    submit.submit(
        paths,
        platform="hackerone", slug="example",
        finding_hash="h1",
        external_report_id="H1-999888",
        note=None,
        now="2026-05-12T10:00:00Z",
    )

    conn2 = _open_db(paths, "hackerone", "example")
    f = findings.find_by_hash(conn2, "h1")
    assert f is not None
    assert f.external_report_id == "H1-999888"
    conn2.close()


def test_audit_history_row_written(tmp_path: Path) -> None:
    """A state history row exists for the verified→submitted transition."""
    paths = _paths(tmp_path)
    register_program(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_queued(conn)
    history.transition_state(
        conn, finding_hash="h1", to_state="verified",
        actor="operator", note="manual check passed", now="2026-05-12T09:00:00Z",
    )
    conn.close()

    submit.submit(
        paths,
        platform="hackerone", slug="example",
        finding_hash="h1",
        external_report_id=None,
        note="confirmed via manual Caido replay",
        now="2026-05-12T10:00:00Z",
    )

    conn2 = _open_db(paths, "hackerone", "example")
    rows = history.state_history_for_hash(conn2, "h1")
    submit_row = next((r for r in rows if r.to_state == "submitted"), None)
    assert submit_row is not None
    assert submit_row.from_state == "verified"
    assert submit_row.actor == "operator"
    assert submit_row.note == "confirmed via manual Caido replay"
    conn2.close()


def test_submit_refuses_unregistered_program(tmp_path: Path) -> None:
    """submit raises ValueError and does NOT create the program directory."""
    paths = _paths(tmp_path)
    # No scope.md — program not registered

    with pytest.raises(ValueError, match="is not registered"):
        submit.submit(
            paths,
            platform="hackerone", slug="typo-program",
            finding_hash="h1",
            external_report_id=None, note=None,
            now="2026-05-12T10:00:00Z",
        )

    # Phantom directory must NOT have been created
    assert not (paths.root / "programs" / "hackerone" / "typo-program").exists()


def test_submit_twice_raises_illegal_transition(tmp_path: Path) -> None:
    """Submitting an already-submitted finding must raise IllegalStateTransition."""
    paths = _paths(tmp_path)
    register_program(paths)
    conn = _open_db(paths, "hackerone", "example")
    seed_verified(conn)
    conn.close()

    submit.submit(
        paths,
        platform="hackerone", slug="example",
        finding_hash="h1",
        external_report_id=None, note=None,
        now="2026-05-12T10:00:00Z",
    )

    with pytest.raises(history.IllegalStateTransition):
        submit.submit(
            paths,
            platform="hackerone", slug="example",
            finding_hash="h1",
            external_report_id=None, note=None,
            now="2026-05-12T11:00:00Z",
        )
