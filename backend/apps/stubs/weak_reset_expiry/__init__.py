"""Stub 2.7 — weak-reset-expiry.

Importing this package fires `@guarded_runner("2.7")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
