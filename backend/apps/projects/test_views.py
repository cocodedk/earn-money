"""API tests for the Projects ModelViewSet — written BEFORE the viewset
per the strict-TDD rule in CLAUDE.md.

Contract matches the API-contract negotiation with agent-em-frontend
(see chat history 2026-05-18):
- Pagination: {count, next, previous, results} via PageNumberPagination
- IDs: UUIDv4 as strings
- Timestamps: ISO-8601 UTC ending in Z
- Errors: DRF defaults — {"field": [...]} on 400, {"detail": "..."} on 4xx
- Denormalized counts on Project: target_count, scan_run_count
- Every write emits one self-describing Event row in the same transaction
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import Event
from apps.events.types import EventType

from .models import Project


class ProjectListTests(APITestCase):
    def test_returns_paginated_shape(self) -> None:
        Project.objects.create(name="acme")
        Project.objects.create(name="bytes")
        r = self.client.get(reverse("project-list"))
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}
        assert body["count"] == 2
        assert len(body["results"]) == 2

    def test_empty_list(self) -> None:
        r = self.client.get(reverse("project-list"))
        assert r.status_code == status.HTTP_200_OK
        assert r.json() == {"count": 0, "next": None, "previous": None, "results": []}

    def test_result_shape_includes_counts_and_timestamps(self) -> None:
        Project.objects.create(name="acme")
        row = self.client.get(reverse("project-list")).json()["results"][0]
        uuid.UUID(row["id"])  # raises if not a valid UUID string
        assert row["name"] == "acme"
        assert row["target_count"] == 0
        assert row["scan_run_count"] == 0
        assert row["created_at"].endswith("Z")
        assert row["updated_at"].endswith("Z")

    def test_counts_denormalized_on_serializer(self) -> None:
        """target_count/scan_run_count come from queryset annotations —
        no N+1. Setting up real related rows verifies the annotation."""
        from apps.scans.models import ScanRun
        from apps.targets.models import ScanTarget

        project = Project.objects.create(name="acme")
        ScanTarget.objects.create(
            project=project, base_url="https://dvwa.cocode.dk", host="dvwa.cocode.dk"
        )
        ScanRun.objects.create(project=project, stub_slug="framework-detection")
        ScanRun.objects.create(project=project, stub_slug="server-headers")
        row = self.client.get(reverse("project-list")).json()["results"][0]
        assert row["target_count"] == 1
        assert row["scan_run_count"] == 2


class ProjectRetrieveTests(APITestCase):
    def test_returns_single_project(self) -> None:
        project = Project.objects.create(name="acme")
        r = self.client.get(reverse("project-detail", args=[project.id]))
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["id"] == str(project.id)
        assert body["name"] == "acme"

    def test_unknown_id_returns_404_with_detail(self) -> None:
        r = self.client.get(reverse("project-detail", args=[uuid.uuid4()]))
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in r.json()


class ProjectCreateTests(APITestCase):
    def test_creates_and_logs_event(self) -> None:
        r = self.client.post(
            reverse("project-list"),
            {"name": "acme", "description": "bb 2026"},
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        body = r.json()
        assert body["name"] == "acme"
        assert body["description"] == "bb 2026"
        assert Project.objects.count() == 1
        ev = Event.objects.get(type=EventType.PROJECT_CREATED)
        assert ev.subject_type == "project"
        assert ev.subject_id == Project.objects.first().id
        assert ev.data["name"] == "acme"
        assert ev.data["description"] == "bb 2026"

    def test_creates_with_only_name(self) -> None:
        r = self.client.post(reverse("project-list"), {"name": "minimal"}, format="json")
        assert r.status_code == status.HTTP_201_CREATED
        assert r.json()["description"] == ""

    def test_missing_name_returns_400_no_event(self) -> None:
        r = self.client.post(reverse("project-list"), {}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in r.json()
        assert Event.objects.count() == 0

    def test_atomic_rollback_when_event_log_fails(self) -> None:
        """Same-transaction discipline — Project row must roll back if
        Event.log() raises."""
        with patch(
            "apps.projects.views.Event.log", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("project-list"), {"name": "acme"}, format="json"
                )
        assert Project.objects.count() == 0
        assert Event.objects.count() == 0


class ProjectUpdateTests(APITestCase):
    def test_patch_updates_and_logs_event(self) -> None:
        project = Project.objects.create(name="acme")
        r = self.client.patch(
            reverse("project-detail", args=[project.id]),
            {"description": "updated"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        project.refresh_from_db()
        assert project.description == "updated"
        ev = Event.objects.get(type=EventType.PROJECT_UPDATED)
        assert ev.data["before"]["description"] == ""
        assert ev.data["after"]["description"] == "updated"

    def test_put_updates_and_logs_event(self) -> None:
        project = Project.objects.create(name="acme", description="old")
        r = self.client.put(
            reverse("project-detail", args=[project.id]),
            {"name": "acme2", "description": "new"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        project.refresh_from_db()
        assert project.name == "acme2"
        ev = Event.objects.get(type=EventType.PROJECT_UPDATED)
        assert ev.data["before"]["name"] == "acme"
        assert ev.data["after"]["name"] == "acme2"


class ProjectDestroyTests(APITestCase):
    def test_destroy_and_logs_event(self) -> None:
        project = Project.objects.create(name="acme", description="bye")
        project_id = project.id
        r = self.client.delete(reverse("project-detail", args=[project.id]))
        assert r.status_code == status.HTTP_204_NO_CONTENT
        assert Project.objects.count() == 0
        ev = Event.objects.get(type=EventType.PROJECT_DELETED)
        assert ev.subject_type == "project"
        assert ev.subject_id == project_id
        assert ev.data["name"] == "acme"
        assert ev.data["description"] == "bye"
