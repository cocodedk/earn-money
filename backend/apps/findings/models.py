"""Finding — concrete result a stub produced for a target.

Status vocabulary matches the cookbook's shared schema
(docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md).
Stub-specific detail goes into `data` as JSON.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedUUIDModel
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget


class FindingStatus(models.TextChoices):
    CANDIDATE = "candidate", "Candidate"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"
    STALE = "stale", "Stale"


class Finding(TimestampedUUIDModel):
    scan_run = models.ForeignKey(
        ScanRun, on_delete=models.CASCADE, related_name="findings"
    )
    target = models.ForeignKey(
        ScanTarget, on_delete=models.CASCADE, related_name="findings"
    )
    stub_slug = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=64)
    severity = models.CharField(max_length=16, blank=True, default="")
    confidence = models.CharField(max_length=16, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=FindingStatus.choices, default=FindingStatus.CANDIDATE
    )
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("scan_run", "status")),
            models.Index(fields=("stub_slug",)),
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.status}]"
