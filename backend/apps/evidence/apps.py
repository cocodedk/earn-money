"""Evidence app — append-only observations a runner collected."""
from __future__ import annotations

from django.apps import AppConfig


class EvidenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.evidence"
    label = "evidence"
