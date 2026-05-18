"""Project — top-level container for a scan engagement."""
from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedUUIDModel


class Project(TimestampedUUIDModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name
