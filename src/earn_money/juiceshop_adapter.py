"""Juice Shop challenge-score adapter.

Polls `/api/Challenges` before and after a pipeline run, stores snapshots in
`juice_shop_scores`, computes the delta, and writes a markdown report.

This module is separate from the core pipeline — it's only activated by
`bin/juice-shop-run` which owns the pre/snapshot_post/report lifecycle.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from earn_money._time import now_iso


@dataclass(frozen=True)
class Challenge:
    challenge_id: int
    name: str
    category: str
    difficulty: int
    solved: bool


def fetch_challenges(base_url: str, *, client: httpx.Client) -> list[Challenge]:
    """GET /api/Challenges and return the parsed list."""
    resp = client.get(f"{base_url.rstrip('/')}/api/Challenges")
    resp.raise_for_status()
    data: Any = resp.json()
    if not isinstance(data, dict) or data.get("status") != "success":
        raise ValueError(f"unexpected /api/Challenges response: {data!r:.200}")
    out: list[Challenge] = []
    for item in data.get("data", []):
        if not isinstance(item, dict):
            continue
        out.append(Challenge(
            challenge_id=int(item.get("id", 0)),
            name=str(item.get("name", "")),
            category=str(item.get("category", "")),
            difficulty=int(item.get("difficulty", 1)),
            solved=bool(item.get("solved", False)),
        ))
    return out


def write_snapshot(
    conn: sqlite3.Connection,
    snapshot_type: str,
    challenges: list[Challenge],
    *,
    snapshot_id: str | None = None,
) -> str:
    """Write one row per challenge for this snapshot. Returns snapshot_id."""
    sid = snapshot_id or uuid.uuid4().hex
    now = now_iso()
    conn.executemany(
        "INSERT INTO juice_shop_scores "
        "(snapshot_id, snapshot_type, snapshot_time, challenge_id, "
        "challenge_name, category, difficulty, solved) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [
            (sid, snapshot_type, now, c.challenge_id, c.name, c.category,
             c.difficulty, int(c.solved))
            for c in challenges
        ],
    )
    conn.commit()
    return sid


def compute_delta(conn: sqlite3.Connection) -> dict[str, Any]:
    """Compare the most recent 'pre' and 'post' snapshots.

    Returns a dict with keys: pre_solved, post_solved, total, newly_solved.
    """
    pre_row = conn.execute(
        "SELECT snapshot_id FROM juice_shop_scores WHERE snapshot_type='pre' "
        "ORDER BY snapshot_time DESC LIMIT 1"
    ).fetchone()
    post_row = conn.execute(
        "SELECT snapshot_id FROM juice_shop_scores WHERE snapshot_type='post' "
        "ORDER BY snapshot_time DESC LIMIT 1"
    ).fetchone()
    if not pre_row or not post_row:
        return {"pre_solved": 0, "post_solved": 0, "total": 0, "newly_solved": []}

    pre_id, post_id = pre_row[0], post_row[0]
    pre_solved = {
        row[0] for row in conn.execute(
            "SELECT challenge_name FROM juice_shop_scores "
            "WHERE snapshot_id=? AND solved=1", (pre_id,)
        )
    }
    post_data = conn.execute(
        "SELECT challenge_name, category, difficulty, solved "
        "FROM juice_shop_scores WHERE snapshot_id=?", (post_id,)
    ).fetchall()
    total = len(post_data)
    post_solved = {row[0] for row in post_data if row[3]}
    newly_solved = sorted(post_solved - pre_solved)
    return {
        "pre_solved": len(pre_solved),
        "post_solved": len(post_solved),
        "total": total,
        "newly_solved": newly_solved,
    }


def write_report(report_path: Path, delta: dict[str, Any]) -> None:
    """Write a markdown score report to `report_path`."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pre = delta["pre_solved"]
    post = delta["post_solved"]
    total = delta["total"]
    newly = delta["newly_solved"]
    lines = [
        "# Juice Shop Score Report",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Pre-run solved | {pre} / {total} |",
        f"| Post-run solved | {post} / {total} |",
        f"| Newly solved | {len(newly)} |",
        "",
    ]
    if newly:
        lines.append("## Newly solved challenges")
        lines.append("")
        for name in newly:
            lines.append(f"- {name}")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
