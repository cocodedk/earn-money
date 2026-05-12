from __future__ import annotations

import sys
import threading
import time

from earn_money.runners import batch


def _fake_tool_script() -> list[str]:
    """A tiny Python one-liner that echoes its argv targets as JSONL."""
    return [
        sys.executable, "-c",
        "import sys, json\n"
        "for a in sys.argv[1:]:\n"
        "    print(json.dumps({'target': a}))",
    ]


def test_batches_split_targets_by_size() -> None:
    targets = [f"t{i}" for i in range(7)]
    calls: list[list[str]] = []

    def factory(chunk: list[str]) -> list[str]:
        calls.append(chunk)
        return _fake_tool_script() + chunk

    result = batch.run_batches(
        targets, command_factory=factory,
        max_batch_size=3, max_batch_duration_s=10.0,
    )
    assert [len(c) for c in calls] == [3, 3, 1]
    assert sum(len(b.lines) for b in result.batches) == 7


def test_batch_timeout_terminates_subprocess() -> None:
    def factory(_chunk: list[str]) -> list[str]:
        return [sys.executable, "-c", "import time; time.sleep(10)"]

    result = batch.run_batches(
        ["x"], command_factory=factory,
        max_batch_size=1, max_batch_duration_s=0.2,
    )
    assert result.batches[0].timed_out is True
    assert result.batches[0].lines == []


def test_watchdog_signal_terminates_in_flight() -> None:
    abort = threading.Event()

    def factory(_chunk: list[str]) -> list[str]:
        return [sys.executable, "-c", "import time; time.sleep(10)"]

    def trigger_abort_soon() -> None:
        time.sleep(0.1)
        abort.set()

    threading.Thread(target=trigger_abort_soon, daemon=True).start()
    result = batch.run_batches(
        ["x"], command_factory=factory,
        max_batch_size=1, max_batch_duration_s=10.0,
        abort=abort,
    )
    assert result.aborted is True
    assert result.batches[0].lines == []
