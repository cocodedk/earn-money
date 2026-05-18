"""Behaviour tests for Finding — written BEFORE the model per the
strict-TDD rule in CLAUDE.md §Engineering principles → TDD."""
from __future__ import annotations

from django.test import TestCase

from apps.projects.models import Project
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget


class FindingCreationTests(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")
        self.target = ScanTarget.objects.create(
            project=self.project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        self.run = ScanRun.objects.create(
            project=self.project, stub_slug="framework-detection"
        )

    def test_creates_with_required_fields(self) -> None:
        from .models import Finding, FindingStatus

        finding = Finding.objects.create(
            scan_run=self.run,
            target=self.target,
            stub_slug="framework-detection",
            title="PHP detected on dvwa.cocode.dk",
            category="runtime",
        )
        assert finding.id is not None
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.confidence == ""  # optional until set
        assert finding.severity == ""
        assert finding.data == {}
        assert finding.created_at is not None
        assert finding.updated_at is not None

    def test_str_includes_title(self) -> None:
        from .models import Finding

        finding = Finding.objects.create(
            scan_run=self.run,
            target=self.target,
            stub_slug="framework-detection",
            title="PHP detected",
            category="runtime",
        )
        assert "PHP detected" in str(finding)

    def test_can_be_updated(self) -> None:
        """Finding (unlike Evidence) is mutable — operator triage moves
        it through candidate → confirmed/rejected/stale."""
        from .models import Finding, FindingStatus

        finding = Finding.objects.create(
            scan_run=self.run,
            target=self.target,
            stub_slug="framework-detection",
            title="PHP detected",
            category="runtime",
        )
        finding.status = FindingStatus.CONFIRMED
        finding.save()
        finding.refresh_from_db()
        assert finding.status == FindingStatus.CONFIRMED


class FindingStatusTests(TestCase):
    def test_status_enum_values_match_cookbook_schema(self) -> None:
        """The cookbook's 00-shared-schema.md fixes these four values."""
        from .models import FindingStatus

        assert FindingStatus.CANDIDATE == "candidate"
        assert FindingStatus.CONFIRMED == "confirmed"
        assert FindingStatus.REJECTED == "rejected"
        assert FindingStatus.STALE == "stale"
