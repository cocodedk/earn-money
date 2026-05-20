"""Stub 2.12 — weak-recovery-codes.

Importing this package fires `@guarded_runner("2.12")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
