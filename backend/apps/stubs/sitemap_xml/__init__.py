"""Stub 1.12 — sitemap.xml URL extraction.

Importing this package fires `@register("1.12")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
