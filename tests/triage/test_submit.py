"""Tests for earn_money.triage.submit — TDD first-pass (RED before GREEN)."""

from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, db
from earn_money.triage import findings, history, submit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paths(tmp_path: Path) -> config.Paths:
    return config.Paths.from_root(tmp_path)


def _open_db(paths: config.Paths, platform: str, slug: str):
    return db.open_db(paths.program_db(platform, slug))


def _seed_queued(conn, finding_hash: str = "abc123") -> None:
    findings.upsert_finding(conn, findings.Finding(
        finding_hash=finding_hash,
        platform="hackerone", slug="example",
        vuln_class="sqli", asset="api.example.com",
        target="https://api.example.com/search?q=1",
        signature="sqli|reflect|param=q",
        title="SQL injection on /search",
        severity_hint="high", confidence=85,
        source_tool="nuclei", source_run_id="run-001",
        evidence_path="recon/outputs/hackerone/example/nuclei/raw.jsonl",
        notes_path="findings/_queue/abc123.md",
        first_seen="2026-05-12T08:00:00Z",
        last_seen="2026-05-12T08:00:00Z",
        occurrence_count=1, current_state="queued",
        state_changed_at="2026-05-12T08:00:00Z",
        external_report_id=None, payout_amount=None, payout_currency=None,
    ))


def _promote_to_verified(conn, finding_hash: str = "abc123") -> None:
    history.transition_state(
        conn, finding_hash=finding_hash, to_state="verified",
        actor="operator", note="manual check passed", now="2026-05-12T09:00:00Z",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_happy_path_verified_to_submitted(tmp_path: Path) -> None:
    """verified → submitted transitions state and writes history row."""
    paths = _paths(tmp_path)
    conn = _open_db(paths, "hackerone", "example")
    _seed_queued(conn)
    _promote_to_verified(conn)
    conn.close()

    submit.submit(
        paths,
        platform="hackerone", slug="example",
        finding_hash="abc123",
        external_report_id=None,
        note="Filed on HackerOne",
        now="2026-05-12T10:00:00Z",
    )

    conn2 = _open_db(paths, "hackerone", "example")
    f = findings.find_by_hash(conn2, "abc123")
    assert f is not None
    assert f.current_state == "submitted"
    assert f.state_changed_at == "2026-05-12T10:00:00Z"

    rows = history.state_history_for_hash(conn2, "abc123")
    states = [(r.from_state, r.to_state, r.actor) for r in rows]
    assert ("verified", "submitted", "operator") in states
    conn2.close()


def test_illegal_transition_queued_to_submitted_raises(tmp_path: Path) -> None:
    """Jumping from queued directly to submitted must raise IllegalStateTransition."""
    paths = _paths(tmp_path)
    conn = _open_db(paths, "hackerone", "example")
    _seed_queued(conn)
    conn.close()

    with pytest.raises(history.IllegalStateTransition):
        submit.submit(
            paths,
            platform="hackerone", slug="example",
            finding_hash="abc123",
            external_report_id=None, note=None,
            now="2026-05-12T10:00:00Z",
        )


def test_external_report_id_stored(tmp_path: Path) -> None:
    """external_report_id is persisted to the findings row when supplied."""
    paths = _paths(tmp_path)
    conn = _open_db(paths, "hackerone", "example")
    _seed_queued(conn)
    _promote_to_verified(conn)
    conn.close()

    submit.submit(
        paths,
        platform="hackerone", slug="example",
        finding_hash="abc123",
        external_report_id="H1-999888",
        note=None,
        now="2026-05-12T10:00:00Z",
    )

    conn2 = _open_db(paths, "hackerone", "example")
    f = findings.find_by_hash(conn2, "abc123")
    assert f is not None
    assert f.external_report_id == "H1-999888"
    conn2.close()


def test_audit_history_row_written(tmp_path: Path) -> None:
    """A state history row exists for the verified→submitted transition."""
    paths = _paths(tmp_path)
    conn = _open_db(paths, "hackerone", "example")
    _seed_queued(conn)
    _promote_to_verified(conn)
    conn.close()

    submit.submit(
        paths,
        platform="hackerone", slug="example",
        finding_hash="abc123",
        external_report_id=None,
        note="confirmed via manual Caido replay",
        now="2026-05-12T10:00:00Z",
    )

    conn2 = _open_db(paths, "hackerone", "example")
    rows = history.state_history_for_hash(conn2, "abc123")
    submit_row = next((r for r in rows if r.to_state == "submitted"), None)
    assert submit_row is not None
    assert submit_row.from_state == "verified"
    assert submit_row.actor == "operator"
    assert submit_row.note == "confirmed via manual Caido replay"
    conn2.close()
