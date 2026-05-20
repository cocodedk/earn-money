"""Stub 1.19 — SQL/ORM error disclosure detector.

Body-signature classifier on HTTP response bodies. Detects exposed
database driver / ORM exception text that reveals backend internals
(table/column names, SQL fragments, stack frames).

Importing this package fires `@register("1.19")` on `run()` via runner.py.
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
