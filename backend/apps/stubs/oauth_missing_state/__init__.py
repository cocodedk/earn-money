"""Stub 2.15 — oauth-missing-state.

Importing this package fires `@guarded_runner("2.15")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
