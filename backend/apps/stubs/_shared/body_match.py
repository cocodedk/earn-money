"""Shared body-marker matchers for stub signals.

Three Phase-1 stubs (admin_panels, old_endpoints, debug_pages — now
robots_txt too once it lands) repeated the same pattern:

    lowered = body.lower()
    if any(marker in lowered for marker in MARKERS): ...
    if all(marker in lowered for marker in MARKERS): ...

Lifted here once we hit four call sites. The helpers expect markers
to be PRE-LOWERED so callers don't need to know the implementation
choice of lowering body vs markers.

`contains_all(body, ())` returns False (not vacuously True): every
current caller passes at least one marker; vacuously-True would
make an empty signature accidentally match every body.
"""
from __future__ import annotations

from typing import Iterable


def contains_any(body: str, markers: Iterable[str]) -> bool:
    """Return True when at least one (pre-lowered) marker appears
    as a substring of `body`. Body is lowered once internally."""
    if not body:
        return False
    lowered = body.lower()
    return any(marker in lowered for marker in markers)


def contains_all(body: str, markers: Iterable[str]) -> bool:
    """Return True when EVERY (pre-lowered) marker appears as a
    substring of `body`. Body is lowered once internally.

    Empty `markers` returns False — see module docstring."""
    if not body:
        return False
    markers_list = list(markers)
    if not markers_list:
        return False
    lowered = body.lower()
    return all(marker in lowered for marker in markers_list)
