"""CLI: snapshot_pre → active pipeline → snapshot_post → score report for Juice Shop."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from earn_money import config, db, flags, juiceshop_adapter
from earn_money.engine import active_pipeline, active_tick_cli

_DEFAULT_BASE_URL = "https://target.cocode.dk"
_DEFAULT_PLATFORM = "local"
_DEFAULT_PROGRAM = "juice-shop"
_HTTP_TIMEOUT = 10.0
_USER_AGENT = "earn-money-juiceshop/1.0 (bb@cocode.dk)"


def _fetch(base_url: str) -> list[juiceshop_adapter.Challenge]:
    with httpx.Client(
        timeout=_HTTP_TIMEOUT, follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        return juiceshop_adapter.fetch_challenges(base_url, client=client)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="juice-shop-run")
    parser.add_argument("--platform", default=_DEFAULT_PLATFORM)
    parser.add_argument("--program", default=_DEFAULT_PROGRAM)
    parser.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--max-targets", type=int, default=None)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)

    try:
        flags.require_recon_enabled(paths)
        flags.require_program_not_frozen(paths, args.platform, args.program)
    except flags.ReconDisabled as e:
        print(f"juice-shop-run: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"juice-shop-run: {e}", file=sys.stderr)
        return 3

    print(f"juice-shop-run: pre-run snapshot from {args.base_url}")
    try:
        pre_challenges = _fetch(args.base_url)
    except Exception as exc:
        print(f"juice-shop-run: pre-snapshot failed: {exc}", file=sys.stderr)
        return 1

    conn = db.open_db(paths.program_db(args.platform, args.program))
    juiceshop_adapter.write_snapshot(conn, "pre", pre_challenges)
    conn.close()
    pre_solved = sum(1 for c in pre_challenges if c.solved)
    print(f"juice-shop-run: pre={pre_solved}/{len(pre_challenges)} solved")

    print("juice-shop-run: running active pipeline")
    pipeline_result = active_pipeline.run_program_pipeline(
        paths, args.platform, args.program,
        tool_factory=active_tick_cli._real_tool_factory,
        max_targets_per_step=args.max_targets,
    )
    active_tick_cli._print_pipeline_result(pipeline_result)
    if pipeline_result.aborted_reason or any(
        s.status == "failed" for s in pipeline_result.steps
    ):
        print("juice-shop-run: pipeline had failures — continuing to post-snapshot",
              file=sys.stderr)

    print("juice-shop-run: post-run snapshot")
    try:
        post_challenges = _fetch(args.base_url)
    except Exception as exc:
        print(f"juice-shop-run: post-snapshot failed: {exc}", file=sys.stderr)
        return 1

    conn = db.open_db(paths.program_db(args.platform, args.program))
    juiceshop_adapter.write_snapshot(conn, "post", post_challenges)
    delta = juiceshop_adapter.compute_delta(conn)
    conn.close()

    report_path = paths.root / f"benchmarks/scores/{args.platform}-{args.program}.md"
    juiceshop_adapter.write_report(report_path, delta)

    print(
        f"juice-shop-run: "
        f"pre={delta['pre_solved']} post={delta['post_solved']} "
        f"total={delta['total']} newly={len(delta['newly_solved'])}"
    )
    print(f"juice-shop-run: report → {report_path}")
    if pipeline_result.aborted_reason or any(
        s.status == "failed" for s in pipeline_result.steps
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
