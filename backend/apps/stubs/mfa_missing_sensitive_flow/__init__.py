"""Stub 2.11 — mfa-missing-sensitive-flow.

Importing this package fires `@guarded_runner("2.11")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
