"""Stub 1.15 — public JavaScript bundles.

Importing this package fires `@register("1.15")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
