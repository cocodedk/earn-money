"""In-memory event-history buffer for the probe dashboard's SSE stream.

The `_serve_probe_stream` handler used to read events out of a single
`queue.Queue` — a single-consumer pattern. That meant page reload, a
second browser tab, or a Last-Event-ID resume all dropped or duplicated
events.

`EventHistory` keeps a per-run append-only log with monotonically
increasing seq IDs. Any subscriber can attach at any time, optionally
declaring "I last saw seq X" via the SSE `Last-Event-ID` header. The
buffer replays everything stored with `seq > X` and then tails new
appends until the run completes (or the subscriber disconnects).
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

# A run lasting `max_turns=10000` (the dashboard form cap) emits roughly
# 4 events per turn (pending / parsed / observation / complete) plus a
# handful of finding events. 50_000 is comfortable headroom and bounds
# worst-case memory under the operator's foreseeable load. The cap
# evicts the oldest entries first, so a very late subscriber still sees
# the most recent activity.
_DEFAULT_CAP = 50_000

_TERMINAL_EVENTS = frozenset({"done", "probe_error"})


class EventHistory:
    """Thread-safe, bounded, append-only event log with seq-based replay."""

    def __init__(self, cap: int = _DEFAULT_CAP) -> None:
        if cap < 1:
            raise ValueError("EventHistory cap must be >= 1")
        self._cap = cap
        self._events: list[dict[str, Any]] = []
        self._next_seq = 1
        self._completed = False
        self._cond = threading.Condition()

    # ── writer side ────────────────────────────────────────────────────

    def append(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Append an event and notify any waiting subscribers. Returns
        the stored event (with its assigned `seq`)."""
        with self._cond:
            event = {"seq": self._next_seq, "event": name, "data": data}
            self._next_seq += 1
            self._events.append(event)
            if len(self._events) > self._cap:
                # Drop oldest entries. A subscriber whose Last-Event-ID
                # is older than the surviving range simply gets whatever
                # is still in the buffer; no crash, no duplicates.
                del self._events[: len(self._events) - self._cap]
            if name in _TERMINAL_EVENTS:
                self._completed = True
            self._cond.notify_all()
            return event

    def is_completed(self) -> bool:
        with self._cond:
            return self._completed

    def snapshot_seqs(self) -> list[int]:
        with self._cond:
            return [e["seq"] for e in self._events]

    # ── reader side ────────────────────────────────────────────────────

    def iter_since(
        self, last_event_id: int = 0, keepalive_interval: float = 15.0,
    ) -> Iterator[dict[str, Any]]:
        """Yield every event with `seq > last_event_id`, in order, then
        tail new appends until the run completes.

        Emits a `_keepalive` placeholder if no event arrives within
        `keepalive_interval` seconds — the SSE handler converts that
        into a `:\\n\\n` comment frame to keep the TCP connection live.
        """
        delivered = last_event_id
        while True:
            with self._cond:
                ready = [e for e in self._events if e["seq"] > delivered]
                if not ready:
                    if self._completed:
                        # No more events will ever arrive; let the
                        # subscriber close cleanly.
                        return
                    got_signal = self._cond.wait(timeout=keepalive_interval)
                    if not got_signal:
                        yield {"event": "_keepalive", "data": {}, "seq": delivered}
                        continue
                    continue
            # Yield outside the lock so a slow subscriber can't stall
            # writers. `delivered` advances monotonically so the next
            # iteration's slice filter naturally skips what we just sent.
            for evt in ready:
                delivered = evt["seq"]
                yield evt
