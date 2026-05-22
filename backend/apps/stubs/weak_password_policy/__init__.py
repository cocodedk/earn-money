"""Stub 2.2 — weak-password-policy.

Importing this package fires `@guarded_runner("2.2")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
