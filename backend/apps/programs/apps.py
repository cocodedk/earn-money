"""Programs app — runtime registry over `programs/<platform>/<slug>/`.

Holds the scope-enforcement primitives (Scope / RoE / Program loader /
flags / rate limit). All file-backed; no DB models in this app.
"""
from __future__ import annotations

from django.apps import AppConfig


class ProgramsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.programs"
    label = "programs"
