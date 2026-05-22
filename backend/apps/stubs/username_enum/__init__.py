"""Stub 2.1 — username enumeration (Phase 2 canary).

Importing this package fires `@guarded_runner("2.1")` on `run()`
via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
