"""Tests for EventHistory — the in-memory replay buffer that lets
multiple subscribers (page reload, second tab, Last-Event-ID resume)
all see the same per-run event trace.
"""
import threading
import time

from earn_money.dashboard.probe_history import EventHistory


def _drain(history: EventHistory, last_event_id: int = 0, limit: int = 100) -> list[dict]:
    """Drain up to `limit` events from `history` starting after `last_event_id`,
    bailing out the moment the history is empty so a non-completed run doesn't
    block the test forever.
    """
    out: list[dict] = []
    for evt in history.iter_since(last_event_id, keepalive_interval=0.05):
        if evt.get("event") == "_keepalive":
            return out
        out.append(evt)
        if len(out) >= limit:
            return out
        if evt.get("event") in ("done", "probe_error"):
            return out
    return out


class TestEventHistoryBasics:
    def test_append_assigns_monotonic_seq_starting_at_one(self):
        h = EventHistory()
        e1 = h.append("turn", {"turn": 1})
        e2 = h.append("turn", {"turn": 2})
        assert e1["seq"] == 1
        assert e2["seq"] == 2

    def test_append_preserves_event_name_and_data(self):
        h = EventHistory()
        evt = h.append("turn", {"turn": 1, "stage": "action_pending"})
        assert evt["event"] == "turn"
        assert evt["data"] == {"turn": 1, "stage": "action_pending"}

    def test_terminal_event_marks_history_completed(self):
        h = EventHistory()
        assert h.is_completed() is False
        h.append("done", {"turns": 3})
        assert h.is_completed() is True

    def test_probe_error_also_marks_completed(self):
        h = EventHistory()
        h.append("probe_error", {"message": "boom"})
        assert h.is_completed() is True


class TestLateSubscriber:
    def test_late_subscriber_receives_all_earlier_events(self):
        """A browser that opens the dashboard mid-run must see T1, T2, T3
        before tailing live events. SSE alone can't deliver this; replay can."""
        h = EventHistory()
        h.append("turn", {"turn": 1})
        h.append("turn", {"turn": 2})
        h.append("turn", {"turn": 3})
        h.append("done", {"turns": 3})

        seen = _drain(h, last_event_id=0)
        assert [e["data"].get("turn") for e in seen if e["event"] == "turn"] == [1, 2, 3]
        assert seen[-1]["event"] == "done"

    def test_two_subscribers_independently_see_full_history(self):
        h = EventHistory()
        h.append("turn", {"turn": 1})
        h.append("turn", {"turn": 2})
        h.append("done", {"turns": 2})

        a = _drain(h)
        b = _drain(h)
        assert [e["data"] for e in a] == [e["data"] for e in b]
        assert len(a) == 3


class TestLastEventIdResume:
    def test_resumes_strictly_after_given_seq(self):
        h = EventHistory()
        h.append("turn", {"turn": 1})           # seq=1
        h.append("turn", {"turn": 2})           # seq=2
        h.append("turn", {"turn": 3})           # seq=3
        h.append("done", {"turns": 3})          # seq=4

        seen = _drain(h, last_event_id=2)
        # Should see only seq=3 (T3) and seq=4 (done).
        assert [e["seq"] for e in seen] == [3, 4]
        assert seen[0]["data"]["turn"] == 3

    def test_resume_from_last_seq_returns_only_terminal(self):
        h = EventHistory()
        h.append("turn", {"turn": 1})
        h.append("done", {"turns": 1})
        # Subscriber already saw the turn (seq=1). On reconnect they must
        # still get the done event (seq=2) so they can re-enable the form.
        seen = _drain(h, last_event_id=1)
        assert len(seen) == 1
        assert seen[0]["event"] == "done"

    def test_resume_with_unknown_high_seq_yields_nothing_and_completes(self):
        """If the client claims to have seen seq=99 but the run only ever
        had 4 events and is now done, the subscriber must return cleanly,
        not hang."""
        h = EventHistory()
        for i in range(1, 5):
            h.append("turn", {"turn": i})
        h.append("done", {"turns": 4})
        seen = _drain(h, last_event_id=99)
        assert seen == []


class TestHistoryCap:
    def test_cap_drops_oldest_events_when_exceeded(self):
        h = EventHistory(cap=3)
        for i in range(1, 6):  # emit 5 events into a cap of 3
            h.append("turn", {"turn": i})

        # The three most recent must remain.
        assert h.snapshot_seqs() == [3, 4, 5]

    def test_cap_does_not_break_streaming(self):
        """A subscriber with last_event_id older than the cap still gets
        whatever survives, in order, without crashing."""
        h = EventHistory(cap=2)
        h.append("turn", {"turn": 1})    # buffer: [1]
        h.append("turn", {"turn": 2})    # buffer: [1,2]
        h.append("turn", {"turn": 3})    # buffer: [2,3] (evicts seq=1)
        h.append("done", {"turns": 3})   # buffer: [3,4] (evicts seq=2)

        seen = _drain(h, last_event_id=0)
        # Subscriber missed seq=1,2 entirely — they were evicted before
        # this drain attached. Surviving range is delivered cleanly.
        assert [e["seq"] for e in seen] == [3, 4]


class TestKeepaliveAndBlocking:
    def test_keepalive_emitted_when_no_events_arrive(self):
        h = EventHistory()
        # No events. Subscriber should get one keepalive then we bail.
        out: list[dict] = []
        for evt in h.iter_since(0, keepalive_interval=0.05):
            out.append(evt)
            break
        assert out and out[0]["event"] == "_keepalive"

    def test_subscriber_unblocks_when_event_appended_from_other_thread(self):
        h = EventHistory()
        received: list[dict] = []
        ready = threading.Event()

        def consume() -> None:
            for evt in h.iter_since(0, keepalive_interval=10.0):
                if evt.get("event") == "_keepalive":
                    continue
                received.append(evt)
                ready.set()
                return

        t = threading.Thread(target=consume, daemon=True)
        t.start()
        time.sleep(0.05)   # let consumer wait on the condition
        h.append("turn", {"turn": 1})
        assert ready.wait(timeout=2.0)
        t.join(timeout=2.0)
        assert received and received[0]["data"] == {"turn": 1}


class TestSnapshotApi:
    def test_snapshot_seqs_returns_in_order(self):
        h = EventHistory()
        h.append("turn", {"turn": 1})
        h.append("turn", {"turn": 2})
        h.append("done", {"turns": 2})
        assert h.snapshot_seqs() == [1, 2, 3]
