"""Abstract base models reused across apps.

UUID primary keys keep model IDs aligned with the cookbook's logical
contract in 00-shared-schema.md ("id: uuid"). Auto timestamps cover
created_at / updated_at on every concrete model that inherits them.
"""
from __future__ import annotations

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Adds a UUID primary key. Use for append-only tables that never
    need an updated_at field (e.g. Evidence, ScanEvent)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class TimestampedUUIDModel(UUIDModel):
    """UUID + created_at + updated_at. The default for most models."""

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
