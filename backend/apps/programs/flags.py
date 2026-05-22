"""Operational safety flags: kill-switch and per-program freeze.

Adapted from `archive/v1/src/earn_money/flags.py`. v2 reads the flag-
file path from Django settings so containers can mount
`/flags/RECON_ENABLED` while local-dev can override via the
`RECON_ENABLED_PATH` env var.

Both checks are deliberately strict — a *directory* at the flag path
counts as "absent". Docker silently creates a directory when a
single-file bind mount points at a missing host file, so a directory
must never be treated as "enabled" / "frozen".
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.programs.exceptions import ReconDisabled


def require_recon_enabled(path: Path | None = None) -> None:
    """Raise ``ReconDisabled`` unless the kill-switch flag is a regular
    file. Default path comes from ``settings.RECON_ENABLED_PATH``."""
    flag = Path(path) if path is not None else Path(settings.RECON_ENABLED_PATH)
    if not flag.is_file():
        raise ReconDisabled(
            f"RECON_ENABLED flag absent at {flag}. "
            "Create the file to enable recon; remove it to halt."
        )


def is_program_frozen(platform: str, slug: str) -> bool:
    """Return True iff ``<PROGRAMS_ROOT>/<platform>/<slug>/FROZEN`` is a
    regular file. A directory at that path does not count as frozen."""
    flag = Path(settings.PROGRAMS_ROOT) / platform / slug / "FROZEN"
    return flag.is_file()
