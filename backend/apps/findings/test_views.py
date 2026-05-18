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
