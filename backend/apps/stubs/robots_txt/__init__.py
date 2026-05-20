"""Stub 1.11 — robots.txt public-metadata extraction.

Importing this package fires `@register("1.11")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
