"""Stub 1.17 — verbose API error detection.

Importing this package fires `@register("1.17")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
