"""ScanTarget — a (host, base_url) pair the scanner is pointed at.

Maps to the cookbook's shared `ScanTarget` type in
docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md,
with the addition of a `project` foreign key for platform plumbing.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedUUIDModel
from apps.projects.models import Project


class TargetStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retired"


class ScanTarget(TimestampedUUIDModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="targets"
    )
    base_url = models.URLField(max_length=1024)
    host = models.CharField(max_length=253)
    ip = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=TargetStatus.choices, default=TargetStatus.ACTIVE
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("project", "base_url"),
                name="uniq_target_per_project_base_url",
            )
        ]

    def __str__(self) -> str:
        return f"{self.host} ({self.base_url})"
