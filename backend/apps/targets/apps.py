"""Targets app — `ScanTarget` rows the scanner can be pointed at."""
from __future__ import annotations

from django.apps import AppConfig


class TargetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.targets"
    label = "targets"
