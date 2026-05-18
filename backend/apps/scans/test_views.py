"""API tests for the ScanRuns ViewSet — written BEFORE the viewset.

This slice only covers list / retrieve / create. Lifecycle transitions
(start / pause / resume / stop) come in task #38. Update / destroy
return 405 — scan runs are immutable post-create; state moves through
action endpoints.

The create endpoint expects:
  {
    "project": "<uuid>",
    "stub_slug": "1.1",
    "target_ids": ["<uuid>", "..."]
  }

Validates: project exists, stub_slug is a real cookbook stub, every
target_id belongs to the project. On success, creates ScanRun + one
ScanTargetRun per target, all inside one transaction, and logs a
scan_run.created Event with the target_ids in the payload.
"""
from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project
from apps.stubs.tests import write_stub
from apps.targets.models import ScanTarget
from .models import RunStatus, ScanRun, ScanTargetRun


class _CookbookFixtureMixin:
    """Spin up a temp cookbook + override COOKBOOK_ROOT for the test class.

    Used by every test class that needs `validate_stub_slug` to succeed.
    """

    cookbook_dir: str
    _override: object

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()  # type: ignore[misc]
        cls.cookbook_dir = tempfile.mkdtemp()
        write_stub(
            Path(cls.cookbook_dir),
            phase=1, spec=1, phase_slug="information-gathering",
            slug="framework-detection",
            title="Framework detection",
            phase_title="Information gathering",
        )
        cls._override = override_settings(COOKBOOK_ROOT=cls.cookbook_dir)
        cls._override.enable()  # type: ignore[attr-defined]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._override.disable()  # type: ignore[attr-defined]
        shutil.rmtree(cls.cookbook_dir, ignore_errors=True)
        super().tearDownClass()  # type: ignore[misc]


class ScanRunListTests(_CookbookFixtureMixin, APITestCase):
    def setUp(self) -> None:
        self.project_a = Project.objects.create(name="acme")
        self.project_b = Project.objects.create(name="bytes")
        ScanRun.objects.create(project=self.project_a, stub_slug="1.1")
        ScanRun.objects.create(
            project=self.project_b, stub_slug="1.1", status=RunStatus.RUNNING
        )

    def test_returns_paginated_shape(self) -> None:
        r = self.client.get(reverse("scanrun-list"))
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}
        assert body["count"] == 2

    def test_filter_by_project(self) -> None:
        r = self.client.get(
            reverse("scanrun-list"), {"project": str(self.project_a.id)}
        )
        assert r.json()["count"] == 1

    def test_filter_by_status(self) -> None:
        r = self.client.get(reverse("scanrun-list"), {"status": "running"})
        assert r.json()["count"] == 1
        assert r.json()["results"][0]["status"] == "running"

    def test_filter_by_stub_slug(self) -> None:
        r = self.client.get(reverse("scanrun-list"), {"stub_slug": "1.1"})
        assert r.json()["count"] == 2

    def test_result_shape_includes_target_run_count(self) -> None:
        row = self.client.get(reverse("scanrun-list")).json()["results"][0]
        uuid.UUID(row["id"])
        assert row["target_run_count"] == 0
        assert row["status"] in {choice.value for choice in RunStatus}
        assert row["created_at"].endswith("Z")


class ScanRunRetrieveTests(_CookbookFixtureMixin, APITestCase):
    def test_returns_single(self) -> None:
        project = Project.objects.create(name="acme")
        run = ScanRun.objects.create(project=project, stub_slug="1.1")
        r = self.client.get(reverse("scanrun-detail", args=[run.id]))
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["id"] == str(run.id)

    def test_unknown_id_returns_404(self) -> None:
        r = self.client.get(reverse("scanrun-detail", args=[uuid.uuid4()]))
        assert r.status_code == status.HTTP_404_NOT_FOUND


class ScanRunCreateTests(_CookbookFixtureMixin, APITestCase):
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

    def _payload(self, **overrides: object) -> dict[str, object]:
        return {
            "project": str(self.project.id),
            "stub_slug": "1.1",
            "target_ids": [str(self.target_a.id), str(self.target_b.id)],
            **overrides,
        }

    def test_creates_run_and_target_runs_and_logs_event(self) -> None:
        r = self.client.post(reverse("scanrun-list"), self._payload(), format="json")
        assert r.status_code == status.HTTP_201_CREATED
        body = r.json()
        assert body["status"] == RunStatus.QUEUED
        run = ScanRun.objects.get(pk=body["id"])
        assert run.target_runs.count() == 2
        ev = Event.objects.get(type=EventType.SCAN_RUN_CREATED)
        assert ev.data["project_id"] == str(self.project.id)
        assert ev.data["stub_slug"] == "1.1"
        assert set(ev.data["target_ids"]) == {
            str(self.target_a.id), str(self.target_b.id)
        }

    def test_rejects_unknown_stub_slug(self) -> None:
        r = self.client.post(
            reverse("scanrun-list"), self._payload(stub_slug="99.99"), format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "stub_slug" in r.json()
        assert ScanRun.objects.count() == 0
        assert Event.objects.count() == 0

    def test_rejects_target_id_not_in_project(self) -> None:
        other_project = Project.objects.create(name="other")
        outsider = ScanTarget.objects.create(
            project=other_project,
            base_url="https://other.cocode.dk",
            host="other.cocode.dk",
        )
        r = self.client.post(
            reverse("scanrun-list"),
            self._payload(target_ids=[str(self.target_a.id), str(outsider.id)]),
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "target_ids" in r.json()
        assert ScanRun.objects.count() == 0

    def test_rejects_empty_target_ids(self) -> None:
        r = self.client.post(
            reverse("scanrun-list"), self._payload(target_ids=[]), format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_atomic_rollback_when_event_log_fails(self) -> None:
        with patch(
            "apps.scans.views.Event.log", side_effect=RuntimeError("boom")
        ), self.assertRaises(RuntimeError):
            self.client.post(reverse("scanrun-list"), self._payload(), format="json")
        assert ScanRun.objects.count() == 0
        assert ScanTargetRun.objects.count() == 0
        assert Event.objects.count() == 0


class ScanRunImmutabilityTests(_CookbookFixtureMixin, APITestCase):
    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")

    def test_put_returns_405(self) -> None:
        r = self.client.put(
            reverse("scanrun-detail", args=[self.run.id]),
            {"stub_slug": "1.2"},
            format="json",
        )
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_returns_405(self) -> None:
        r = self.client.patch(
            reverse("scanrun-detail", args=[self.run.id]),
            {"stub_slug": "1.2"},
            format="json",
        )
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self) -> None:
        r = self.client.delete(reverse("scanrun-detail", args=[self.run.id]))
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
