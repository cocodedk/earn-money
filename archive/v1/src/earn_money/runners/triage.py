"""Cron entry point for the triage engine.

Triage produces no target traffic and therefore intentionally skips the
policy gate — a `manual-only` program can still have findings triaged
from operator-fed signals. The kill-switch and per-program freeze flag
ARE still respected so the operator can halt all per-program work in
one place.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from earn_money import config, flags, scope
from earn_money.triage import engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="triage")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    try:
        result = engine.run_program(paths, args.platform, args.program)
    except flags.ReconDisabled as e:
        print(f"triage: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"triage: {e}", file=sys.stderr)
        return 3
    except scope.InvalidScope as e:
        print(f"triage: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(f"triage: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(
        f"triage: runs={result.runs_processed} "
        f"created={result.findings_created} "
        f"refreshed={result.findings_refreshed} "
        f"skipped={result.signals_skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
