"""CLI entry-point and real-tool wiring for sqli-probe."""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx

from earn_money import config, flags, policy, roe
from earn_money._time import now_iso
from earn_money.recon import sqli_tool
from earn_money.runners import active, sqli_probe

_HTTP_TIMEOUT = 10.0
_USER_AGENT = "earn-money-sqli/1.0 (bb@cocode.dk)"


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str,
) -> Callable[[list[str]], active.ToolRunResult]:
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
                    sigs = sqli_tool.probe_url(
                        url, client=client, run_id=run_id, observed_at=now,
                    )
                except httpx.HTTPError:
                    errors += 1
                    continue
                signals.extend(sigs)
        return active.ToolRunResult(
            outputs=tuple(signals),
            source_failures=errors,
            raw_stdout=f"sqli_candidates={len(signals)} errors={errors}",
        )
    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sqli-probe")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--max-targets", type=int, default=None)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex

    try:
        real_tool = _build_real_tool(
            paths, platform=args.platform, slug=args.program, run_id=run_id,
        )
        result = sqli_probe.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id, max_targets=args.max_targets,
        )
    except flags.ReconDisabled as e:
        print(f"sqli-probe: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"sqli-probe: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"sqli-probe: {e}", file=sys.stderr)
        return 4
    except roe.InvalidRoE as e:
        print(f"sqli-probe: invalid roe.md: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(
            f"sqli-probe: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    if result.prereq_skipped:
        print("sqli-probe: skipped — no recent katana run; run bin/katana-crawl first")
    else:
        print(
            f"sqli-probe: scanned={result.targets_scanned} "
            f"signals={result.outputs_recorded} "
            f"source_failures={result.source_failures}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
