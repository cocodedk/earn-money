"""Stub 1.9 — old / deprecated endpoint discovery.

Importing this package fires `@register("1.9")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
