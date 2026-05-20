"""Unified Event log.

Single audit + SSE-streaming primitive. Every state-changing action in
the platform emits exactly one Event row in the same DB transaction as
the change. See [[project-event-log-medium-done-well]] for the contract.

The `data` JSON payload is intentionally self-describing — a future
event-replay projector should be able to reconstruct what happened from
the Event row alone, without joining other tables. Audit checklist when
emitting: if everything else were deleted, could a fresh projector
rebuild the action from this one row? If no, the payload is too lean.
"""
from __future__ import annotations

import uuid
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.common.models import UUIDModel
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget

from .types import EventType


class EventLevel(models.TextChoices):
    DEBUG = "debug", "Debug"
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"


class Event(UUIDModel):
    type = models.CharField(max_length=64, choices=EventType.choices)
    scan_run = models.ForeignKey(
        ScanRun, null=True, blank=True, on_delete=models.CASCADE,
        related_name="events",
    )
    target = models.ForeignKey(
        ScanTarget, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="events",
    )
    subject_type = models.CharField(max_length=32, blank=True, default="")
    subject_id = models.UUIDField(null=True, blank=True)
    level = models.CharField(
        max_length=8, choices=EventLevel.choices, default=EventLevel.INFO,
    )
    message = models.TextField(blank=True, default="")
    # DjangoJSONEncoder so datetime / Decimal / UUID values in event
    # payloads serialize as ISO-8601 / float / string (default json
    # module can't handle them).
    data = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("scan_run", "created_at")),
            models.Index(fields=("type", "created_at")),
            models.Index(fields=("subject_type", "subject_id")),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk and Event.objects.filter(pk=self.pk).exists():
            raise RuntimeError(
                "Event is append-only — existing rows cannot be updated."
            )
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "Event is append-only — existing rows cannot be deleted."
        )

    def __str__(self) -> str:
        return f"{self.type} [{self.level}] {self.message[:60]}"

    @classmethod
    def log(
        cls,
        type: str,
        *,
        scan_run: ScanRun | None = None,
        target: ScanTarget | None = None,
        subject: Any = None,
        subject_type: str = "",
        subject_id: uuid.UUID | None = None,
        level: str = EventLevel.INFO,
        message: str = "",
        data: dict[str, Any] | None = None,
    ) -> "Event":
        """The single write path for events. Direct ORM `.objects.create()`
        outside this method is forbidden by convention.

        If `subject` is a Django model instance, it's decomposed into
        (subject_type, subject_id) automatically. Otherwise pass
        `subject_type` + `subject_id` explicitly.

        Does NOT open a transaction itself — the caller wraps both the
        state change AND this log() call in `transaction.atomic()` so
        they land together.

        `data` should be self-describing: enough JSON to reconstruct the
        action without FK lookups against other tables.
        """
        if subject is not None:
            subject_type = subject._meta.model_name
            subject_id = subject.pk
        return cls.objects.create(
            type=type,
            scan_run=scan_run,
            target=target,
            subject_type=subject_type,
            subject_id=subject_id,
            level=level,
            message=message,
            data=data or {},
        )
