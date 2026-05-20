"""Stub 2.4 — weak-rate-limiting.

Importing this package fires `@guarded_runner("2.4")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
