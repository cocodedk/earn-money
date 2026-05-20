"""API tests for the FindingViewSet — written BEFORE the viewset."""
from __future__ import annotations

import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.projects.models import Project
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .models import Finding, FindingStatus


class _Fixtures(APITestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")
        self.target = ScanTarget.objects.create(
            project=self.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        self.run = ScanRun.objects.create(project=self.project, stub_slug="1.1")
        self.other_run = ScanRun.objects.create(project=self.project, stub_slug="1.2")
        Finding.objects.create(
            scan_run=self.run, target=self.target,
            stub_slug="1.1", title="PHP detected", category="runtime",
            severity="info", confidence="high",
        )
        Finding.objects.create(
            scan_run=self.run, target=self.target,
            stub_slug="1.1", title="Server header leak", category="runtime",
            status=FindingStatus.CONFIRMED,
        )
        Finding.objects.create(
            scan_run=self.other_run, target=self.target,
            stub_slug="1.2", title="Other", category="runtime",
        )


class FindingListTests(_Fixtures):
    def test_returns_paginated(self) -> None:
        body = self.client.get(reverse("finding-list")).json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}
        assert body["count"] == 3

    def test_filter_by_scan_run(self) -> None:
        r = self.client.get(reverse("finding-list"), {"scan_run": str(self.run.id)})
        body = r.json()
        assert body["count"] == 2
        assert all(row["scan_run"] == str(self.run.id) for row in body["results"])

    def test_filter_by_status(self) -> None:
        r = self.client.get(reverse("finding-list"), {"status": "confirmed"})
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["title"] == "Server header leak"

    def test_filter_by_stub_slug(self) -> None:
        r = self.client.get(reverse("finding-list"), {"stub_slug": "1.2"})
        assert r.json()["count"] == 1

    def test_result_shape(self) -> None:
        row = self.client.get(reverse("finding-list")).json()["results"][0]
        uuid.UUID(row["id"])
        assert {"scan_run", "target", "stub_slug", "title", "category",
                "severity", "confidence", "status", "data",
                "created_at", "updated_at"}.issubset(row.keys())


class FindingRetrieveTests(_Fixtures):
    def test_returns_single(self) -> None:
        finding = Finding.objects.first()
        r = self.client.get(reverse("finding-detail", args=[finding.id]))
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["id"] == str(finding.id)

    def test_unknown_id_returns_404(self) -> None:
        r = self.client.get(reverse("finding-detail", args=[uuid.uuid4()]))
        assert r.status_code == status.HTTP_404_NOT_FOUND


class FindingImmutabilityTests(_Fixtures):
    def test_post_returns_405(self) -> None:
        r = self.client.post(reverse("finding-list"), {}, format="json")
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_returns_405(self) -> None:
        finding = Finding.objects.first()
        r = self.client.put(
            reverse("finding-detail", args=[finding.id]), {}, format="json"
        )
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self) -> None:
        finding = Finding.objects.first()
        r = self.client.delete(reverse("finding-detail", args=[finding.id]))
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class FindingStatusActionTests(_Fixtures):
    """PATCH /api/findings/<id>/status/  body {"status": "<value>"}.

    Operator triage. Only the status field is updatable via this
    endpoint — title/severity/data/etc. stay untouched through the API.
    Emits `finding.status_changed` event with before/after.
    """

    def _patch(self, finding_id, body):
        url = reverse("finding-status", args=[finding_id])
        return self.client.patch(url, body, format="json")

    def test_valid_status_flip_updates_and_logs_event(self) -> None:
        from apps.events.models import Event
        from apps.events.types import EventType

        finding = Finding.objects.create(
            scan_run=self.run, target=self.target,
            stub_slug="1.1", title="new finding", category="runtime",
        )
        r = self._patch(finding.id, {"status": FindingStatus.CONFIRMED})
        assert r.status_code == status.HTTP_200_OK
        finding.refresh_from_db()
        assert finding.status == FindingStatus.CONFIRMED
        ev = Event.objects.get(type=EventType.FINDING_STATUS_CHANGED)
        assert ev.data["before"] == "candidate"
        assert ev.data["after"] == "confirmed"
        assert ev.data["id"] == str(finding.id)

    def test_invalid_status_returns_400(self) -> None:
        finding = Finding.objects.create(
            scan_run=self.run, target=self.target,
            stub_slug="1.1", title="x", category="runtime",
        )
        r = self._patch(finding.id, {"status": "nonsense"})
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "status" in r.json()
        finding.refresh_from_db()
        assert finding.status == FindingStatus.CANDIDATE  # unchanged

    def test_missing_status_returns_400(self) -> None:
        finding = Finding.objects.create(
            scan_run=self.run, target=self.target,
            stub_slug="1.1", title="x", category="runtime",
        )
        r = self._patch(finding.id, {})
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_other_fields_in_body_are_ignored(self) -> None:
        """Triage endpoint is status-only — other fields in body silently
        dropped by the narrow serializer."""
        finding = Finding.objects.create(
            scan_run=self.run, target=self.target,
            stub_slug="1.1", title="original", category="runtime",
        )
        r = self._patch(finding.id, {
            "status": FindingStatus.REJECTED,
            "title": "tampered",
            "severity": "critical",
        })
        assert r.status_code == status.HTTP_200_OK
        finding.refresh_from_db()
        assert finding.status == FindingStatus.REJECTED
        # Other fields unchanged.
        assert finding.title == "original"
        assert finding.severity == "info"  # default

    def test_unknown_finding_returns_404(self) -> None:
        import uuid as uuid_mod

        r = self._patch(uuid_mod.uuid4(), {"status": "confirmed"})
        assert r.status_code == status.HTTP_404_NOT_FOUND
