"""Stub 1.7 — backup-files discovery.

Importing this package fires `@register("1.7")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
