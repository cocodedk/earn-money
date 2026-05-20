"""Tests for the FINDING_CREATED post_save signal."""
from __future__ import annotations

from django.test import TestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run


class FindingCreatedSignalTests(TestCase):
    def test_saving_a_finding_emits_finding_created_event(self) -> None:
        scan_run, target_run = seed_target_run(stub_slug="1.11", host="x.example")
        before = Event.objects.filter(type=EventType.FINDING_CREATED).count()
        finding = Finding.objects.create(
            scan_run=scan_run, target=target_run.target,
            stub_slug="1.11", category="robots_txt",
            title="Robots.txt present", data={},
        )
        after = Event.objects.filter(type=EventType.FINDING_CREATED).count()
        assert after == before + 1
        ev = Event.objects.filter(
            type=EventType.FINDING_CREATED, subject_id=finding.id,
        ).get()
        assert ev.scan_run_id == scan_run.id
        assert ev.target_id == target_run.target_id
        assert ev.data["stub_slug"] == "1.11"
        assert ev.data["category"] == "robots_txt"

    def test_updating_a_finding_does_not_re_emit(self) -> None:
        scan_run, target_run = seed_target_run(stub_slug="1.11", host="x.example")
        finding = Finding.objects.create(
            scan_run=scan_run, target=target_run.target,
            stub_slug="1.11", category="robots_txt",
            title="t", data={},
        )
        before = Event.objects.filter(
            type=EventType.FINDING_CREATED, subject_id=finding.id,
        ).count()
        finding.status = "confirmed"
        finding.save()
        after = Event.objects.filter(
            type=EventType.FINDING_CREATED, subject_id=finding.id,
        ).count()
        assert after == before  # no duplicate emit
