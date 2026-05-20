"""Scan-run pre-flight checks.

Run BEFORE creating any `ScanRun` row or enqueuing a Celery task.
Refuses out-of-scope / manual-only / ambiguous / frozen / kill-
switched dispatches with a single narrow exception type so callers
(typically `ScanRunSerializer.validate`) can convert to an explicit
4xx response without leaking implementation details.

URL normalisation: HTTP(S) only, hostless URLs rejected, IDNA / lower-
case / trailing-dot handled by `scope.normalise_host`.
"""
from __future__ import annotations

from typing import Iterable
from urllib.parse import urlsplit

from .exceptions import (
    AmbiguousPolicy,
    ManualOnly,
    OutOfScope,
)
from .flags import is_program_frozen, require_recon_enabled
from .loader import Program, get_registry
from .scope import normalise_host


_ALLOWED_SCHEMES = ("http", "https")


def host_from_url(url: str) -> str:
    """Pull the host out of an HTTP(S) URL and normalise it.

    Rejects non-HTTP(S) schemes and URLs without a hostname with
    `ValueError`. Lower-cases, strips one trailing dot, IDNA-encodes.
    """
    if not isinstance(url, str) or not url:
        raise ValueError("empty URL")
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme must be one of {_ALLOWED_SCHEMES}, got {parts.scheme!r}"
        )
    host = parts.hostname
    if not host:
        raise ValueError(f"URL has no hostname: {url!r}")
    return normalise_host(host)


def preflight_scan_run(
    target_urls: Iterable[str], *, active: bool = True,
) -> list[Program]:
    """Run every scan-run pre-flight check; return the resolved Program
    per target (in input order).

    Pipeline:
    1. `require_recon_enabled()` — master kill-switch.
    2. For each target URL:
        a. normalise → host
        b. `find_for_host(host)` → Program (raises OutOfScope /
           AmbiguousProgram).
        c. policy guard (rate-limited-OK passes; manual-only raises
           ManualOnly; ambiguous raises AmbiguousPolicy for active
           stubs).
        d. `is_program_frozen()` raises `ProgramFrozen`.

    Raises any of: `ReconDisabled`, `OutOfScope`, `AmbiguousProgram`,
    `ManualOnly`, `AmbiguousPolicy`, `ProgramFrozen`, or `ValueError`
    (URL-shape rejection).
    """
    require_recon_enabled()  # ReconDisabled if missing
    registry = get_registry()
    programs: list[Program] = []
    for url in target_urls:
        host = host_from_url(url)
        program = registry.find_for_host(host)  # OutOfScope / AmbiguousProgram
        _enforce_policy(program, active=active)
        _enforce_not_frozen(program)
        programs.append(program)
    return programs


def _enforce_policy(program: Program, *, active: bool) -> None:
    """Refuse `manual-only` always; refuse `ambiguous` for active stubs."""
    policy = program.scope.policy
    if policy == "manual-only":
        raise ManualOnly(
            f"program {program.platform}/{program.slug} is manual-only — "
            "operator must scan by hand"
        )
    if policy == "ambiguous" and active:
        raise AmbiguousPolicy(
            f"program {program.platform}/{program.slug} has ambiguous ToS — "
            "active stubs disallowed; passive recon only"
        )


def _enforce_not_frozen(program: Program) -> None:
    """Raise `ProgramFrozen` when the per-program FROZEN flag is set."""
    if is_program_frozen(program.platform, program.slug):
        from .exceptions import ProgramFrozen  # local import keeps deps tight
        raise ProgramFrozen(
            f"program {program.platform}/{program.slug} is FROZEN — "
            "operator paused recon for this program"
        )
