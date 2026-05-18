"""CLI entry-point and HTTP wiring for the sourcemap-scan runner.

Sits between the tool-agnostic core (`sourcemap_scan.run_program`) and
the real network — owns the httpx.Client lifecycle, the scope-aware
fetch closure, and the per-URL iteration. Sequential per target so
the natural HTTP latency keeps us well under the RoE rate cap.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx

from earn_money import config, flags, policy, roe, scope
from earn_money._time import now_iso
from earn_money.recon import sourcemap_tool
from earn_money.runners import active, sourcemap_scan

_HTTP_TIMEOUT = 8.0
_USER_AGENT = "earn-money-sourcemap/1.0 (bb@cocode.dk)"


def resolve_rate_limit(paths: config.Paths, platform: str, slug: str) -> int:
    """Read `roe.md` and return `max_requests_per_second`.

    Sequential fetches already self-throttle; the cap is recorded in
    the manifest via the runner for audit, but enforcement here is
    a soft limit (httpx default behaviour).
    """
    return roe.read_roe(paths.roe_file(platform, slug)).max_requests_per_second


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str,
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire an httpx.Client + scope-aware fetch + sourcemap_tool.scan_target."""
    s = scope.read_scope(paths.scope_file(platform, slug))

    def host_in_scope(host: str) -> bool:
        return scope.is_in_scope(host, s.in_scope, s.out_of_scope)

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        signals: list[object] = []
        scripts = 0
        maps = 0
        errors = 0
        now = now_iso()
        with httpx.Client(
            timeout=_HTTP_TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            for url in targets:
                try:
                    result = sourcemap_tool.scan_target(
                        url, client=client, in_scope=host_in_scope,
                        run_id=run_id, observed_at=now,
                    )
                except httpx.HTTPError:
                    errors += 1
                    continue
                signals.extend(result.signals)
                scripts += result.scripts_fetched
                maps += result.sourcemaps_fetched
        # Embed scan counters into raw_stdout so the operator can read
        # them via the audit log without re-querying the DB.
        summary = (
            f"scripts_fetched={scripts} sourcemaps_fetched={maps} "
            f"per_target_errors={errors}"
        )
        return active.ToolRunResult(
            outputs=tuple(signals),
            source_failures=errors,
            raw_stdout=summary,
        )

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sourcemap-scan")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--max-targets", type=int, default=None,
        help="Cap in-scope service URLs to the first N (explicit-first sort).",
    )
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex

    try:
        real_tool = _build_real_tool(
            paths, platform=args.platform, slug=args.program, run_id=run_id,
        )
        result = sourcemap_scan.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id, max_targets=args.max_targets,
        )
    except flags.ReconDisabled as e:
        print(f"sourcemap-scan: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"sourcemap-scan: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"sourcemap-scan: {e}", file=sys.stderr)
        return 4
    except roe.InvalidRoE as e:
        print(f"sourcemap-scan: invalid roe.md: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(
            f"sourcemap-scan: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    if result.prereq_skipped:
        print(
            "sourcemap-scan: skipped — no recent httpx run; "
            "run bin/httpx-probe first"
        )
    else:
        print(
            f"sourcemap-scan: scanned={result.targets_scanned} "
            f"signals={result.outputs_recorded} "
            f"oos_drops={result.oos_drops} "
            f"source_failures={result.source_failures}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
