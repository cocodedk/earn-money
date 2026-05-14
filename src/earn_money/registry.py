"""Walk the registered program directory tree.

A "registered program" is any `programs/<platform>/<slug>/` directory that
contains a `scope.md` file. The dashboard aggregator, future cron jobs,
and the rate-card retro will all iterate via the same helper.
"""

from __future__ import annotations

from collections.abc import Iterator

from earn_money.config import Paths


def iter_registered_programs(paths: Paths) -> Iterator[tuple[str, str]]:
    """Yield `(platform, slug)` pairs for every registered program.

    The iteration order is `(platform, slug)` ascending so callers get a
    stable, reproducible status snapshot.
    """
    programs_root = paths.programs
    if not programs_root.is_dir():
        return
    for platform_dir in sorted(p for p in programs_root.iterdir() if p.is_dir()):
        for slug_dir in sorted(s for s in platform_dir.iterdir() if s.is_dir()):
            if (slug_dir / "scope.md").is_file():
                yield platform_dir.name, slug_dir.name
