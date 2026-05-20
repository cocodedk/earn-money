"""Tests for the unified Event log.

Written BEFORE the model per the strict-TDD rule in CLAUDE.md.
Encodes the medium-done-well contract: single write path via
Event.log(), self-describing payload, append-only, typed event keys.
"""
from __future__ import annotations

import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.projects.models import Project
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget


class EventLogTests(TestCase):
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

    def test_log_creates_event_row(self) -> None:
        from .models import Event
        from .types import EventType

        ev = Event.log(
            type=EventType.SYSTEM_TEST,
            data={"k": "v"},
        )
        assert ev.id is not None
        assert ev.type == EventType.SYSTEM_TEST
        assert ev.data == {"k": "v"}
        assert ev.created_at is not None

    def test_log_accepts_scan_run_and_target(self) -> None:
        from .models import Event
        from .types import EventType

        ev = Event.log(
            type=EventType.SYSTEM_TEST,
            scan_run=self.run,
            target=self.target,
            level="warning",
            message="hi",
            data={"phase": 1},
        )
        assert ev.scan_run_id == self.run.id
        assert ev.target_id == self.target.id
        assert ev.level == "warning"
        assert ev.message == "hi"

    def test_log_accepts_subject_type_and_id(self) -> None:
        from .models import Event
        from .types import EventType

        ev = Event.log(
            type=EventType.SYSTEM_TEST,
            subject_type="project",
            subject_id=self.project.id,
            data={"name": "acme"},
        )
        assert ev.subject_type == "project"
        assert ev.subject_id == self.project.id

    def test_log_accepts_subject_instance_decomposes(self) -> None:
        """Passing a Django model instance as `subject=` should decompose
        into (subject_type, subject_id) automatically."""
        from .models import Event
        from .types import EventType

        ev = Event.log(
            type=EventType.SYSTEM_TEST,
            subject=self.project,
            data={"name": "acme"},
        )
        assert ev.subject_type == "project"
        assert ev.subject_id == self.project.id

    def test_log_defaults(self) -> None:
        from .models import Event
        from .types import EventType

        ev = Event.log(type=EventType.SYSTEM_TEST)
        assert ev.level == "info"
        assert ev.message == ""
        assert ev.data == {}
        assert ev.scan_run is None
        assert ev.target is None
        assert ev.subject_type == ""
        assert ev.subject_id is None


class EventAppendOnlyTests(TestCase):
    def setUp(self) -> None:
        from .models import Event
        from .types import EventType

        self.ev = Event.log(type=EventType.SYSTEM_TEST, data={"x": 1})

    def test_cannot_update_existing_row(self) -> None:
        self.ev.message = "tampered"
        with self.assertRaises(RuntimeError):
            self.ev.save()

    def test_cannot_delete_existing_row(self) -> None:
        with self.assertRaises(RuntimeError):
            self.ev.delete()


class EventTypeConstraintTests(TestCase):
    def test_type_must_be_in_enum(self) -> None:
        """`type` must be one of EventType.values; raw strings are
        refused at the model layer via choices=."""
        from .models import Event
        from django.core.exceptions import ValidationError

        ev = Event(type="bogus.action", level="info")
        with self.assertRaises(ValidationError):
            ev.full_clean()

    def test_str_includes_type(self) -> None:
        from .models import Event
        from .types import EventType

        ev = Event.log(type=EventType.SYSTEM_TEST, message="hello")
        assert "system.test" in str(ev)


class EventLogTransactionTests(TestCase):
    """The medium-done-well rule: state change + event are atomic.

    Event.log() does not OPEN a transaction itself — that's the caller's
    responsibility. But if the caller's transaction rolls back, the
    Event row must roll back with it.
    """

    def test_event_rolls_back_with_outer_transaction(self) -> None:
        from .models import Event
        from .types import EventType

        outer_caught = False
        try:
            with transaction.atomic():
                Event.log(type=EventType.SYSTEM_TEST, data={"rolled": True})
                # Force a rollback by raising — Event.log was already
                # called inside the atomic block.
                raise IntegrityError("forced rollback for the test")
        except IntegrityError:
            outer_caught = True

        assert outer_caught
        # No event should have been persisted.
        assert (
            Event.objects.filter(data__rolled=True).count() == 0
        )
