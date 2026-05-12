from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

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
    assert row.current_state == "queued"


def test_re_upsert_on_terminal_finding_is_noop(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    # Insert via DAO (queued), then promote to terminal via raw SQL to bypass
    # the state-change guard (simulating what transition_state() would do).
    findings.upsert_finding(conn, _seed_finding(current_state="queued"))
    conn.execute(
        "UPDATE findings SET current_state='resolved_dupe', "
        "state_changed_at='2026-05-12T06:00:00Z' WHERE finding_hash='h1'"
    )
    conn.commit()
    # Re-upsert with same terminal state — must be a no-op.
    findings.upsert_finding(
        conn,
        _seed_finding(last_seen="2026-06-01T05:00:00Z", current_state="resolved_dupe"),
    )
    row = findings.find_by_hash(conn, "h1")
    assert row is not None
    assert row.last_seen == "2026-05-12T05:00:00Z"
    assert row.occurrence_count == 1


def test_findings_in_state_filters_by_program_and_state(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    findings.upsert_finding(conn, _seed_finding(
        finding_hash="h1", current_state="queued",
    ))
    # h2 must be inserted with queued first, then state changes are out-of-scope
    # for this DAO test; for now we use raw SQL to seed h2 in 'verified' to
    # validate the SELECT filter.
    conn.execute(
        "UPDATE findings SET current_state='verified', state_changed_at='t' "
        "WHERE finding_hash='h1'"
    )
    findings.upsert_finding(conn, _seed_finding(
        finding_hash="h2", current_state="queued",
    ))
    findings.upsert_finding(conn, _seed_finding(
        finding_hash="h3", platform="hackerone", slug="other",
        current_state="queued",
    ))
    queued = findings.findings_in_state(
        conn, platform="hackerone", slug="example", state="queued"
    )
    assert [f.finding_hash for f in queued] == ["h2"]


def test_upsert_refuses_new_finding_with_non_queued_state(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    with pytest.raises(ValueError, match="only 'queued' is allowed for new rows"):
        findings.upsert_finding(conn, _seed_finding(current_state="verified"))


def test_upsert_refuses_state_change_on_existing_finding(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    findings.upsert_finding(conn, _seed_finding(current_state="queued"))
    with pytest.raises(ValueError, match="Use transition_state"):
        findings.upsert_finding(conn, _seed_finding(current_state="verified"))


def test_find_by_hash_returns_none_when_missing(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assert findings.find_by_hash(conn, "nonexistent") is None
