"""Contract tests for `_shared/http.guard`.

Coverage matrix per [[plan slice G]]:
- RECON_ENABLED missing → ReconDisabled (no scope check, no rate-limit).
- FROZEN flag present → ProgramFrozen.
- Host not in scope → OutOfScope (and emits OUT_OF_SCOPE_REJECTED).
- In-scope happy path acquires a rate-limit token.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.test import TestCase, override_settings

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.exceptions import OutOfScope, ProgramFrozen, ReconDisabled
from apps.programs.loader import Program
from apps.programs.rate_limit import _reset_for_tests as _reset_buckets
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.http import guard, resolve_and_guard
from apps.stubs._shared.scope_check import _reset_emit_cache_for_tests
from apps.stubs._test_factories import seed_target_run


def _program(slug: str = "algolia", in_scope: list[str] | None = None) -> Program:
    return Program(
        platform="hackerone", slug=slug,
        scope=Scope(
            platform="hackerone", slug=slug,
            policy="rate-limited-OK",
            in_scope=in_scope or ["www.algolia.com"],
            out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=10),
    )


class HttpGuardTests(TestCase):
    def setUp(self) -> None:
        _reset_emit_cache_for_tests()
        _reset_buckets()

    def test_raises_when_recon_disabled(self) -> None:
        prog = _program()
        target = MagicMock(base_url="https://www.algolia.com")
        with override_settings(RECON_ENABLED_PATH="/nonexistent/RECON_ENABLED"):
            with pytest.raises(ReconDisabled):
                guard(prog, target, "https://www.algolia.com/")

    def test_raises_when_program_frozen(self, tmp_path_factory=None) -> None:
        prog = _program()
        target = MagicMock(base_url="https://www.algolia.com")
        # Settings autouse fixture in conftest sets PROGRAMS_ROOT to a
        # temp dir; create the FROZEN flag inside it.
        from django.conf import settings
        frozen = (
            Path(settings.PROGRAMS_ROOT) / "hackerone" / "algolia"
        )
        frozen.mkdir(parents=True, exist_ok=True)
        (frozen / "FROZEN").touch()
        try:
            with pytest.raises(ProgramFrozen):
                guard(prog, target, "https://www.algolia.com/")
        finally:
            (frozen / "FROZEN").unlink()

    def test_raises_out_of_scope_for_off_host(self) -> None:
        scan_run, target_run = seed_target_run(
            base_url="https://www.algolia.com", stub_slug="1.20",
        )
        prog = _program()
        with pytest.raises(OutOfScope):
            guard(
                prog, target_run.target, "https://evil.example/",
                scan_run=scan_run, stub_id="1.X",
            )
        # An audit event was emitted for the rejected candidate.
        events = Event.objects.filter(type=EventType.OUT_OF_SCOPE_REJECTED)
        self.assertEqual(events.count(), 1)

    def test_in_scope_returns_silently(self) -> None:
        prog = _program()
        target = MagicMock(base_url="https://www.algolia.com")
        # No exception, no event. Acquires a rate-limit token.
        guard(prog, target, "https://www.algolia.com/path")

    def test_resolve_and_guard_returns_program(self) -> None:
        """resolve_and_guard looks up the program from the registry
        and guards the base_url; returns the resolved Program so
        multi-URL runners can re-guard candidate URLs."""
        scan_run, target_run = seed_target_run(
            base_url="https://www.algolia.com", stub_slug="1.X",
        )
        from apps.programs.loader import get_registry
        from unittest.mock import patch
        prog = _program()
        with patch.object(get_registry(), "find_for_host", return_value=prog):
            out = resolve_and_guard(scan_run, target_run.target, stub_id="1.X")
        self.assertIs(out, prog)

    def test_resolve_and_guard_raises_out_of_scope(self) -> None:
        """When the resolved program's scope excludes the target host,
        resolve_and_guard raises OutOfScope after emitting the event."""
        scan_run, target_run = seed_target_run(
            base_url="https://www.algolia.com", stub_slug="1.X",
        )
        from apps.programs.loader import get_registry
        from unittest.mock import patch
        off_scope_prog = _program(in_scope=["other.example"])
        with patch.object(get_registry(), "find_for_host", return_value=off_scope_prog):
            with pytest.raises(OutOfScope):
                resolve_and_guard(scan_run, target_run.target, stub_id="1.X")
