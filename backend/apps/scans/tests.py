from django.test import TestCase

from apps.projects.models import Project
from apps.targets.models import ScanTarget
from .models import EventLevel, RunStatus, ScanEvent, ScanRun, ScanTargetRun


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


class ScanEventAppendOnlyTests(TestCase):
    def setUp(self) -> None:
        project = Project.objects.create(name="acme")
        self.target = ScanTarget.objects.create(
            project=project, base_url="https://dvwa.cocode.dk", host="dvwa.cocode.dk"
        )
        self.run = ScanRun.objects.create(project=project, stub_slug="framework-detection")

    def test_create_event(self) -> None:
        event = ScanEvent.objects.create(
            scan_run=self.run,
            event_type="scan_started",
            message="run kicked off",
        )
        assert event.level == EventLevel.INFO
        assert event.id is not None
        assert "scan_started" in str(event)
        assert "run kicked off" in str(event)

    def test_cannot_update_event(self) -> None:
        event = ScanEvent.objects.create(
            scan_run=self.run, event_type="ping", message="initial"
        )
        event.message = "tampered"
        with self.assertRaises(RuntimeError):
            event.save()

    def test_cannot_delete_event(self) -> None:
        event = ScanEvent.objects.create(
            scan_run=self.run, event_type="ping", message="initial"
        )
        with self.assertRaises(RuntimeError):
            event.delete()


class ScanTargetRunTests(TestCase):
    def test_uniqueness_per_run_target(self) -> None:
        project = Project.objects.create(name="acme")
        target = ScanTarget.objects.create(
            project=project, base_url="https://dvwa.cocode.dk", host="dvwa.cocode.dk"
        )
        run = ScanRun.objects.create(project=project, stub_slug="framework-detection")
        target_run = ScanTargetRun.objects.create(scan_run=run, target=target)
        assert "dvwa.cocode.dk" in str(target_run)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ScanTargetRun.objects.create(scan_run=run, target=target)
