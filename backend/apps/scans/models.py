"""Scan run state machine.

Status values match the spec
(docs/superpowers/specs/2026-05-18-DOCKERIZED-ENV/06-scan-control.md):
queued → running → paused → stopping → stopped / failed / done.

State transition VALIDATION (i.e. "you can't go done → running") lives
in lifecycle methods that land alongside the API actions — the model
just stores the current value. Choices enforce a closed set.

Audit events for scan runs (started, paused, …) and per-step progress
events live in the unified `apps.events.Event` log — see
[[project-event-log-medium-done-well]].
"""
from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedUUIDModel
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
