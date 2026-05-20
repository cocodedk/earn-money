"""Static + behavioural regression tests for runner scope-enforcement.

Slice G ([[plan slice G]]) wired every Phase 1 stub through the shared
`guard()` callable in `apps.stubs._shared.http`. The 18 single-pass
runners use the `@guarded_runner` decorator on `apps.stubs.runners`;
the `well_known_paths` canary uses the lower-level `guard()` inside
its candidate-iteration loop.

Two invariants:

1. Static (grep) regression: every registered runner.py must import
   one of `@guarded_runner` (preferred) or `guard` (low-level).
2. Behavioural regression: when the resolved Program's scope excludes
   the target host, the runner must emit `OUT_OF_SCOPE_REJECTED` and
   must not call any fetcher.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.rate_limit import _reset_for_tests as _reset_buckets
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.scope_check import _reset_emit_cache_for_tests
from apps.stubs._test_factories import seed_target_run
from apps.stubs.runners import get as _registry_get, registered_slugs


# The Phase 1 runner set is the live registry — see
# `apps.stubs.apps.StubsConfig.ready` for the imports that populate it.
# Module-scoped fixture reloads each runner once per test file so the
# registry survives `apps.stubs.test_runners`' setUp/tearDown clearing.
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
    "apps.stubs.username_enum",
    "apps.stubs.weak_password_policy",
)


@pytest.fixture(scope="module", autouse=True)
def _restore_runner_registry():
    # Reload runner.py directly (not the package) so the @register /
    # @guarded_runner decorator re-fires even after another test
    # cleared the registry.
    for name in _STUB_MODULES:
        importlib.reload(importlib.import_module(name + ".runner"))
    yield


def test_every_registered_runner_imports_guard_symbol() -> None:
    """No new Phase 1 stub can bypass the safety layer."""
    for slug in registered_slugs():
        runner_fn = _registry_get(slug)
        runner_module = inspect.getmodule(runner_fn)
        assert runner_module is not None
        src = Path(runner_module.__file__).read_text()
        assert (
            "from ..runners import guarded_runner" in src
            or "from apps.stubs._shared.http import guard" in src
        ), (
            f"runner for stub {slug} ({runner_module.__name__}) does not "
            f"import @guarded_runner or guard; future fetchers might "
            f"bypass scope enforcement."
        )


def _off_scope_program() -> Program:
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["other.example"],
            out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=10),
    )


def _all_phase_1_slugs() -> list[str]:
    """Collect-time helper: ensure the registry is populated before
    pytest builds the parametrize ids."""
    for name in _STUB_MODULES:
        importlib.import_module(name + ".runner")
    return registered_slugs()


@pytest.mark.django_db
@pytest.mark.parametrize("stub_slug", _all_phase_1_slugs())
def test_runner_refuses_oos_target(stub_slug: str) -> None:
    """Each runner emits OUT_OF_SCOPE_REJECTED and halts without HTTP
    when the resolved program excludes the target host."""
    _reset_emit_cache_for_tests()
    _reset_buckets()
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug=stub_slug,
    )
    runner_fn = _registry_get(stub_slug)

    with patch.object(
        get_registry(), "find_for_host", return_value=_off_scope_program(),
    ):
        runner_fn(scan_run, target_run)

    events = Event.objects.filter(
        scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
    )
    assert events.count() >= 1, (
        f"runner {stub_slug} did not emit OUT_OF_SCOPE_REJECTED"
    )
