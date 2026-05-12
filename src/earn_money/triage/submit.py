"""Mark a verified finding as submitted, with audit history.

This is the second human gate. The operator runs `bin/submit` AFTER
filing the report on HackerOne, with the platform's assigned report ID
as the optional last argument. The state-machine transition + audit
row both fire in one SQLite transaction.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from earn_money import config, db
from earn_money._time import now_iso
from earn_money.triage import history


def submit(
    paths: config.Paths,
    *,
    platform: str,
    slug: str,
    finding_hash: str,
    external_report_id: str | None,
    note: str | None,
    now: str,
) -> None:
    """Run transition_state(verified → submitted) and store the report ID."""
    scope_file = paths.scope_file(platform, slug)
    if not scope_file.exists():
        raise ValueError(
            f"program {platform}/{slug!r} is not registered "
            f"(no scope.md at {scope_file})"
        )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        history.transition_state(
            conn,
            finding_hash=finding_hash,
            to_state="submitted",
            actor="operator",
            note=note,
            now=now,
        )
        if external_report_id:
            conn.execute(
                "UPDATE findings SET external_report_id = ? "
                "WHERE finding_hash = ?",
                (external_report_id, finding_hash),
            )
        conn.commit()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="submit")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--hash", required=True, dest="finding_hash")
    parser.add_argument(
        "--report-id",
        default=None,
        dest="external_report_id",
        help="External (platform) report ID after filing.",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="Optional note (e.g. brief verification summary).",
    )
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    now = now_iso()

    try:
        submit(
            paths,
            platform=args.platform,
            slug=args.program,
            finding_hash=args.finding_hash,
            external_report_id=args.external_report_id,
            note=args.note,
            now=now,
        )
    except ValueError as e:
        print(f"submit: {e}", file=sys.stderr)
        return 1
    except history.FindingNotFound as e:
        print(f"submit: finding not found: {e}", file=sys.stderr)
        return 1
    except history.IllegalStateTransition as e:
        print(f"submit: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"submit: unexpected: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    msg = f"submit: {args.finding_hash} marked submitted"
    if args.external_report_id:
        msg += f" (external_report_id={args.external_report_id})"
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
