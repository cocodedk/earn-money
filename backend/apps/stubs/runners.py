"""Stub runner registry.

Each cookbook stub gets a runner: a callable that takes
`(scan_run, target_run)` and does the stub's work — fetches HTTP,
runs signatures, writes Evidence + Finding rows, lets the worker emit
the surrounding start/done events.

Registration is a decorator-driven pattern. Runner modules call
`@register("1.1")` at import time; the Stubs app's `ready()` hook is
where future runner modules will be imported so registration fires.

The dispatcher (`apps.scans.tasks._do_work`) calls `get(stub_slug)`.
If the slug isn't registered, the simulator's sleep fallback runs —
useful for stubs that haven't been implemented yet.
"""
from __future__ import annotations

import functools
from typing import Callable, Protocol

from apps.programs.exceptions import OutOfScope
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.http import resolve_and_guard


class StubRunner(Protocol):
    """Every stub runner has the same signature."""

    def __call__(
        self, scan_run: ScanRun, target_run: ScanTargetRun
    ) -> None: ...  # pragma: no cover — Protocol body, never executed


_REGISTRY: dict[str, StubRunner] = {}


def register(stub_slug: str) -> Callable[[StubRunner], StubRunner]:
    """Decorator: `@register("1.1")` makes the function the runner for
    cookbook stub 1.1. Re-registering the same slug overrides the
    previous entry — useful for tests."""

    def decorator(fn: StubRunner) -> StubRunner:
        _REGISTRY[stub_slug] = fn
        return fn

    return decorator


def guarded_runner(
    stub_slug: str,
) -> Callable[[StubRunner], StubRunner]:
    """Decorator: register a runner AND wrap it with the standard
    pre-flight scope/RECON_ENABLED/FROZEN/rate-limit guard.

    The decorated function receives a target whose base_url is already
    in-scope (or never executes, because the guard raises ``OutOfScope``
    and the wrapper swallows it). Use this for the 18 single-pass
    runners. Stubs that iterate candidate URLs (well_known_paths) must
    stay on the lower-level ``guard()`` call inside the iteration loop
    instead.
    """

    def decorator(fn: StubRunner) -> StubRunner:
        @functools.wraps(fn)
        def wrapper(
            scan_run: ScanRun, target_run: ScanTargetRun
        ) -> None:
            try:
                resolve_and_guard(
                    scan_run, target_run.target, stub_id=stub_slug,
                )
            except OutOfScope:
                return  # event already emitted; halt this stub
            fn(scan_run, target_run)

        return register(stub_slug)(wrapper)

    return decorator


def get(stub_slug: str) -> StubRunner | None:
    return _REGISTRY.get(stub_slug)


def registered_slugs() -> list[str]:
    return sorted(_REGISTRY.keys())


def _clear_for_testing() -> None:
    """Reset the registry. Test fixtures only — production code never
    calls this."""
    _REGISTRY.clear()
