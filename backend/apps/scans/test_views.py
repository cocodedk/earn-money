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
        assert row["findings_count"] == 0
        assert row["status"] in {choice.value for choice in RunStatus}
        assert row["created_at"].endswith("Z")

    def test_findings_count_reflects_actual_findings(self) -> None:
        # Seed a run with three findings, then assert the annotation
        # surfaces them. Guards against the annotation accidentally
        # joining the wrong reverse relation.
        from apps.findings.models import Finding
        from apps.targets.models import ScanTarget

        target = ScanTarget.objects.create(
            project=self.project_a,
            base_url="https://x.example",
            host="x.example",
        )
        run = ScanRun.objects.create(
            project=self.project_a, stub_slug="1.1",
        )
        for _ in range(3):
            Finding.objects.create(
                scan_run=run, target=target, stub_slug="1.1",
                title="t", category="x",
            )
        rows = self.client.get(
            reverse("scanrun-list"), {"project": str(self.project_a.id)},
        ).json()["results"]
        row = next(r for r in rows if r["id"] == str(run.id))
        assert row["findings_count"] == 3


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
        # Create response carries the denormalized counts, same as list.
        assert body["target_run_count"] == 2
        assert body["findings_count"] == 0
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


class ScanRunLifecycleActionsApiTests(_CookbookFixtureMixin, APITestCase):
    """Thin wire-up tests for the @action endpoints. Exhaustive transition
    coverage lives in tests.py at the model layer; here we just verify
    the HTTP plumbing routes correctly to the model methods."""

    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")

    def _action_url(self, name: str) -> str:
        return reverse(f"scanrun-{name}", args=[self.run.id])

    def test_start_action_transitions_to_running(self) -> None:
        r = self.client.post(self._action_url("start"))
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["status"] == RunStatus.RUNNING

    def test_start_action_invalid_state_returns_400(self) -> None:
        self.run.status = RunStatus.DONE
        self.run.save()
        r = self.client.post(self._action_url("start"))
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "detail" in r.json()

    def test_pause_action_after_start(self) -> None:
        self.client.post(self._action_url("start"))
        r = self.client.post(self._action_url("pause"))
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["status"] == RunStatus.PAUSED

    def test_resume_action_after_pause(self) -> None:
        self.client.post(self._action_url("start"))
        self.client.post(self._action_url("pause"))
        r = self.client.post(self._action_url("resume"))
        assert r.json()["status"] == RunStatus.RUNNING

    def test_stop_action_from_running(self) -> None:
        self.client.post(self._action_url("start"))
        r = self.client.post(self._action_url("stop"))
        assert r.json()["status"] == RunStatus.STOPPING


class ScanRunEventsActionTests(_CookbookFixtureMixin, APITestCase):
    """GET /api/scan-runs/<uuid>/events/ — chronological event stream
    scoped to one run."""

    def setUp(self) -> None:
        from apps.events.types import EventType

        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")
        self.other_run = ScanRun.objects.create(project=project, stub_slug="1.1")
        # Emit a few events on each run.
        Event.log(type=EventType.SYSTEM_TEST, scan_run=self.run, message="a")
        Event.log(type=EventType.SYSTEM_TEST, scan_run=self.run, message="b")
        Event.log(
            type=EventType.SYSTEM_TEST, scan_run=self.other_run, message="other"
        )

    def test_returns_only_events_for_the_run(self) -> None:
        url = reverse("scanrun-events", args=[self.run.id])
        body = self.client.get(url).json()
        assert body["count"] == 2
        messages = [row["message"] for row in body["results"]]
        assert messages == ["a", "b"]

    def test_paginated_shape(self) -> None:
        url = reverse("scanrun-events", args=[self.run.id])
        body = self.client.get(url).json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}

    def test_unknown_run_returns_404(self) -> None:
        url = reverse("scanrun-events", args=[uuid.uuid4()])
        r = self.client.get(url)
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_post_to_events_returns_405(self) -> None:
        url = reverse("scanrun-events", args=[self.run.id])
        r = self.client.post(url)
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class ScanRunFindingsActionTests(_CookbookFixtureMixin, APITestCase):
    def setUp(self) -> None:
        from apps.findings.models import Finding

        project = Project.objects.create(name="acme")
        target = ScanTarget.objects.create(
            project=project, base_url="https://dvwa.cocode.dk", host="dvwa.cocode.dk"
        )
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")
        other_run = ScanRun.objects.create(project=project, stub_slug="1.2")
        Finding.objects.create(
            scan_run=self.run, target=target, stub_slug="1.1",
            title="In-run finding", category="runtime",
        )
        Finding.objects.create(
            scan_run=other_run, target=target, stub_slug="1.2",
            title="Other run", category="runtime",
        )

    def test_returns_only_findings_for_the_run(self) -> None:
        url = reverse("scanrun-findings", args=[self.run.id])
        body = self.client.get(url).json()
        assert body["count"] == 1
        assert body["results"][0]["title"] == "In-run finding"


