"""Scan run state machine.

Status values match the spec
(docs/superpowers/specs/2026-05-18-DOCKERIZED-ENV/06-scan-control.md):
queued → running → paused → stopping → stopped / failed / done.

State-transition validation lives in lifecycle methods on `ScanRun`
(`start`, `pause`, `resume`, `stop`). Each validates the source status,
flips the state, and emits one Event in the same DB transaction — see
[[project-event-log-medium-done-well]].

Audit events for scan runs and per-step progress events live in the
unified `apps.events.Event` log.
"""
from __future__ import annotations

from typing import Any

from django.db import models, transaction
from django.utils import timezone

from apps.common.models import TimestampedUUIDModel
from apps.projects.models import Project
from apps.targets.models import ScanTarget

from .exceptions import InvalidTransition


class RunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    STOPPING = "stopping", "Stopping"
    STOPPED = "stopped", "Stopped"
    FAILED = "failed", "Failed"
    DONE = "done", "Done"


class ScanRun(TimestampedUUIDModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="scan_runs"
    )
    stub_slug = models.CharField(
        max_length=64,
        help_text="Cookbook stub identifier (phase.spec form, e.g. '1.1').",
    )
    status = models.CharField(
        max_length=16, choices=RunStatus.choices, default=RunStatus.QUEUED
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.stub_slug} on {self.project.name} [{self.status}]"

    # --- Lifecycle methods ---
    # Each transition writes one Event row atomically with the status
    # update. Caller doesn't wrap in transaction.atomic() — the method
    # owns it.

    def start(self) -> "ScanRun":
        return self._transition(
            from_=(RunStatus.QUEUED,),
            to=RunStatus.RUNNING,
            event_type="scan_run.started",
            extra={"started_at": timezone.now()},
        )

    def pause(self) -> "ScanRun":
        return self._transition(
            from_=(RunStatus.RUNNING,),
            to=RunStatus.PAUSED,
            event_type="scan_run.paused",
        )

    def resume(self) -> "ScanRun":
        return self._transition(
            from_=(RunStatus.PAUSED,),
            to=RunStatus.RUNNING,
            event_type="scan_run.resumed",
        )

    def stop(self) -> "ScanRun":
        return self._transition(
            from_=(RunStatus.RUNNING, RunStatus.PAUSED),
            to=RunStatus.STOPPING,
            event_type="scan_run.stopped",
        )

    def _transition(
        self,
        *,
        from_: tuple[str, ...],
        to: str,
        event_type: str,
        extra: dict[str, Any] | None = None,
    ) -> "ScanRun":
        extra = extra or {}
        if self.status not in from_:
            raise InvalidTransition(
                f"Invalid transition: scan_run is {self.status!r}, "
                f"expected one of {sorted(from_)} to move to {to!r}."
            )
        # Late import — apps.events.models imports ScanRun from here.
        from apps.events.models import Event

        before = self.status
        with transaction.atomic():
            self.status = to
            for field, value in extra.items():
                setattr(self, field, value)
            self.save(update_fields=["status", "updated_at", *extra.keys()])
            Event.log(
                type=event_type,
                subject=self,
                scan_run=self,
                data={
                    "id": str(self.id),
                    "before_status": before,
                    "after_status": to,
                    **extra,
                },
            )
        return self


class ScanTargetRun(TimestampedUUIDModel):
    scan_run = models.ForeignKey(
        ScanRun, on_delete=models.CASCADE, related_name="target_runs"
    )
    target = models.ForeignKey(
        ScanTarget, on_delete=models.CASCADE, related_name="target_runs"
    )
    status = models.CharField(
        max_length=16, choices=RunStatus.choices, default=RunStatus.QUEUED
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("scan_run", "target"),
                name="uniq_target_per_scan_run",
            )
        ]

    def __str__(self) -> str:
        return f"{self.target.host} in {self.scan_run_id} [{self.status}]"
