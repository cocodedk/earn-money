"""CLI entry-point and real-tool wiring for nuclei-scan.

Kept in a sibling module so `nuclei_scan.py` itself stays under the
200-line cap.
"""

from __future__ import annotations

import argparse
import sys
import threading
import uuid
from collections.abc import Callable
from pathlib import Path

from earn_money import config, flags, policy, roe
from earn_money._time import now_iso
from earn_money.recon import nuclei_tool
from earn_money.runners import active, nuclei_scan
from earn_money.runners.watchdog import Reason

# Per-batch runtime caps. Tuning history:
#   - Cycle 1 (15 targets x 2 dirs, batch_size=50): just barely fit in
#     1500s, 0 signals produced — but it was a timeout we missed.
#   - Cycle 2 (15 x 5, batch_size=50): silent timeout, 0 outputs.
#   - Cycle 3 (15 x 5, batch_size=5): 3 batches all hit 1500s, 0
#     outputs across the board.
# nuclei's -rl 10 is a GLOBAL rate cap across all targets in one
# process; loading templates + DNS-resolving 5 targets + 5 dirs of
# templates eats most of 1500s before any output. Manual one-target
# probe completes in ~60s. Going to batch_size=1 — each nuclei
# invocation scans one target across all 5 template dirs. 15 batches
# x ~5 min each = ~75 min total, comfortably under the 90-min
# systemd ceiling and well within the per-batch 1500s.
_BATCH_DURATION_S = 1500.0
_BATCH_SIZE = 1


def resolve_rate_limit(paths: config.Paths, platform: str, slug: str) -> int:
    """Read the program's `roe.md` and return its `max_requests_per_second`.

    Missing roe.md falls back to the conservative floor in `roe.default_roe()`.
    Public so tests can exercise it without driving the real subprocess.
    """
    return roe.read_roe(paths.roe_file(platform, slug)).max_requests_per_second


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire the kill-switch watchdog + batch runner + nuclei tool parser.

    The program's roe.md decides `-rl` (rate limit). When the file is
    absent or omits the field, the floor in `roe.default_roe()` applies.
    """
    from earn_money.runners import batch, watchdog

    rate_limit = resolve_rate_limit(paths, platform, slug)

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        abort = threading.Event()
        # P1.1: capture the watchdog reason so the runner can record
        # "kill_switch" vs "freeze" in terminated_reason.  One-element list
        # because nonlocal assignment inside a nested def requires cell binding.
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
        try:
            batches_result = batch.run_batches(
                targets,
                command_factory=lambda chunk: nuclei_tool.build_command(
                    chunk,
                    template_dirs=tuple(sorted(nuclei_tool.APPROVED_TEMPLATE_DIRS)),
                    rate_limit=rate_limit,
                ),
                max_batch_size=_BATCH_SIZE, max_batch_duration_s=_BATCH_DURATION_S,
                abort=abort,
            )
        finally:
            wd.stop()

        raw_stdout = "\n".join(
            line for b in batches_result.batches for line in b.lines
        )
        # BatchResult.stderr is a single string per batch (not stderr_lines).
        raw_stderr = "\n".join(
            b.stderr for b in batches_result.batches if b.stderr
        )
        now = now_iso()
        source_failures = sum(
            1 for b in batches_result.batches
            if b.timed_out or b.return_code not in (0, None)
        )
        timed_out = any(b.timed_out for b in batches_result.batches)
        parsed = nuclei_tool.parse_jsonl(raw_stdout, run_id=run_id, observed_at=now)
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
    parser = argparse.ArgumentParser(prog="nuclei-scan")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--max-targets", type=int, default=None,
        help="Cap in-scope service URLs to the first N alphabetical. "
             "Critical for wildcard-explosion programs — nuclei at "
             "batch_size=1 takes ~5 min per target.",
    )
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex

    try:
        real_tool = _build_real_tool(
            paths, platform=args.platform, slug=args.program, run_id=run_id
        )
        result = nuclei_scan.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id, max_targets=args.max_targets,
        )
    except flags.ReconDisabled as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 4
    except nuclei_tool.UnsafeTemplateProfile as e:
        print(f"nuclei-scan: {e}", file=sys.stderr)
        return 5
    except roe.InvalidRoE as e:
        print(f"nuclei-scan: invalid roe.md: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(
            f"nuclei-scan: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    if result.prereq_skipped:
        print(
            "nuclei-scan: skipped — no recent httpx run; "
            "run bin/httpx-probe first"
        )
    else:
        print(
            f"nuclei-scan: scanned={result.targets_scanned} "
            f"signals={result.outputs_recorded} "
            f"oos_drops={result.oos_drops} "
            f"source_failures={result.source_failures}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
