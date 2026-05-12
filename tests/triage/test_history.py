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
