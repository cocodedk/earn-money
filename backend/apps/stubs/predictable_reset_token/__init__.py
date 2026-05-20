"""Stub 2.5 — predictable-reset-token.

Importing this package fires `@guarded_runner("2.5")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
