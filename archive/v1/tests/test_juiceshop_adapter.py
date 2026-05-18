"""Tests for juiceshop_adapter — challenge snapshot and delta."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx

from earn_money import db, juiceshop_adapter
from earn_money.juiceshop_adapter import Challenge, compute_delta, write_report, write_snapshot


def _open_db(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def _challenge(
    cid: int = 1, name: str = "Score Board", solved: bool = False
) -> Challenge:
    return Challenge(
        challenge_id=cid, name=name, category="Misc",
        difficulty=1, solved=solved,
    )


def test_write_and_read_snapshot(tmp_path: Path) -> None:
    conn = _open_db(tmp_path)
    challenges = [_challenge(1, "Score Board", True), _challenge(2, "Admin Section", False)]
    sid = write_snapshot(conn, "pre", challenges)
    rows = conn.execute(
        "SELECT challenge_name, solved FROM juice_shop_scores WHERE snapshot_id=?", (sid,)
    ).fetchall()
    assert len(rows) == 2
    assert {r[0] for r in rows} == {"Score Board", "Admin Section"}
    conn.close()


def test_compute_delta_finds_newly_solved(tmp_path: Path) -> None:
    conn = _open_db(tmp_path)
    pre = [_challenge(1, "Score Board", True), _challenge(2, "Admin Section", False)]
    post = [_challenge(1, "Score Board", True), _challenge(2, "Admin Section", True)]
    write_snapshot(conn, "pre", pre)
    write_snapshot(conn, "post", post)
    delta = compute_delta(conn)
    assert delta["pre_solved"] == 1
    assert delta["post_solved"] == 2
    assert delta["newly_solved"] == ["Admin Section"]
    conn.close()


def test_compute_delta_empty_when_no_snapshots(tmp_path: Path) -> None:
    conn = _open_db(tmp_path)
    delta = compute_delta(conn)
    assert delta["newly_solved"] == []
    conn.close()


def test_write_report_creates_markdown(tmp_path: Path) -> None:
    delta = {
        "pre_solved": 5, "post_solved": 8, "total": 112,
        "newly_solved": ["Score Board", "Admin Section"],
    }
    report_path = tmp_path / "report.md"
    write_report(report_path, delta)
    content = report_path.read_text(encoding="utf-8")
    assert "Newly solved" in content
    assert "Score Board" in content
    assert "8 / 112" in content


def test_fetch_challenges_parses_response() -> None:
    api_response = {
        "status": "success",
        "data": [
            {"id": 1, "name": "Score Board", "category": "Misc",
             "difficulty": 1, "solved": True},
            {"id": 2, "name": "Admin Section", "category": "Broken Access",
             "difficulty": 2, "solved": False},
        ],
    }

    def _handler(req: httpx.Request) -> httpx.Response:
        import json
        return httpx.Response(200, text=json.dumps(api_response))

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        challenges = juiceshop_adapter.fetch_challenges(
            "https://target.cocode.dk", client=client,
        )
    assert len(challenges) == 2
    assert challenges[0].solved is True
    assert challenges[1].name == "Admin Section"
