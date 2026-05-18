"""API tests for the Targets ModelViewSet — written BEFORE the viewset.

Matches the API-contract negotiation with agent-em-frontend:
- Pagination shape + UUID strings + ISO timestamps + DRF error shapes.
- Uniqueness on (project, base_url) returns 400, not 500. Validator runs
  at serializer level so the response carries `non_field_errors`.
- Filtering by project via `?project=<uuid>` query param.
- Every write emits one self-describing Event row, atomically with the
  state change.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project

from .models import ScanTarget, TargetStatus


class TargetListTests(APITestCase):
    def setUp(self) -> None:
        self.project_a = Project.objects.create(name="acme")
        self.project_b = Project.objects.create(name="bytes")
        ScanTarget.objects.create(
            project=self.project_a,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        ScanTarget.objects.create(
            project=self.project_b,
            base_url="https://webgoat.cocode.dk",
            host="webgoat.cocode.dk",
        )

    def test_returns_paginated_shape(self) -> None:
        r = self.client.get(reverse("target-list"))
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}
        assert body["count"] == 2

    def test_empty_list(self) -> None:
        ScanTarget.objects.all().delete()
        body = self.client.get(reverse("target-list")).json()
        assert body == {"count": 0, "next": None, "previous": None, "results": []}

    def test_result_shape_includes_fields(self) -> None:
        row = self.client.get(reverse("target-list")).json()["results"][0]
        uuid.UUID(row["id"])
        assert "project" in row
        assert "base_url" in row
        assert "host" in row
        assert "ip" in row
        assert row["status"] in {"active", "retired"}
        assert row["created_at"].endswith("Z")

    def test_filter_by_project(self) -> None:
        r = self.client.get(
            reverse("target-list"), {"project": str(self.project_a.id)}
        )
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["host"] == "dvwa.cocode.dk"


class TargetRetrieveTests(APITestCase):
    def test_returns_single(self) -> None:
        project = Project.objects.create(name="acme")
        target = ScanTarget.objects.create(
            project=project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        body = self.client.get(reverse("target-detail", args=[target.id])).json()
        assert body["id"] == str(target.id)
        assert body["host"] == "dvwa.cocode.dk"

    def test_unknown_id_returns_404(self) -> None:
        r = self.client.get(reverse("target-detail", args=[uuid.uuid4()]))
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in r.json()


class TargetCreateTests(APITestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")

    def test_creates_and_logs_event(self) -> None:
        r = self.client.post(
            reverse("target-list"),
            {
                "project": str(self.project.id),
                "base_url": "https://dvwa.cocode.dk",
                "host": "dvwa.cocode.dk",
                "ip": "89.167.63.167",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        body = r.json()
        assert body["status"] == TargetStatus.ACTIVE
        ev = Event.objects.get(type=EventType.TARGET_CREATED)
        assert ev.data["project_id"] == str(self.project.id)
        assert ev.data["base_url"] == "https://dvwa.cocode.dk"
        assert ev.data["host"] == "dvwa.cocode.dk"
        assert ev.data["ip"] == "89.167.63.167"
        assert ev.data["status"] == "active"

    def test_missing_required_returns_400(self) -> None:
        r = self.client.post(reverse("target-list"), {"host": "x"}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        body = r.json()
        assert "project" in body or "base_url" in body
        assert Event.objects.count() == 0

    def test_uniqueness_returns_400_not_500(self) -> None:
        ScanTarget.objects.create(
            project=self.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        r = self.client.post(
            reverse("target-list"),
            {
                "project": str(self.project.id),
                "base_url": "https://dvwa.cocode.dk",
                "host": "dvwa.cocode.dk",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        # Cross-field validators emit non_field_errors.
        body = r.json()
        assert "non_field_errors" in body
        # Only the existing row from setUp survives; no event for the
        # rejected create.
        assert ScanTarget.objects.count() == 1
        assert Event.objects.filter(type=EventType.TARGET_CREATED).count() == 0

    def test_atomic_rollback_when_event_log_fails(self) -> None:
        with patch(
            "apps.targets.views.Event.log", side_effect=RuntimeError("boom")
        ), self.assertRaises(RuntimeError):
            self.client.post(
                reverse("target-list"),
                {
                    "project": str(self.project.id),
                    "base_url": "https://x.cocode.dk",
                    "host": "x.cocode.dk",
                },
                format="json",
            )
        assert ScanTarget.objects.count() == 0
        assert Event.objects.count() == 0


class TargetUpdateTests(APITestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")
        self.target = ScanTarget.objects.create(
            project=self.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )

    def test_patch_updates_and_logs_event(self) -> None:
        r = self.client.patch(
            reverse("target-detail", args=[self.target.id]),
            {"status": TargetStatus.RETIRED},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        self.target.refresh_from_db()
        assert self.target.status == TargetStatus.RETIRED
        ev = Event.objects.get(type=EventType.TARGET_UPDATED)
        assert ev.data["before"]["status"] == "active"
        assert ev.data["after"]["status"] == "retired"


class TargetDestroyTests(APITestCase):
    def test_destroy_and_logs_event(self) -> None:
        project = Project.objects.create(name="acme")
        target = ScanTarget.objects.create(
            project=project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        target_id = target.id
        r = self.client.delete(reverse("target-detail", args=[target.id]))
        assert r.status_code == status.HTTP_204_NO_CONTENT
        assert ScanTarget.objects.count() == 0
        ev = Event.objects.get(type=EventType.TARGET_DELETED)
        assert ev.subject_id == target_id
        assert ev.data["host"] == "dvwa.cocode.dk"
