"""Findings app — per-stub Finding records produced by scan runs."""
from __future__ import annotations

from django.apps import AppConfig


class FindingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.findings"
    label = "findings"

    def ready(self) -> None:
        # Wire the post_save signal that emits FINDING_CREATED events.
        from . import signals  # noqa: F401