class ScanRunEvidenceActionTests(_CookbookFixtureMixin, APITestCase):
    def setUp(self) -> None:
        from apps.evidence.models import Evidence

        project = Project.objects.create(name="acme")
        target = ScanTarget.objects.create(
            project=project, base_url="https://dvwa.cocode.dk", host="dvwa.cocode.dk"
        )
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")
        other_run = ScanRun.objects.create(project=project, stub_slug="1.2")
        Evidence.objects.create(
            scan_run=self.run, target=target, source="cookie",
            url="https://dvwa.cocode.dk/", field="Set-Cookie",
            matched_value="PHPSESSID", content_hash="sha256:a",
        )
        Evidence.objects.create(
            scan_run=other_run, target=target, source="header",
            url="https://dvwa.cocode.dk/", content_hash="sha256:b",
        )

    def test_returns_only_evidence_for_the_run(self) -> None:
        url = reverse("scanrun-evidence", args=[self.run.id])
        body = self.client.get(url).json()
        assert body["count"] == 1
        assert body["results"][0]["matched_value"] == "PHPSESSID"


class ScanRunTargetRunsActionTests(_CookbookFixtureMixin, APITestCase):
    def setUp(self) -> None:
        from apps.evidence.models import Evidence
        from apps.findings.models import Finding

        from .models import ScanTargetRun

        project = Project.objects.create(name="acme")
        self.target_a = ScanTarget.objects.create(
            project=project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        self.target_b = ScanTarget.objects.create(
            project=project,
            base_url="https://webgoat.cocode.dk",
            host="webgoat.cocode.dk",
        )
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")
        self.tr_a = ScanTargetRun.objects.create(
            scan_run=self.run, target=self.target_a,
        )
        self.tr_b = ScanTargetRun.objects.create(
            scan_run=self.run, target=self.target_b,
        )
        # Findings + Evidence on target_a only, to verify per-target
        # denormalized counts.
        for _ in range(3):
            Finding.objects.create(
                scan_run=self.run, target=self.target_a, stub_slug="1.1",
                title="finding", category="runtime",
            )
        Evidence.objects.create(
            scan_run=self.run, target=self.target_a, source="cookie",
            url="https://dvwa.cocode.dk/", field="Set-Cookie",
            matched_value="PHPSESSID", content_hash="sha256:a",
        )

        # Different run on the same project — must NOT contaminate counts.
        other_run = ScanRun.objects.create(project=project, stub_slug="1.2")
        Finding.objects.create(
            scan_run=other_run, target=self.target_a, stub_slug="1.2",
            title="other-run finding", category="runtime",
        )

    def test_returns_each_target_run_with_denormalized_counts(self) -> None:
        url = reverse("scanrun-target-runs", args=[self.run.id])
        body = self.client.get(url).json()
        assert body["count"] == 2
        rows = {r["target"]: r for r in body["results"]}
        # target_a: 3 findings + 1 evidence
        row_a = rows[str(self.target_a.id)]
        assert row_a["target_base_url"] == "https://dvwa.cocode.dk"
        assert row_a["findings_count"] == 3
        assert row_a["evidence_count"] == 1
        assert row_a["status"] == "queued"
        # target_b: zero counts but row present
        row_b = rows[str(self.target_b.id)]
        assert row_b["findings_count"] == 0
        assert row_b["evidence_count"] == 0

    def test_row_exposes_updated_at_and_target_host(self) -> None:
        # em-frontend slice 6B needs `updated_at` for live-freshness
        # diffing until SSE lands, and `target_host` as the canonical
        # short label for the per-target column. See chat msg #1565.
        url = reverse("scanrun-target-runs", args=[self.run.id])
        row = {r["target"]: r for r in self.client.get(url).json()["results"]}[
            str(self.target_a.id)
        ]
        assert row["target_host"] == "dvwa.cocode.dk"
        assert "updated_at" in row and row["updated_at"] is not None

    def test_returns_lifecycle_timestamps(self) -> None:
        from django.utils import timezone

        now = timezone.now()
        self.tr_a.status = "running"
        self.tr_a.started_at = now
        self.tr_a.save()
        url = reverse("scanrun-target-runs", args=[self.run.id])
        body = self.client.get(url).json()
        row_a = {r["target"]: r for r in body["results"]}[str(self.target_a.id)]
        assert row_a["status"] == "running"
        assert row_a["started_at"] is not None
        assert row_a["finished_at"] is None

    def test_unknown_scan_run_returns_404(self) -> None:
        url = reverse("scanrun-target-runs", args=[uuid.uuid4()])
        assert self.client.get(url).status_code == status.HTTP_404_NOT_FOUND

    def test_paginated_shape(self) -> None:
        body = self.client.get(
            reverse("scanrun-target-runs", args=[self.run.id])
        ).json()
        assert "count" in body
        assert "results" in body
