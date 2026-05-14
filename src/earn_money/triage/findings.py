"""DAO for the v3 `findings` table.

The DAO is deliberately state-immutable: callers cannot pass a new
`current_state` through `upsert_finding`. State changes go through
`earn_money.triage.history.transition_state` (Task 4) which writes an
audit row inside the same transaction as the state UPDATE.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from dataclasses import dataclass
from typing import Literal, get_args

FindingState = Literal[
    "queued", "verified", "submitted",
    "resolved_paid", "resolved_dupe", "resolved_na", "resolved_info",
    "archived",
]

_TERMINAL_STATES: frozenset[FindingState] = frozenset({
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
    current_state: FindingState
    state_changed_at: str
    external_report_id: str | None
    payout_amount: str | None
    payout_currency: str | None


_PLACEHOLDERS = ", ".join("?" * len(dataclasses.fields(Finding)))

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

    If the existing finding is in a terminal state (`resolved_*` or
    `archived`), the call is a no-op: triage cannot resurrect a closed
    finding. Use `transition_state()` (Task 4) only for legitimate state
    advances.

    Runtime guards (enforcing the human gate in code, not just convention):
    - New rows may only be created with `current_state='queued'`.
    - Existing rows refuse a state change — use `transition_state()` instead.
    """
    existing = find_by_hash(conn, f.finding_hash)
    if existing is None:
        if f.current_state != "queued":
            raise ValueError(
                f"upsert_finding refuses to create finding "
                f"{f.finding_hash!r} with state={f.current_state!r}; "
                f"only 'queued' is allowed for new rows."
            )
        _insert(conn, f)
        return
    if f.current_state != existing.current_state:
        raise ValueError(
            f"upsert_finding refuses to change current_state on "
            f"existing finding {f.finding_hash!r}: "
            f"{existing.current_state!r} -> {f.current_state!r}. "
            f"Use transition_state() to advance state."
        )
    if existing.current_state in _TERMINAL_STATES:
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
        f"INSERT INTO findings ({_SELECT_COLUMNS}) VALUES ({_PLACEHOLDERS})",
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
    conn: sqlite3.Connection, *, platform: str, slug: str, state: FindingState
) -> list[Finding]:
    cursor = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM findings "
        "WHERE platform = ? AND slug = ? AND current_state = ? "
        "ORDER BY first_seen",
        (platform, slug, state),
    )
    return [Finding(*row) for row in cursor]


def count_findings_by_state(
    conn: sqlite3.Connection, *, platform: str, slug: str
) -> dict[FindingState, int]:
    """Return a zero-filled count of findings per state for (platform, slug).

    Every value in ``typing.get_args(FindingState)`` is present in the result,
    even when the underlying DB has no row in that state. Callers can rely on
    `result["queued"]` etc. without a `KeyError`.
    """
    counts: dict[FindingState, int] = {s: 0 for s in get_args(FindingState)}
    cursor = conn.execute(
        "SELECT current_state, COUNT(*) FROM findings "
        "WHERE platform = ? AND slug = ? GROUP BY current_state",
        (platform, slug),
    )
    for state, count in cursor:
        if state in counts:
            counts[state] = count
    return counts
