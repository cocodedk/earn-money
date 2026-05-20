"""Shared helpers for probe-runner test splits."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from earn_money.agent.observations import ObservationWrapper


def _runner_with_session(observations: list[ObservationWrapper] | None = None):
    """Build a ProbeRunner without actually starting its thread."""
    from earn_money.dashboard.probe_runner import ProbeRunner

    # Construct via factory that bypasses provider env (patched).
    runner = MagicMock(spec=ProbeRunner)
    runner._next_task_hint = None
    runner.session = MagicMock()
    runner.session.observations = observations or []
    # Bind the real _pick_task method to the mock.
    runner._pick_task = ProbeRunner._pick_task.__get__(runner, ProbeRunner)
    return runner


def _grab_meta(runner) -> dict | None:
    """Snapshot the runner's history for the first `meta` event without
    blocking on a non-completed run. `iter_since` would otherwise hang
    until either a terminal event arrives or a keepalive fires."""
    for evt in runner._history.iter_since(0, keepalive_interval=0.01):
        if evt.get("event") == "_keepalive":
            return None
        if evt.get("event") == "meta":
            return evt
    return None


def _events_from(runner) -> list[dict]:
    """Drain the runner's history synchronously and return events.

    Equivalent to the old queue-drain helper, but reads through the
    EventHistory replay buffer. Skips the constructor-time `meta` event
    (seq=1) so per-turn assertions stay index-stable, and strips the
    seq id for backward-compat.
    """
    out: list[dict] = []
    for evt in runner._history.iter_since(0, keepalive_interval=0.01):
        if evt.get("event") == "_keepalive":
            break
        if evt.get("event") == "meta":
            continue
        out.append({"event": evt["event"], "data": evt["data"]})
        if evt["event"] in ("done", "probe_error"):
            break
    return out


def _j(**kwargs) -> str:
    return json.dumps(kwargs)
