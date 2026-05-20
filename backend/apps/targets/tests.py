from django.db import IntegrityError
from django.test import TestCase

from apps.projects.models import Project
from .models import ScanTarget, TargetStatus


class ScanTargetModelTests(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")

    def test_create_target_defaults_active(self) -> None:
        target = ScanTarget.objects.create(
            project=self.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        assert target.status == TargetStatus.ACTIVE
        assert target.id is not None
        assert "dvwa.cocode.dk" in str(target)

    def test_uniqueness_per_project_base_url(self) -> None:
        ScanTarget.objects.create(
            project=self.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        with self.assertRaises(IntegrityError):
            ScanTarget.objects.create(
                project=self.project,
                base_url="https://dvwa.cocode.dk",
                host="dvwa.cocode.dk",
            )
