"""CLI for graphql-probe — httpx.Client + sequential per-target loop."""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx

from earn_money import config, flags, policy, roe, scope
from earn_money._time import now_iso
from earn_money.recon import graphql_tool
from earn_money.runners import active, graphql_probe

_HTTP_TIMEOUT = 8.0
_USER_AGENT = "earn-money-graphql/1.0 (bb@cocode.dk)"


def resolve_rate_limit(paths: config.Paths, platform: str, slug: str) -> int:
    return roe.read_roe(paths.roe_file(platform, slug)).max_requests_per_second


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str,
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire httpx.Client + scope-aware probe + per-target iteration."""
    s = scope.read_scope(paths.scope_file(platform, slug))

    def host_in_scope(host: str) -> bool:
        return scope.is_in_scope(host, s.in_scope, s.out_of_scope)

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        signals: list[object] = []
        errors = 0
        now = now_iso()
        with httpx.Client(
            timeout=_HTTP_TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            for url in targets:
                try:
                    sigs = graphql_tool.probe(
                        url, client=client, in_scope=host_in_scope,
                        run_id=run_id, observed_at=now,
                    )
                except httpx.HTTPError:
                    errors += 1
                    continue
                signals.extend(sigs)
        summary = f"introspection_signals={len(signals)} per_target_errors={errors}"
        return active.ToolRunResult(
            outputs=tuple(signals),
            source_failures=errors,
            raw_stdout=summary,
        )

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="graphql-probe")
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
        result = graphql_probe.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id, max_targets=args.max_targets,
        )
    except flags.ReconDisabled as e:
        print(f"graphql-probe: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"graphql-probe: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"graphql-probe: {e}", file=sys.stderr)
        return 4
    except roe.InvalidRoE as e:
        print(f"graphql-probe: invalid roe.md: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(
            f"graphql-probe: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    if result.prereq_skipped:
        print(
            "graphql-probe: skipped — no recent httpx run; "
            "run bin/httpx-probe first"
        )
    else:
        print(
            f"graphql-probe: scanned={result.targets_scanned} "
            f"signals={result.outputs_recorded} "
            f"oos_drops={result.oos_drops} "
            f"source_failures={result.source_failures}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
