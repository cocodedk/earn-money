"""CLI entry-point and watchdog wiring for the httpx-probe runner.

Separated from httpx_probe.py (the testable core) so each file stays
under the 200-line cap.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from earn_money import config, flags, policy
from earn_money.runners import active, httpx_probe
from earn_money.runners.watchdog import Reason


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str
) -> httpx_probe.ToolRun:
    """Wire the kill-switch watchdog + batch runner + httpx tool parser."""
    import threading

    from earn_money.recon import httpx_tool
    from earn_money.runners import batch, watchdog

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        abort = threading.Event()
        # P1.1: capture the watchdog reason so the runner can record
        # "kill_switch" vs "freeze" in terminated_reason instead of a
        # generic sentinel. One-element list because nonlocal assignment
        # inside a nested def requires Python cell binding.
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
                command_factory=lambda chunk: httpx_tool.build_command(chunk),
                max_batch_size=50, max_batch_duration_s=300.0,
                abort=abort,
            )
        finally:
            wd.stop()
        raw = "\n".join(line for b in batches_result.batches for line in b.lines)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        source_failures = sum(
            1 for b in batches_result.batches
            if b.timed_out or b.return_code != 0
        )
        timed_out = any(b.timed_out for b in batches_result.batches)
        return active.ToolRunResult(
            outputs=tuple(httpx_tool.parse_jsonl(raw, run_id=run_id, observed_at=now)),
            aborted=batches_result.aborted,
            terminated_reason=abort_reason[0],
            source_failures=source_failures,
            timed_out=timed_out,
        )

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="httpx-probe")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex
    real_tool = _build_real_tool(
        paths, platform=args.platform, slug=args.program, run_id=run_id
    )

    try:
        result = httpx_probe.run_program(
            paths, args.platform, args.program, tool_run=real_tool, run_id=run_id,
        )
    except flags.ReconDisabled as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"httpx-probe: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(
        f"httpx-probe: scanned={result.targets_scanned} "
        f"services={result.targets_scanned - result.oos_drops} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
