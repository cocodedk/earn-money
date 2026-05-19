"""Stub 1.13 — security.txt public-metadata extraction.

Importing this package fires `@register("1.13")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
