"""Stubs app — read-only API surface over the cookbook tree + runners.

No models. Parses YAML-frontmatter spec files from
`docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/` and serves
them as JSON via `GET /api/stubs/` and `GET /api/stubs/<phase.spec>/`.

`ready()` imports each stub runner module so its `@register("N.M")`
decorator fires before the Celery scan task attempts dispatch.
"""
from __future__ import annotations

from django.apps import AppConfig


class StubsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stubs"
    label = "stubs"

    def ready(self) -> None:
        # Importing the package runs its __init__, which imports
        # `runner.py` and applies `@register("1.1")`.
        from . import framework_detection  # noqa: F401
