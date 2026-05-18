"""Evidence — append-only observations from scan runs.

Aligned with the cookbook's logical Evidence type in
docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md.
Extra platform fields (scan_run, target, method, data, finding linkage)
sit on top of the logical shape.

Source values match the cookbook's fixed vocabulary so detection runners
write the same source tags the schema expects.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import UUIDModel
from apps.scans.models import ScanRun
from apps.targets.models import ScanTarget


class EvidenceSource(models.TextChoices):
    HEADER = "header", "Header"
    COOKIE = "cookie", "Cookie"
    HTML = "html", "HTML"
    SCRIPT = "script", "Script"
    CSS = "css", "CSS"
    FAVICON = "favicon", "Favicon"
    PATH = "path", "Path"
    META = "meta", "Meta"
    DNS = "dns", "DNS"


class Evidence(UUIDModel):
    scan_run = models.ForeignKey(
        ScanRun, on_delete=models.CASCADE, related_name="evidence"
    )
    target = models.ForeignKey(
        ScanTarget, on_delete=models.CASCADE, related_name="evidence"
    )
    finding = models.ForeignKey(
        "findings.Finding",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evidence",
    )
    source = models.CharField(max_length=16, choices=EvidenceSource.choices)
    url = models.URLField(max_length=2048)
    method = models.CharField(max_length=10, default="GET")
    field = models.CharField(max_length=128, blank=True, default="")
    matched_value = models.TextField(blank=True, default="")
    raw_excerpt = models.TextField(blank=True, default="")
    content_hash = models.CharField(max_length=80, blank=True, default="")
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("scan_run", "created_at")),
            models.Index(fields=("target", "source")),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and Evidence.objects.filter(pk=self.pk).exists():
            raise RuntimeError(
                "Evidence is append-only — existing rows cannot be updated."
            )
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "Evidence is append-only — existing rows cannot be deleted."
        )

    def __str__(self) -> str:
        return f"{self.source}:{self.field}={self.matched_value[:40]}"
