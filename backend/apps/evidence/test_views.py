"""API tests for the EvidenceViewSet — written BEFORE the viewset."""
from __future__ import annotations

import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.findings.models import Finding
from apps.projects.models import Project
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .models import Evidence


class _Fixtures(APITestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")
        self.target_a = ScanTarget.objects.create(
            project=self.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        self.target_b = ScanTarget.objects.create(
            project=self.project,
            base_url="https://webgoat.cocode.dk",
            host="webgoat.cocode.dk",
        )
        self.run = ScanRun.objects.create(project=self.project, stub_slug="1.1")
        self.other_run = ScanRun.objects.create(project=self.project, stub_slug="1.2")
        self.finding = Finding.objects.create(
            scan_run=self.run, target=self.target_a,
            stub_slug="1.1", title="PHP detected", category="runtime",
        )
        Evidence.objects.create(
            scan_run=self.run, target=self.target_a, finding=self.finding,
            source="cookie", url="https://dvwa.cocode.dk/",
            field="Set-Cookie", matched_value="PHPSESSID",
            content_hash="sha256:a",
        )
        Evidence.objects.create(
            scan_run=self.run, target=self.target_b,
            source="header", url="https://webgoat.cocode.dk/",
            field="X-Powered-By", matched_value="Tomcat",
            content_hash="sha256:b",
        )
        Evidence.objects.create(
            scan_run=self.other_run, target=self.target_a,
            source="html", url="https://dvwa.cocode.dk/",
            content_hash="sha256:c",
        )


class EvidenceListTests(_Fixtures):
    def test_returns_paginated(self) -> None:
        body = self.client.get(reverse("evidence-list")).json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}
        assert body["count"] == 3

    def test_filter_by_scan_run(self) -> None:
        r = self.client.get(reverse("evidence-list"), {"scan_run": str(self.run.id)})
        assert r.json()["count"] == 2

    def test_filter_by_target(self) -> None:
        r = self.client.get(
            reverse("evidence-list"), {"target": str(self.target_b.id)}
        )
        assert r.json()["count"] == 1

    def test_filter_by_source(self) -> None:
        r = self.client.get(reverse("evidence-list"), {"source": "cookie"})
        assert r.json()["count"] == 1

    def test_filter_by_finding(self) -> None:
        r = self.client.get(
            reverse("evidence-list"), {"finding": str(self.finding.id)}
        )
        assert r.json()["count"] == 1

    def test_result_shape(self) -> None:
        row = self.client.get(reverse("evidence-list")).json()["results"][0]
        uuid.UUID(row["id"])
        assert {"scan_run", "target", "finding", "source", "url", "method",
                "field", "matched_value", "raw_excerpt", "content_hash",
                "data", "created_at"}.issubset(row.keys())


class EvidenceRetrieveTests(_Fixtures):
    def test_returns_single(self) -> None:
        ev = Evidence.objects.first()
        r = self.client.get(reverse("evidence-detail", args=[ev.id]))
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["id"] == str(ev.id)

    def test_unknown_id_returns_404(self) -> None:
        r = self.client.get(reverse("evidence-detail", args=[uuid.uuid4()]))
        assert r.status_code == status.HTTP_404_NOT_FOUND


class EvidenceImmutabilityTests(_Fixtures):
    def test_post_returns_405(self) -> None:
        r = self.client.post(reverse("evidence-list"), {}, format="json")
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_returns_405(self) -> None:
        ev = Evidence.objects.first()
        r = self.client.put(
            reverse("evidence-detail", args=[ev.id]), {}, format="json"
        )
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self) -> None:
        ev = Evidence.objects.first()
        r = self.client.delete(reverse("evidence-detail", args=[ev.id]))
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED