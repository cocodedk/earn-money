"""Tests for the SSE event-stream view — written BEFORE the view.

Wire path: `GET /sse/scan-runs/<uuid>/events/` returns
`text/event-stream` and pushes one SSE frame per `Event` row for that
scan run. Stream closes cleanly when the run reaches a terminal status
(done / stopped / failed).

Reconnect support: client sends `Last-Event-ID` header on reconnect;
server resumes from events strictly after that anchor.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project
from apps.scans.models import RunStatus, ScanRun


class SSEStreamTests(TestCase):
    """Single-iteration tests — ScanRun is already terminal on entry,
    so the generator yields everything pending and closes."""

    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(
            project=project, stub_slug="1.1", status=RunStatus.DONE
        )
        Event.log(
            type=EventType.SYSTEM_TEST, scan_run=self.run, message="first"
        )
        Event.log(
            type=EventType.SYSTEM_TEST, scan_run=self.run, message="second"
        )

    def test_returns_event_stream_content_type(self) -> None:
        url = reverse("scanrun-event-stream", args=[self.run.id])
        response = self.client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"
        assert response["Cache-Control"] == "no-cache"
        assert response["X-Accel-Buffering"] == "no"

    def test_streams_all_events_then_closes(self) -> None:
        url = reverse("scanrun-event-stream", args=[self.run.id])
        body = b"".join(self.client.get(url).streaming_content).decode()
        # SSE frames format
        assert "event: system.test" in body
        assert '"message": "first"' in body
        assert '"message": "second"' in body
        # Stream close marker
        assert ": stream-closed" in body

    def test_excludes_events_from_other_runs(self) -> None:
        project = Project.objects.first()
        other = ScanRun.objects.create(
            project=project, stub_slug="1.1", status=RunStatus.DONE
        )
        Event.log(
            type=EventType.SYSTEM_TEST, scan_run=other, message="other-run-event"
        )
        url = reverse("scanrun-event-stream", args=[self.run.id])
        body = b"".join(self.client.get(url).streaming_content).decode()
        assert "other-run-event" not in body

    def test_unknown_run_returns_404(self) -> None:
        import uuid as uuid_mod

        url = reverse("scanrun-event-stream", args=[uuid_mod.uuid4()])
        assert self.client.get(url).status_code == 404


class SSELastEventIdTests(TestCase):
    """Reconnect path: Last-Event-ID header resumes the stream from the
    event strictly after the named anchor."""

    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(
            project=project, stub_slug="1.1", status=RunStatus.DONE
        )
        self.first = Event.log(
            type=EventType.SYSTEM_TEST, scan_run=self.run, message="first"
        )
        self.second = Event.log(
            type=EventType.SYSTEM_TEST, scan_run=self.run, message="second"
        )

    def test_resumes_after_last_event_id(self) -> None:
        url = reverse("scanrun-event-stream", args=[self.run.id])
        response = self.client.get(url, HTTP_LAST_EVENT_ID=str(self.first.id))
        body = b"".join(response.streaming_content).decode()
        assert '"message": "first"' not in body
        assert '"message": "second"' in body

    def test_unknown_last_event_id_treated_as_fresh(self) -> None:
        import uuid as uuid_mod

        url = reverse("scanrun-event-stream", args=[self.run.id])
        response = self.client.get(url, HTTP_LAST_EVENT_ID=str(uuid_mod.uuid4()))
        body = b"".join(response.streaming_content).decode()
        # No filter applied → all events stream as if fresh connect.
        assert '"message": "first"' in body
        assert '"message": "second"' in body


@patch("apps.events.views.time.sleep")
class SSEPollLoopTests(TestCase):
    """Multi-iteration coverage — the `if last_seen_at` true branch
    only fires on the SECOND poll. Force two iterations by stubbing
    the terminal check (False then True)."""

    def test_two_iterations_with_status_flip(self, _sleep) -> None:
        project = Project.objects.create(name="acme")
        run = ScanRun.objects.create(
            project=project, stub_slug="1.1", status=RunStatus.RUNNING
        )
        Event.log(
            type=EventType.SYSTEM_TEST, scan_run=run, message="iter-1"
        )

        # First terminal check: not terminal; second: terminal.
        with patch(
            "apps.events.views._is_terminal", side_effect=[False, True]
        ):
            url = reverse("scanrun-event-stream", args=[run.id])
            body = b"".join(self.client.get(url).streaming_content).decode()

        assert '"message": "iter-1"' in body
        assert ": stream-closed" in body
