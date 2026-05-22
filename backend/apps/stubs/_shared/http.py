"""Shared safety guard for stub fetcher call sites.

`guard(program, target, url, *, scan_run=None, stub_id=None)` is the
single function every stub runner calls before any HTTP. It runs four
checks, in order:

1. `require_recon_enabled()` — global kill-switch.
2. `is_program_frozen(platform, slug)` — per-program freeze.
3. `enforce_scope(target, url, program, ...)` — host must be in scope.
4. `acquire_for(program)` — block on the program's rate-limit budget.

The order matters: kill-switch first (no work at all), program freeze
next (no work for this program), scope third (refuse the URL with an
audit event), rate-limit last (only delay if we're actually going to
fire).

Why a single function instead of four inline calls per runner?
The canonical sequence is identical at every call site; centralising
it makes it easy to add a fifth check later (e.g. global rate floor)
without touching 19 runners, and the regression test in
`apps/stubs/tests/test_runner_guard_wiring.py` can grep for one symbol.
"""
from __future__ import annotations

from typing import Any

from apps.programs.exceptions import ProgramFrozen
from apps.programs.flags import is_program_frozen, require_recon_enabled
from apps.programs.loader import Program, get_registry
from apps.programs.preflight import host_from_url
from apps.programs.rate_limit import acquire_for

from .scope_check import enforce_scope


def guard(
    program: Program,
    target: Any,
    url: str,
    *,
    scan_run: Any = None,
    stub_id: str | None = None,
) -> None:
    """Run the four pre-HTTP safety checks.

    Raises:
        ReconDisabled: if the master kill-switch flag file is absent.
        ProgramFrozen: if the per-program FROZEN flag exists.
        OutOfScope: if ``url``'s host is not in ``program.scope``.

    On success, blocks until the program's rate-limit budget grants
    one token; then returns.
    """
    require_recon_enabled()
    if is_program_frozen(program.platform, program.slug):
        raise ProgramFrozen(
            f"program {program.platform}/{program.slug} is FROZEN"
        )
    enforce_scope(target, url, program, scan_run=scan_run, stub_id=stub_id)
    acquire_for(program)


def resolve_and_guard(
    scan_run: Any, target: Any, *, stub_id: str,
) -> Program:
    """Resolve the target's Program (via host_from_url + find_for_host)
    and run :func:`guard` against the target's base_url.

    Returns the resolved Program so multi-URL runners can re-guard
    against each derived candidate URL.

    Raises:
        ReconDisabled / ProgramFrozen / OutOfScope: per :func:`guard`.
    """
    program = get_registry().find_for_host(host_from_url(target.base_url))
    guard(program, target, target.base_url,
          scan_run=scan_run, stub_id=stub_id)
    return program
