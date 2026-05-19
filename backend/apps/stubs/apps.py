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
        # Each stub package's __init__ imports its runner and fires the
        # @register("N.M") decorator at app-init time.
        from . import framework_detection  # noqa: F401  registers "1.1"
        from . import server_headers  # noqa: F401  registers "1.2"
        from . import frontend_framework  # noqa: F401  registers "1.3"
        from . import backend_hints  # noqa: F401  registers "1.4"
        from . import package_leaks  # noqa: F401  registers "1.5"
