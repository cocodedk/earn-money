"""Bounded subprocess batches for active-recon tools.

Each batch is one subprocess invocation. The wrapper splits the input
target list into chunks of ``max_batch_size``, runs each via
``command_factory``, captures stdout JSONL line-by-line, and enforces
``max_batch_duration_s``. A watchdog ``abort`` event terminates the
in-flight subprocess immediately.
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

CommandFactory = Callable[[list[str]], Sequence[str]]


@dataclass(frozen=True)
class BatchResult:
    chunk_size: int
    lines: list[str]
    timed_out: bool
    return_code: int | None
    stderr: str


@dataclass(frozen=True)
class BatchesResult:
    batches: tuple[BatchResult, ...] = field(default_factory=tuple)
    aborted: bool = False


def run_batches(
    targets: Sequence[str],
    *,
    command_factory: CommandFactory,
    max_batch_size: int,
    max_batch_duration_s: float,
    abort: threading.Event | None = None,
) -> BatchesResult:
    if max_batch_size <= 0:
        raise ValueError("max_batch_size must be positive")
    abort_event = abort or threading.Event()
    results: list[BatchResult] = []
    aborted = False

    for chunk in _chunks(targets, max_batch_size):
        if abort_event.is_set():
            aborted = True
            break
        result = _run_one(
            command_factory(chunk), max_batch_duration_s, abort_event,
            chunk_size=len(chunk),
        )
        results.append(result)
        if abort_event.is_set():
            aborted = True
            break

    return BatchesResult(batches=tuple(results), aborted=aborted)


def _chunks(targets: Sequence[str], size: int) -> list[list[str]]:
    return [list(targets[i : i + size]) for i in range(0, len(targets), size)]


def _run_one(
    command: Sequence[str],
    timeout_s: float,
    abort: threading.Event,
    *,
    chunk_size: int,
) -> BatchResult:
    proc = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    # A local done event lets the abort-watcher thread exit without
    # polluting the caller-supplied abort event.
    done = threading.Event()

    def kill_if_aborted() -> None:
        # Wait until either abort fires or the batch finishes normally.
        abort.wait(timeout_s)
        if not done.is_set() and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    abort_thread = threading.Thread(target=kill_if_aborted, daemon=True)
    abort_thread.start()

    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        timed_out = False
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        timed_out = True
    finally:
        done.set()  # signal the abort thread that we're done
        abort_thread.join(timeout=1)

    return BatchResult(
        chunk_size=chunk_size,
        lines=[line for line in stdout.splitlines() if line],
        timed_out=timed_out,
        return_code=proc.returncode,
        stderr=stderr,
    )
