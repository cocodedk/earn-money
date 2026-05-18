"""ScanRun + ScanTargetRun model tests.

Lifecycle method tests (start/pause/resume/stop) live here too — they're
data-layer behaviour, not API-layer. The action endpoints in
test_views.py only verify the wire-up.
"""
from __future__ import annotations

from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project
from apps.targets.models import ScanTarget

from .exceptions import InvalidTransition
from .models import RunStatus, ScanRun, ScanTargetRun


class ScanRunTests(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")

    def test_defaults_to_queued(self) -> None:
        run = ScanRun.objects.create(project=self.project, stub_slug="framework-detection")
        assert run.status == RunStatus.QUEUED
        assert run.started_at is None
        assert run.finished_at is None
        assert "framework-detection" in str(run)
        assert "acme" in str(run)


class ScanTargetRunTests(TestCase):
    def test_uniqueness_per_run_target(self) -> None:
        project = Project.objects.create(name="acme")
        target = ScanTarget.objects.create(
            project=project, base_url="https://dvwa.cocode.dk", host="dvwa.cocode.dk"
        )
        run = ScanRun.objects.create(project=project, stub_slug="framework-detection")
        target_run = ScanTargetRun.objects.create(scan_run=run, target=target)
        assert "dvwa.cocode.dk" in str(target_run)
        with self.assertRaises(IntegrityError):
            ScanTargetRun.objects.create(scan_run=run, target=target)


class ScanRunLifecycleStartTests(TestCase):
    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")

    def test_start_from_queued_transitions_to_running(self) -> None:
        self.run.start()
        self.run.refresh_from_db()
        assert self.run.status == RunStatus.RUNNING
        assert self.run.started_at is not None
        ev = Event.objects.get(type=EventType.SCAN_RUN_STARTED)
        assert ev.data["before_status"] == "queued"
        assert ev.data["after_status"] == "running"
        assert ev.data["id"] == str(self.run.id)

    def test_start_from_non_queued_raises(self) -> None:
        self.run.status = RunStatus.RUNNING
        self.run.save()
        with self.assertRaises(InvalidTransition):
            self.run.start()

    def test_start_atomic_rollback_when_event_log_fails(self) -> None:
        # `Event` is lazily imported inside the model's `_transition`,
        # so we patch the class attribute at its real home.
        with patch(
            "apps.events.models.Event.log", side_effect=RuntimeError("boom")
        ), self.assertRaises(RuntimeError):
            self.run.start()
        self.run.refresh_from_db()
        assert self.run.status == RunStatus.QUEUED
        assert self.run.started_at is None


class ScanRunLifecyclePauseTests(TestCase):
    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(
            project=project, stub_slug="1.1", status=RunStatus.RUNNING
        )

    def test_pause_from_running_transitions_to_paused(self) -> None:
        self.run.pause()
        self.run.refresh_from_db()
        assert self.run.status == RunStatus.PAUSED
        ev = Event.objects.get(type=EventType.SCAN_RUN_PAUSED)
        assert ev.data["before_status"] == "running"
        assert ev.data["after_status"] == "paused"

    def test_pause_from_non_running_raises(self) -> None:
        self.run.status = RunStatus.QUEUED
        self.run.save()
        with self.assertRaises(InvalidTransition):
            self.run.pause()


class ScanRunLifecycleResumeTests(TestCase):
    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(
            project=project, stub_slug="1.1", status=RunStatus.PAUSED
        )

    def test_resume_from_paused_transitions_to_running(self) -> None:
        self.run.resume()
        self.run.refresh_from_db()
        assert self.run.status == RunStatus.RUNNING
        ev = Event.objects.get(type=EventType.SCAN_RUN_RESUMED)
        assert ev.data["before_status"] == "paused"
        assert ev.data["after_status"] == "running"

    def test_resume_from_non_paused_raises(self) -> None:
        self.run.status = RunStatus.RUNNING
        self.run.save()
        with self.assertRaises(InvalidTransition):
            self.run.resume()


class ScanRunLifecycleStopTests(TestCase):
    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.run = ScanRun.objects.create(project=project, stub_slug="1.1")

    def test_stop_from_running_transitions_to_stopping(self) -> None:
        self.run.status = RunStatus.RUNNING
        self.run.save()
        self.run.stop()
        self.run.refresh_from_db()
        assert self.run.status == RunStatus.STOPPING
        ev = Event.objects.get(type=EventType.SCAN_RUN_STOPPED)
        assert ev.data["before_status"] == "running"
        assert ev.data["after_status"] == "stopping"

    def test_stop_from_paused_transitions_to_stopping(self) -> None:
        self.run.status = RunStatus.PAUSED
        self.run.save()
        self.run.stop()
        self.run.refresh_from_db()
        assert self.run.status == RunStatus.STOPPING

    def test_stop_from_queued_raises(self) -> None:
        # queued runs haven't been started yet; nothing to stop.
        with self.assertRaises(InvalidTransition):
            self.run.stop()

    def test_stop_from_terminal_raises(self) -> None:
        self.run.status = RunStatus.DONE
        self.run.save()
        with self.assertRaises(InvalidTransition):
            self.run.stop()
