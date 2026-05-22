"""Event REST ViewSet and SSE event-stream view.

REST: EventViewSet — read-only list/retrieve at /api/events/.
SSE:  scan_run_event_stream — streaming feed at /sse/scan-runs/<uuid>/events/.
"""
from __future__ import annotations

import json
import time
from typing import Iterator

from django.http import Http404, HttpRequest, StreamingHttpResponse
from rest_framework import viewsets

from apps.scans.models import RunStatus, ScanRun

from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """Filters (AND semantics):
      ?target=<uuid>           events for one ScanTarget
      ?scan_run=<uuid>         events for one ScanRun
      ?type=<str>              events of one EventType
      ?type=<a>&type=<b>       events matching any of the listed types (OR)
    """

    serializer_class = EventSerializer

    def get_queryset(self):  # type: ignore[override]
        qs = Event.objects.all()
        params = self.request.query_params
        if params.get("target"):
            qs = qs.filter(target_id=params["target"])
        if params.get("scan_run"):
            qs = qs.filter(scan_run_id=params["scan_run"])
        types = params.getlist("type")
        if types:
            qs = qs.filter(type__in=types)
        return qs


SSE_POLL_INTERVAL = 0.5  # seconds between server-side polls

_TERMINAL = (RunStatus.DONE, RunStatus.STOPPED, RunStatus.FAILED)


def _is_terminal(scan_run_id: str) -> bool:
    return ScanRun.objects.filter(
        id=scan_run_id, status__in=_TERMINAL
    ).exists()


def _format(event: Event) -> bytes:
    payload = EventSerializer(event).data
    frame = (
        f"id: {event.id}\n"
        f"event: {payload['type']}\n"
        f"data: {json.dumps(payload, default=str)}\n\n"
    )
    return frame.encode("utf-8")


def _stream(scan_run_id: str, last_event_id: str | None) -> Iterator[bytes]:
    last_seen_at = None
    if last_event_id:
        try:
            anchor = Event.objects.get(id=last_event_id)
            last_seen_at = anchor.created_at
        except (Event.DoesNotExist, ValueError):
            pass  # fresh start

    while True:
        qs = Event.objects.filter(scan_run_id=scan_run_id)
        if last_seen_at is not None:
            qs = qs.filter(created_at__gt=last_seen_at)
        for event in qs.order_by("created_at"):
            yield _format(event)
            last_seen_at = event.created_at
        if _is_terminal(scan_run_id):
            yield b": stream-closed\n\n"
            return
        time.sleep(SSE_POLL_INTERVAL)


def scan_run_event_stream(
    request: HttpRequest, scan_run_id: str
) -> StreamingHttpResponse:
    if not ScanRun.objects.filter(id=scan_run_id).exists():
        raise Http404("No scan run with that id.")

    response = StreamingHttpResponse(
        _stream(str(scan_run_id), request.headers.get("Last-Event-ID")),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
