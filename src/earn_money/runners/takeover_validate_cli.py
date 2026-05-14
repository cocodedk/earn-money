"""CLI entry-point and real-tool wiring for the takeover-validate runner.

Kept in a sibling module so `takeover_validate.py` stays under the
200-line cap and the runner core remains tool-agnostic (testable
without a subzy binary on PATH).
"""

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
from earn_money._time import now_iso
from earn_money.recon import subzy_tool
from earn_money.recon.subzy_tool import SubzyUnavailable
from earn_money.runners import active, takeover_validate
from earn_money.runners.watchdog import Reason

_BATCH_DURATION_S = 900.0
_BATCH_SIZE = 200  # subzy is DNS-bound; a single batch handles many hosts.


_REQS_PER_HOST = 2  # subzy ~ 1 DNS + 1 HTTPS probe per target


def resolve_rate_limit(paths: config.Paths, platform: str, slug: str) -> int:
    """Read the program's `roe.md` and return `max_requests_per_second`.

    Missing roe.md falls back to the conservative floor.
    """
    return roe.read_roe(paths.roe_file(platform, slug)).max_requests_per_second


def resolve_subzy_concurrency(rate_limit: int) -> int:
    """Translate RoE `max_requests_per_second` into subzy's `--concurrency`.

    Subzy has no req/s knob; the closest control is concurrent goroutines.
    A goroutine issues roughly one DNS + one HTTPS probe per target, so
    dividing the req/s budget by `_REQS_PER_HOST` keeps actual traffic
    under the declared cap. Always returns at least 1.
    """
    return max(1, rate_limit // _REQS_PER_HOST)


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str,
    *, concurrency: int,
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire kill-switch watchdog + tmpfile + subzy subprocess + parser."""
    from earn_money.runners import batch, watchdog

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
        tmp_root = Path(tempfile.mkdtemp(prefix="subzy-"))
        try:
            def command_factory(chunk: list[str]) -> list[str]:
                # One tmpfile per batch — file path embedded in argv.
                tf = tmp_root / f"targets-{uuid.uuid4().hex}.txt"
                tf.write_text("\n".join(chunk) + "\n", encoding="utf-8")
                return subzy_tool.build_command(
                    str(tf), rate_limit=concurrency,
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
                # `subzy` binary missing on PATH — typed re-raise so the
                # CLI surfaces it as exit 7 with an install hint rather
                # than a generic stack trace.
                raise SubzyUnavailable(
                    "subzy binary not found on PATH; install via "
                    "`go install -v github.com/PentestPad/subzy@latest`"
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
        now = now_iso()
        source_failures = sum(
            1 for b in batches_result.batches
            if b.timed_out or b.return_code not in (0, None)
        )
        timed_out = any(b.timed_out for b in batches_result.batches)
        parsed = subzy_tool.parse_output(
            raw_stdout, run_id=run_id, observed_at=now,
        )
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
    parser = argparse.ArgumentParser(prog="takeover-validate")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--max-targets", type=int, default=None,
        help="Cap in-scope subdomains to the first N (explicit-first sort). "
             "Useful for wildcard-explosion programs.",
    )
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex

    try:
        rate_limit = resolve_rate_limit(paths, args.platform, args.program)
        concurrency = resolve_subzy_concurrency(rate_limit)
        real_tool = _build_real_tool(
            paths, platform=args.platform, slug=args.program, run_id=run_id,
            concurrency=concurrency,
        )
        result = takeover_validate.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id, max_targets=args.max_targets,
            extra_manifest_fields={"subzy_concurrency": concurrency},
        )
    except flags.ReconDisabled as e:
        print(f"takeover-validate: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"takeover-validate: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"takeover-validate: {e}", file=sys.stderr)
        return 4
    except roe.InvalidRoE as e:
        print(f"takeover-validate: invalid roe.md: {e}", file=sys.stderr)
        return 6
    except SubzyUnavailable as e:
        print(f"takeover-validate: {e}", file=sys.stderr)
        return 7
    except Exception as e:
        print(
            f"takeover-validate: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print(
        f"takeover-validate: scanned={result.targets_scanned} "
        f"signals={result.outputs_recorded} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
