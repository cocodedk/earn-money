"""Stubs app — read-only API surface over the cookbook tree.

No models. Parses YAML-frontmatter spec files from
`docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/` and serves
them as JSON via `GET /api/stubs/` and `GET /api/stubs/<phase.spec>/`.
"""
from __future__ import annotations

from django.apps import AppConfig


class StubsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stubs"
    label = "stubs"
