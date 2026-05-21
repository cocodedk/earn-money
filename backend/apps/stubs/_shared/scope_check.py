"""Fetcher-level scope enforcement.

Every stub fetcher calls `enforce_scope(target, candidate_url, program,
*, scan_run=None, stub_id=None)` BEFORE issuing any HTTP. The function:

1. Parses `candidate_url` → host (HTTP/HTTPS only; hostless URLs
   rejected with `ValueError`).
2. Checks the host against the already-resolved program's scope.
3. Raises `OutOfScope` if the host is outside scope OR on the program's
   `out_of_scope` deny-list.
4. Emits a single `OUT_OF_SCOPE_REJECTED` event per (scan_run, candidate
   URL) when `scan_run` is supplied — idempotent within a process via
   a small LRU set to avoid duplicate emissions when the same candidate
   is probed twice.

Pre-flight at scan-run-start (slice D) already established that the
ScanRun's targets are in-scope; this layer catches candidate URLs the
fetcher derives at runtime (well-known paths, crawled links, etc.)
that may leave the program's surface.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any
from urllib.parse import urlsplit

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.programs.scope import matches_any, normalise_host


# Idempotent-emit cache. Bounded LRU per process; the runner re-checks
# the same candidate at most a handful of times per scan, and the cache
# size keeps memory bounded across long-lived workers.
_EMIT_CACHE_SIZE = 1024
_emit_cache: OrderedDict[tuple[str, str], None] = OrderedDict()


def _host_from_candidate(url: str) -> str:
    """Extract + normalise the host from a candidate URL."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(
            f"candidate URL must be HTTP(S), got scheme {parts.scheme!r}"
        )
    if not parts.hostname:
        raise ValueError(f"candidate URL has no hostname: {url!r}")
    return normalise_host(parts.hostname)


def _has_emitted(scan_run_id: str, candidate_url: str) -> bool:
    """LRU-checked dedup so the same rejected candidate doesn't fire
    multiple events on retry."""
    key = (scan_run_id, candidate_url)
    if key in _emit_cache:
        _emit_cache.move_to_end(key)
        return True
    _emit_cache[key] = None
    if len(_emit_cache) > _EMIT_CACHE_SIZE:
        _emit_cache.popitem(last=False)
    return False


def is_in_scope(candidate_url: str, program: Program) -> bool:
    """Pure predicate — True iff ``candidate_url``'s host is allowed
    by ``program`` (in-scope AND not on the out_of_scope deny-list).

    No side effects: emits no events, raises no exceptions for normal
    out-of-scope verdicts. Malformed URLs (non-HTTP scheme, no host)
    are treated as not-in-scope. Used by fetchers that need to gate
    each redirect hop without spamming OUT_OF_SCOPE_REJECTED.
    """
    try:
        host = _host_from_candidate(candidate_url)
    except ValueError:
        return False
    if matches_any(host, program.scope.out_of_scope):
        return False
    return matches_any(host, program.scope.in_scope)


def enforce_scope(
    target: Any,
    candidate_url: str,
    program: Program,
    *,
    scan_run: Any = None,
    stub_id: str | None = None,
) -> None:
    """Raise ``OutOfScope`` if ``candidate_url``'s host is not in
    ``program.scope``. Log an `OUT_OF_SCOPE_REJECTED` event once per
    (scan_run, candidate_url) when ``scan_run`` is supplied.

    `target` is duck-typed — only `target.base_url` is read (for the
    event payload).
    """
    try:
        host = _host_from_candidate(candidate_url)
    except ValueError as exc:
        # Treat malformed URLs as out-of-scope so the rejection path
        # is single. Don't emit an event (no scan-context to attribute
        # the rejection to in a meaningful way for triage).
        raise OutOfScope(f"malformed candidate URL: {exc}") from exc

    if matches_any(host, program.scope.out_of_scope):
        reason = f"host {host!r} on program out_of_scope deny-list"
    elif matches_any(host, program.scope.in_scope):
        return  # in scope — fetcher proceeds
    else:
        reason = f"host {host!r} not in program scope"

    if scan_run is not None and not _has_emitted(str(scan_run.id), candidate_url):
        Event.log(
            type=EventType.OUT_OF_SCOPE_REJECTED,
            scan_run=scan_run,
            target=target,
            data={
                "platform": program.platform,
                "program_slug": program.slug,
                "target_url": getattr(target, "base_url", None),
                "candidate_url": candidate_url,
                "stub_id": stub_id,
                "reason": reason,
            },
        )
    raise OutOfScope(reason)


def _reset_emit_cache_for_tests() -> None:
    """Test hook: clear the dedup cache between independent assertions."""
    _emit_cache.clear()
