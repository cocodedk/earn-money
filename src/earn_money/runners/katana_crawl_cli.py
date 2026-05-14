"""CLI entry-point and real-tool wiring for the katana_crawl runner."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import threading
import uuid
from collections.abc import Callable
from pathlib import Path

from earn_money import config, flags, policy, roe
from earn_money.recon import katana_tool
from earn_money.recon.katana_tool import KatanaUnavailable
from earn_money.runners import active, katana_crawl
from earn_money.runners.watchdog import Reason

_BATCH_DURATION_S = 1500.0
_BATCH_SIZE = 50  # katana is slower per target than nuclei; smaller batches.
_DEFAULT_DEPTH = 2


def resolve_rate_limit(paths: config.Paths, platform: str, slug: str) -> int:
    return roe.read_roe(paths.roe_file(platform, slug)).max_requests_per_second


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str,
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire kill-switch watchdog + tmpfile + katana subprocess + parser."""
    from earn_money.runners import batch, watchdog

    rate_limit = resolve_rate_limit(paths, platform, slug)

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        abort = threading.Event()
        abort_reason: list[Reason | None] = [None]

        def on_state_change(reason: Reason) -> None:
            abort_reason[0] = reason
            abort.set()

        wd = watchdog.KillSwitchWatchdog(
            paths, platform=platform, slug=slug,
            on_state_change=on_state_change,
            poll_interval_s=5.0,
        )
        wd.start()
        tmp_root = Path(tempfile.mkdtemp(prefix="katana-"))
        try:
            def command_factory(chunk: list[str]) -> list[str]:
                tf = tmp_root / f"seeds-{uuid.uuid4().hex}.txt"
                tf.write_text("\n".join(chunk) + "\n", encoding="utf-8")
                return katana_tool.build_command(
                    str(tf), rate_limit=rate_limit, depth=_DEFAULT_DEPTH,
                )

            try:
                batches_result = batch.run_batches(
                    targets,
                    command_factory=command_factory,
                    max_batch_size=_BATCH_SIZE,
                    max_batch_duration_s=_BATCH_DURATION_S,
                    abort=abort,
                )
            except FileNotFoundError as exc:
                raise KatanaUnavailable(
                    "katana binary not found on PATH; re-run "
                    "scripts/install-vps.sh"
                ) from exc
        finally:
            wd.stop()
            shutil.rmtree(tmp_root, ignore_errors=True)

        raw_stdout = "\n".join(
            line for b in batches_result.batches for line in b.lines
        )
        raw_stderr = "\n".join(
            b.stderr for b in batches_result.batches if b.stderr
        )
        source_failures = sum(
            1 for b in batches_result.batches
            if b.timed_out or b.return_code not in (0, None)
        )
        timed_out = any(b.timed_out for b in batches_result.batches)
        parsed = katana_tool.parse_jsonl(raw_stdout)
        return active.ToolRunResult(
            outputs=tuple(parsed),
            aborted=batches_result.aborted,
            terminated_reason=abort_reason[0],
            source_failures=source_failures,
            timed_out=timed_out,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
        )

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="katana-crawl")
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
        result = katana_crawl.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id, max_targets=args.max_targets,
        )
    except flags.ReconDisabled as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 4
    except roe.InvalidRoE as e:
        print(f"katana-crawl: invalid roe.md: {e}", file=sys.stderr)
        return 6
    except KatanaUnavailable as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 7
    except Exception as e:
        print(
            f"katana-crawl: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    if result.prereq_skipped:
        print("katana-crawl: skipped — no recent httpx run; run bin/httpx-probe first")
    else:
        print(
            f"katana-crawl: scanned={result.targets_scanned} "
            f"discovered={result.outputs_recorded} "
            f"oos_drops={result.oos_drops} "
            f"source_failures={result.source_failures}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
