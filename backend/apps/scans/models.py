"""Scan run state machine + event stream.

Status values match the spec
(docs/superpowers/specs/2026-05-18-DOCKERIZED-ENV/06-scan-control.md):
queued → running → paused → stopping → stopped / failed / done.

State transition VALIDATION (i.e. "you can't go done → running") lives
in the API layer when it lands — the model just stores the current
value. Choices enforce a closed set; transitions are not enforced here.

ScanEvent is append-only by design (no updated_at). Use UUIDModel.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedUUIDModel, UUIDModel
from apps.projects.models import Project
from apps.targets.models import ScanTarget


class RunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    STOPPING = "stopping", "Stopping"
    STOPPED = "stopped", "Stopped"
    FAILED = "failed", "Failed"
    DONE = "done", "Done"


class EventLevel(models.TextChoices):
    DEBUG = "debug", "Debug"
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"


class ScanRun(TimestampedUUIDModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="scan_runs"
    )
    stub_slug = models.CharField(
        max_length=64,
        help_text="Slug of the cookbook spec being run (e.g. 'framework-detection').",
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


class ScanEvent(UUIDModel):
    """Append-only event from a scan run.

    Streamed to the frontend via SSE. No updated_at — corrections happen
    by inserting a new row, never editing existing ones.
    """

    scan_run = models.ForeignKey(
        ScanRun, on_delete=models.CASCADE, related_name="events"
    )
    target = models.ForeignKey(
        ScanTarget,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    level = models.CharField(
        max_length=8, choices=EventLevel.choices, default=EventLevel.INFO
    )
    event_type = models.CharField(max_length=64)
    message = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at",)  # chronological for SSE
        indexes = [
            models.Index(fields=("scan_run", "created_at")),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and ScanEvent.objects.filter(pk=self.pk).exists():
            raise RuntimeError(
                "ScanEvent is append-only — existing rows cannot be updated."
            )
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "ScanEvent is append-only — existing rows cannot be deleted."
        )

    def __str__(self) -> str:
        return f"[{self.level}] {self.event_type}: {self.message[:60]}"
