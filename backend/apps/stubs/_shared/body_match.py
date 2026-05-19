"""Shared body-marker matchers for stub signals.

Three Phase-1 stubs (admin_panels, old_endpoints, debug_pages)
repeated the same pattern:

    lowered = body.lower()
    if any(marker in lowered for marker in MARKERS): ...
    if all(marker in lowered for marker in MARKERS): ...

Lifted here. Markers are expected PRE-LOWERED so callers don't
need to know the implementation choice of lowering body vs markers.

`_lowered` variants take an already-lowered body for hot loops
(e.g. debug_pages iterates ~11 framework signatures per probe;
re-lowering a capped 256KB body inside the loop is wasteful).
Callers compute `lowered = body.lower()` once outside the loop.

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
    return contains_any_lowered(body.lower(), markers)


def contains_any_lowered(lowered: str, markers: Iterable[str]) -> bool:
    """Same as `contains_any` but takes an already-lowercased body.
    Use in hot loops where the caller has computed the lowered body
    once and reuses it across many marker checks."""
    if not lowered:
        return False
    return any(marker in lowered for marker in markers)


def contains_all(body: str, markers: Iterable[str]) -> bool:
    """Return True when EVERY (pre-lowered) marker appears as a
    substring of `body`. Body is lowered once internally.

    Empty `markers` returns False — see module docstring."""
    if not body:
        return False
    return contains_all_lowered(body.lower(), markers)


def contains_all_lowered(
    lowered: str, markers: Iterable[str],
) -> bool:
    """Same as `contains_all` but takes an already-lowercased body."""
    if not lowered:
        return False
    markers_list = list(markers)
    if not markers_list:
        return False
    return all(marker in lowered for marker in markers_list)
