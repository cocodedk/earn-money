"""Stub 2.19 — duplicate-account-confusion.

Importing this package fires `@guarded_runner("2.19")` on `run()`.
"""
from __future__ import annotations

from .runner import run  # noqa: F401

__all__ = ("run",)
