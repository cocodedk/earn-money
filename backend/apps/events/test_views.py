"""API tests for the EventViewSet — read-only list/retrieve."""
from __future__ import annotations

import uuid

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget


class _Fixtures(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.project = Project.objects.create(name="acme")
        cls.target_a = ScanTarget.objects.create(
            project=cls.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        cls.target_b = ScanTarget.objects.create(
            project=cls.project,
            base_url="https://webgoat.cocode.dk",
            host="webgoat.cocode.dk",
        )
        cls.run_a = ScanRun.objects.create(project=cls.project, stub_slug="1.1")
        cls.run_b = ScanRun.objects.create(project=cls.project, stub_slug="1.2")
        cls.ev_a1 = Event.log(
            type=EventType.SCAN_TARGET_RUN_STARTED,
            scan_run=cls.run_a, target=cls.target_a,
        )
        cls.ev_a2 = Event.log(
            type=EventType.SCAN_TARGET_RUN_DONE,
            scan_run=cls.run_a, target=cls.target_a,
        )
        cls.ev_b = Event.log(
            type=EventType.SCAN_TARGET_RUN_STARTED,
            scan_run=cls.run_b, target=cls.target_b,
        )


class EventListTests(_Fixtures):
    def test_returns_paginated(self) -> None:
        body = self.client.get(reverse("event-list")).json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}
        assert body["count"] == 3

    def test_filter_by_target(self) -> None:
        r = self.client.get(
            reverse("event-list"), {"target": str(self.target_a.id)}
        )
        assert r.json()["count"] == 2

    def test_filter_by_scan_run(self) -> None:
        r = self.client.get(
            reverse("event-list"), {"scan_run": str(self.run_b.id)}
        )
        assert r.json()["count"] == 1

    def test_filter_by_type(self) -> None:
        r = self.client.get(
            reverse("event-list"),
            {"type": EventType.SCAN_TARGET_RUN_DONE},
        )
        assert r.json()["count"] == 1

    def test_filter_by_multiple_types(self) -> None:
        r = self.client.get(
            reverse("event-list"),
            {"type": [EventType.SCAN_TARGET_RUN_STARTED, EventType.SCAN_TARGET_RUN_DONE]},
        )
        assert r.json()["count"] == 3

    def test_unknown_target_returns_empty(self) -> None:
        r = self.client.get(
            reverse("event-list"), {"target": str(uuid.uuid4())}
        )
        assert r.json()["count"] == 0

    def test_ordered_oldest_first(self) -> None:
        body = self.client.get(reverse("event-list")).json()
        ids = [e["id"] for e in body["results"]]
        assert ids == [
            str(self.ev_a1.id), str(self.ev_a2.id), str(self.ev_b.id),
        ]


class EventRetrieveTests(_Fixtures):
    def test_retrieve_returns_event(self) -> None:
        r = self.client.get(reverse("event-detail", args=[str(self.ev_a1.id)]))
        assert r.status_code == 200
        assert r.json()["type"] == EventType.SCAN_TARGET_RUN_STARTED

    def test_retrieve_unknown_404(self) -> None:
        r = self.client.get(reverse("event-detail", args=[str(uuid.uuid4())]))
        assert r.status_code == 404
