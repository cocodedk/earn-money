"""Framework-detection runner (cookbook stub 1.1).

Importing this package registers `run()` against stub slug "1.1" via
`apps.stubs.runners.register`. The Stubs app's `ready()` hook is where
future stub runner packages will be imported to fire registrations.
"""
from __future__ import annotations

from .runner import run

__all__ = ("run",)
