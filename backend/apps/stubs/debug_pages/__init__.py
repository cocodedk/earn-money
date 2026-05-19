"""Stub 1.10 — debug / profiler / diagnostic page exposure.

Importing this package fires `@register("1.10")` on `run()` via runner.py.
The runner import is deferred until the runner module lands so partial
TDD slices (signals, classify, fetcher) can be tested in isolation.
"""
from __future__ import annotations
