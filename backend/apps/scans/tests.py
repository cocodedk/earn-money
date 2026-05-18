from django.db import IntegrityError
from django.test import TestCase

from apps.projects.models import Project
from apps.targets.models import ScanTarget
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
