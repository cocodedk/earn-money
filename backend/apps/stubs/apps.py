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
        from . import hidden_routes  # noqa: F401  registers "1.6"
        from . import backup_files  # noqa: F401  registers "1.7"
        from . import admin_panels  # noqa: F401  registers "1.8"
        from . import old_endpoints  # noqa: F401  registers "1.9"
        from . import debug_pages  # noqa: F401  registers "1.10"
        from . import robots_txt  # noqa: F401  registers "1.11"
        from . import sitemap_xml  # noqa: F401  registers "1.12"
        from . import security_txt  # noqa: F401  registers "1.13"
        from . import source_maps  # noqa: F401  registers "1.14"
        from . import public_javascript_bundles  # noqa: F401  registers "1.15"
        from . import stack_traces  # noqa: F401  registers "1.16"
        from . import verbose_api_errors  # noqa: F401  registers "1.17"
        from . import sql_orm_errors  # noqa: F401  registers "1.19"
        from . import well_known_paths  # noqa: F401  registers "1.20" (absorbs 1.21-1.25)
        # Phase 2 — authentication.
        from . import username_enum  # noqa: F401  registers "2.1"
