"""`bin/queue` — list pending findings.

DB is the source of truth (per the parent design spec). The
`_queue/<hash>.md` file is the human-readable surface, written by the
engine atomically when the queued row is inserted. Queue listing reads
from the DB only — no `_queue/` directory scan, no consistency check.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from earn_money import config, db
from earn_money.triage import findings
from earn_money.triage.findings import Finding

_SEVERITY_RANK: dict[str, int] = {
    "critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5,
}

_DEFAULT_LIMIT = 5

_HEADER = (
    f"{'hash':<8}  {'severity':<8}  {'vuln_class':<32}  {'asset':<32}  first_seen"
)
_DIVIDER = "-" * len(_HEADER)


def _sort_key(f: Finding) -> tuple[int, str]:
    return (_SEVERITY_RANK.get(f.severity_hint, _SEVERITY_RANK["unknown"]), f.first_seen)


def _format_row(f: Finding) -> str:
    return (
        f"{f.finding_hash[:8]}  {f.severity_hint:<8}  "
        f"{f.vuln_class[:32]:<32}  {f.asset[:32]:<32}  {f.first_seen}"
    )


def list_queued(
    paths: config.Paths, *, platform: str, slug: str, show_all: bool,
) -> list[Finding]:
    conn = db.open_db(paths.program_db(platform, slug))
    try:
        items = findings.findings_in_state(
            conn, platform=platform, slug=slug, state="queued",
        )
    finally:
        conn.close()
    items.sort(key=_sort_key)
    if not show_all:
        items = items[:_DEFAULT_LIMIT]
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="queue")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--all", action="store_true", default=False)
    args = parser.parse_args(argv)
    paths = config.Paths.from_root(args.root)

    rows = list_queued(
        paths, platform=args.platform, slug=args.program, show_all=args.all,
    )
    if not rows:
        print(f"no queued findings for {args.platform}/{args.program}")
        return 0
    print(_HEADER)
    print(_DIVIDER)
    for r in rows:
        print(_format_row(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
