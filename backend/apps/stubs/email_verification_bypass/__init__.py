"""Stub 2.20 — email-verification-bypass.

Importing this package fires `@guarded_runner("2.20")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
