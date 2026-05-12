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
from datetime import UTC, datetime
from pathlib import Path

from earn_money import config, flags, policy
from earn_money.recon import nuclei_tool
from earn_money.runners import active, nuclei_scan

# A full http/cves scan against one live host can run 10-20 minutes at
# the spec's -rl 10 throughput cap. 1500s = 25 min gives margin without
# burning the systemd timer's 90-min ceiling.
_BATCH_DURATION_S = 1500.0


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire the kill-switch watchdog + batch runner + nuclei tool parser."""
    from earn_money.runners import batch, watchdog

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        abort = threading.Event()
        # P1.1: capture the watchdog reason so the runner can record
        # "kill_switch" vs "freeze" in terminated_reason.  One-element list
        # because nonlocal assignment inside a nested def requires cell binding.
        abort_reason: list[str | None] = [None]

        def on_state_change(reason: str) -> None:
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
                    chunk, template_dirs=tuple(sorted(nuclei_tool.APPROVED_TEMPLATE_DIRS)),
                ),
                max_batch_size=50, max_batch_duration_s=_BATCH_DURATION_S,
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
        now = datetime.now(UTC).isoformat(timespec="seconds")
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
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex
    real_tool = _build_real_tool(
        paths, platform=args.platform, slug=args.program, run_id=run_id
    )

    try:
        result = nuclei_scan.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id,
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
    except Exception as e:
        print(
            f"nuclei-scan: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print(
        f"nuclei-scan: scanned={result.targets_scanned} "
        f"signals={result.signals_emitted} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
