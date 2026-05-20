"""Stub 1.16 — public stack-trace exposure detection.

Importing this package fires `@register("1.16")` on `run()` via
runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
