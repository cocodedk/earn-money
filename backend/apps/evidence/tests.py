"""Behaviour tests for Evidence — written BEFORE the model.

The single most important rule for this table is append-only: once a
row is committed, it cannot be updated or deleted. The cookbook's
00-shared-schema.md and §10 coding-agent rules both spell this out.
"""
from __future__ import annotations

from django.test import TestCase

from apps.projects.models import Project
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget


class EvidenceCreationTests(TestCase):
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
        from .models import Evidence

        ev = Evidence.objects.create(
            scan_run=self.run,
            target=self.target,
            source="cookie",
            url="https://dvwa.cocode.dk/",
            method="GET",
            field="Set-Cookie",
            matched_value="PHPSESSID",
            raw_excerpt="PHPSESSID=abc123; path=/",
            content_hash="sha256:abc",
        )
        assert ev.id is not None
        assert ev.created_at is not None
        # No updated_at on Evidence — it's UUIDModel, not TimestampedUUIDModel.
        assert not hasattr(ev, "updated_at")
        assert "cookie" in str(ev)
        assert "PHPSESSID" in str(ev)

    def test_finding_is_optional(self) -> None:
        """Evidence may be collected before any Finding is created."""
        from .models import Evidence

        ev = Evidence.objects.create(
            scan_run=self.run,
            target=self.target,
            source="header",
            url="https://dvwa.cocode.dk/",
            method="GET",
            field="X-Powered-By",
            matched_value="PHP/8.2.0",
            raw_excerpt="X-Powered-By: PHP/8.2.0",
            content_hash="sha256:def",
        )
        assert ev.finding is None


class EvidenceAppendOnlyTests(TestCase):
    """Append-only enforcement — explicit per cookbook coding-agent rules."""

    def setUp(self) -> None:
        from .models import Evidence

        project = Project.objects.create(name="acme")
        target = ScanTarget.objects.create(
            project=project,
            base_url="https://dvwa.cocode.dk",
            host="dvwa.cocode.dk",
        )
        run = ScanRun.objects.create(project=project, stub_slug="framework-detection")
        self.ev = Evidence.objects.create(
            scan_run=run,
            target=target,
            source="cookie",
            url="https://dvwa.cocode.dk/",
            method="GET",
            field="Set-Cookie",
            matched_value="PHPSESSID",
            raw_excerpt="PHPSESSID=abc; path=/",
            content_hash="sha256:abc",
        )

    def test_cannot_update_existing_row(self) -> None:
        self.ev.matched_value = "tampered"
        with self.assertRaises(RuntimeError):
            self.ev.save()

    def test_cannot_delete_existing_row(self) -> None:
        with self.assertRaises(RuntimeError):
            self.ev.delete()


class EvidenceSourceVocabularyTests(TestCase):
    def test_source_values_match_cookbook_schema(self) -> None:
        from .models import EvidenceSource

        # The cookbook's 00-shared-schema.md fixes this vocabulary.
        expected = {
            "header", "cookie", "html", "script",
            "css", "favicon", "path", "meta", "dns",
        }
        assert {choice.value for choice in EvidenceSource} == expected
