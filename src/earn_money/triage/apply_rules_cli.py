"""`bin/apply-rules` — retroactive suppression for queued findings.

Walks every `findings WHERE current_state='queued'` row and transitions
those matching a rule in `triage_rules.yaml` to `resolved_info` with
the same audit-note format the live engine uses. Closes the
prospective-only gap of the engine's suppression check.

Audit-note format:
    rule=<rule.name> template=<vuln_class> version=unknown reason=<rule.reason>

`version=unknown` because we don't carry the original nuclei payload
through the queue row. Live-engine suppression has access to the
payload and may set a real version; retro-suppression cannot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from earn_money import config, db
from earn_money._time import now_iso
from earn_money.triage import findings, history, rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apply-rules")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Show what would transition; make no changes.",
    )
    args = parser.parse_args(argv)
    paths = config.Paths.from_root(args.root)

    scope_file = paths.scope_file(args.platform, args.program)
    if not scope_file.exists():
        print(
            f"apply-rules: program {args.platform}/{args.program!r} is not "
            f"registered (no scope.md at {scope_file})",
            file=sys.stderr,
        )
        return 1

    rs = rules.load_rules(paths.root / "triage_rules.yaml")
    now = now_iso()
    applied = 0

    conn = db.open_db(paths.program_db(args.platform, args.program))
    try:
        queued = findings.findings_in_state(
            conn, platform=args.platform, slug=args.program, state="queued",
        )
        for f in queued:
            rule = rules.match(
                rs, vuln_class=f.vuln_class, severity=f.severity_hint,
            )
            if rule is None:
                continue
            print(
                f"would transition {f.finding_hash[:8]} ({f.vuln_class}) "
                f"→ resolved_info via {rule.name}"
            )
            if not args.dry_run:
                note = (
                    f"rule={rule.name} template={f.vuln_class} "
                    f"version=unknown reason={rule.reason}"
                )
                history.transition_state(
                    conn,
                    finding_hash=f.finding_hash,
                    to_state="resolved_info",
                    actor="triage-engine",
                    note=note,
                    now=now,
                )
            applied += 1
    finally:
        conn.close()

    print(f"apply-rules: applied={applied} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
