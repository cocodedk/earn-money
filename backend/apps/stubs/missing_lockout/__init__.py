"""Stub 2.3 — missing-lockout.

Importing this package fires `@guarded_runner("2.3")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
