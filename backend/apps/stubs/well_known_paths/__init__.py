"""Stub `well_known_paths` — six-family well-known-path probe.

Absorbs cookbook specs 1.20–1.25 (env / git / config_files / logs /
backup_archives / db_dumps) into a single stub with shared safety
controls (soft-404, HEAD-first probing, Range-bounded GETs, byte
caps, per-family redaction).

Importing this package fires `@register("1.20")` on `run()` via
runner.py. Specs 1.21–1.25 are closed via frontmatter + closure-note
in slice WKP-D, NOT via additional `@register` calls — single-owner
pattern mirrors `debug_pages` registering once for 1.10 (covering
1.18's families too).
"""
from __future__ import annotations

from .runner import run  # noqa: F401  (registration side effect)

__all__ = ("run",)
