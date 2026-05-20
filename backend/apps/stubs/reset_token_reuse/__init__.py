"""Stub 2.6 — reset-token-reuse.

Importing this package fires `@guarded_runner("2.6")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
