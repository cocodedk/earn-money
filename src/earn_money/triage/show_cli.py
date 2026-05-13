"""`bin/show <hash-prefix>` — display one finding's notes body + audit
history. Accepts any unique short hash prefix that `bin/queue` shows
(default 8 chars). Errors clearly on ambiguous or missing prefixes.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from earn_money import config, db
from earn_money.triage import history


def _resolve_prefix(
    conn: sqlite3.Connection, prefix: str,
) -> list[tuple[str, str]]:
    cursor = conn.execute(
        "SELECT finding_hash, notes_path FROM findings "
        "WHERE finding_hash LIKE ? ORDER BY finding_hash",
        (prefix + "%",),
    )
    return [(row[0], row[1]) for row in cursor]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="show")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("prefix")
    args = parser.parse_args(argv)
    paths = config.Paths.from_root(args.root)

    scope_file = paths.scope_file(args.platform, args.program)
    if not scope_file.exists():
        print(
            f"show: program {args.platform}/{args.program!r} is not "
            f"registered (no scope.md at {scope_file})",
            file=sys.stderr,
        )
        return 1

    conn = db.open_db(paths.program_db(args.platform, args.program))
    try:
        rows = _resolve_prefix(conn, args.prefix)
        if not rows:
            print(
                f"show: no finding matching prefix {args.prefix!r} "
                f"in {args.platform}/{args.program}",
                file=sys.stderr,
            )
            return 1
        if len(rows) > 1:
            matches = ", ".join(r[0][:12] for r in rows[:5])
            extra = "" if len(rows) <= 5 else f" (+{len(rows) - 5} more)"
            print(
                f"show: ambiguous prefix {args.prefix!r} — matches "
                f"{len(rows)} findings: {matches}{extra}",
                file=sys.stderr,
            )
            return 1
        finding_hash, notes_path = rows[0]
        body_path = paths.root / notes_path
        if body_path.exists():
            print(body_path.read_text(encoding="utf-8"), end="")
        else:
            print(f"(notes file missing at {body_path})")
        print()
        print("--- audit history ---")
        for sc in history.state_history_for_hash(conn, finding_hash):
            frm = sc.from_state or "∅"
            note = sc.note or ""
            print(f"{sc.changed_at}  {frm} → {sc.to_state}  · {sc.actor}  · {note}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
