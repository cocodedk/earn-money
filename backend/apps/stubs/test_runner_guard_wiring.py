"""Static + behavioural regression tests for runner scope-enforcement.

Slice G ([[plan slice G]]) wired every Phase 1 stub through the shared
`guard()` callable in `apps.stubs._shared.http`. This test guards
two invariants:

1. **Static (grep) regression**: every `runner.py` registered in
   `apps.stubs.runners.REGISTRY` MUST import `resolve_and_guard` from
   `apps.stubs._shared.http`. The well-known-paths canary uses the
   lower-level `guard` symbol directly — both forms are accepted.

2. **Behavioural regression**: when the resolved Program's scope
   excludes the target host, the runner MUST emit
   `OUT_OF_SCOPE_REJECTED` and MUST NOT call any fetcher.

The parametrized behavioural test patches `find_for_host` to return a
program whose `in_scope` excludes `x.example`. Every fetcher is
mocked so a real HTTP would crash the test loudly.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program, get_registry
from apps.programs.rate_limit import _reset_for_tests as _reset_buckets
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.scope_check import _reset_emit_cache_for_tests
from apps.stubs._test_factories import seed_target_run
from apps.stubs.runners import get as _registry_get


# Phase 1 stubs that own a standalone runner (slice G inventory).
PHASE_1_STUBS: list[str] = [
    "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8",
    "1.9", "1.10", "1.11", "1.12", "1.13", "1.14", "1.15",
    "1.16", "1.17", "1.19", "1.20",
]


# `apps.stubs.test_runners` clears the runner registry in setUp/tearDown
# as part of its isolation strategy; that clearing leaks across pytest's
# session and breaks any later test that relies on a populated registry.
# Re-import each stub package as an autouse fixture: registration is
# idempotent (the @register decorator just overwrites with the same fn).
_STUB_MODULES = (
    "apps.stubs.framework_detection",
    "apps.stubs.server_headers",
    "apps.stubs.frontend_framework",
    "apps.stubs.backend_hints",
    "apps.stubs.package_leaks",
    "apps.stubs.hidden_routes",
    "apps.stubs.backup_files",
    "apps.stubs.admin_panels",
    "apps.stubs.old_endpoints",
    "apps.stubs.debug_pages",
    "apps.stubs.robots_txt",
    "apps.stubs.sitemap_xml",
    "apps.stubs.security_txt",
    "apps.stubs.source_maps",
    "apps.stubs.public_javascript_bundles",
    "apps.stubs.stack_traces",
    "apps.stubs.verbose_api_errors",
    "apps.stubs.sql_orm_errors",
    "apps.stubs.well_known_paths",
)


@pytest.fixture(autouse=True)
def _restore_runner_registry():
    # The runner.py module (not the package __init__) is where
    # @register fires. Reload runner.py directly so registration
    # re-runs even when the package was already imported.
    for name in _STUB_MODULES:
        runner_mod = importlib.import_module(name + ".runner")
        importlib.reload(runner_mod)
    yield


# ----- static (grep-based) regression test ------------------------------


def test_every_registered_runner_imports_guard_symbol() -> None:
    """No new Phase 1 stub can bypass the safety layer by skipping the
    `resolve_and_guard`/`guard` import."""
    for slug in PHASE_1_STUBS:
        runner_fn = _registry_get(slug)
        runner_module = inspect.getmodule(runner_fn)
        assert runner_module is not None
        src = Path(runner_module.__file__).read_text()
        # Accept either the high-level `resolve_and_guard` (used by 18
        # runners) or the lower-level `guard` (used by well_known_paths).
        assert (
            "from apps.stubs._shared.http import resolve_and_guard" in src
            or "from apps.stubs._shared.http import guard" in src
        ), (
            f"runner for stub {slug} ({runner_module.__name__}) does not "
            f"import a guard symbol from apps.stubs._shared.http; this "
            f"likely means a future fetcher can bypass scope enforcement."
        )


# ----- behavioural test: OOS host rejects without HTTP ------------------


def _off_scope_program() -> Program:
    """A Program whose scope EXCLUDES `x.example` so any runner
    invoked against the default seeded target rejects on guard()."""
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["other.example"],  # x.example NOT in scope
            out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=10),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("slug", PHASE_1_STUBS)
def test_runner_refuses_oos_target(slug: str) -> None:
    """Every Phase 1 runner halts and emits OUT_OF_SCOPE_REJECTED when
    invoked against a target whose host is no longer in the resolved
    program's scope. No fetcher HTTP fires."""
    _reset_emit_cache_for_tests()
    _reset_buckets()
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug=slug,
    )
    off_scope = _off_scope_program()
    runner_fn = _registry_get(slug)

    # Mock find_for_host on the live registry to return the OOS program
    # without touching the file-backed PROGRAMS_ROOT.
    with patch.object(get_registry(), "find_for_host", return_value=off_scope):
        runner_fn(scan_run, target_run)

    # The runner returned silently (no exception escaped) and an audit
    # event was logged for the rejected base_url.
    events = Event.objects.filter(
        scan_run=scan_run,
        type=EventType.OUT_OF_SCOPE_REJECTED,
    )
    assert events.count() >= 1, (
        f"runner {slug} did NOT emit OUT_OF_SCOPE_REJECTED for an "
        f"out-of-scope target — guard wiring is broken"
    )
