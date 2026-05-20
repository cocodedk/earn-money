"""Stub `well_known_paths` registers under spec ID "1.20" via @register.

Single-owner pattern: ONE @register("1.20") absorbs all six spec
families (1.20-1.25). Specs 1.21-1.25 close via frontmatter, not via
additional registrations — assert that explicitly.

Spec sources: 1.20-1.25 + closeout plan slice WKP-A.
"""
from __future__ import annotations

import importlib

from apps.events.types import EventType
from apps.stubs.runners import get as get_runner


def test_120_is_registered() -> None:
    """Re-import the runner module so `@register("1.20")` fires."""
    from apps.stubs.well_known_paths import runner as runner_module
    importlib.reload(runner_module)
    assert get_runner("1.20") is runner_module.run


def test_121_to_125_are_not_registered_as_separate_stubs() -> None:
    """Specs 1.21-1.25 are absorbed by stub 1.20; no separate
    @register calls."""
    for slug in ("1.21", "1.22", "1.23", "1.24", "1.25"):
        assert get_runner(slug) is None, (
            f"spec {slug} should be absorbed by 1.20, not separately registered"
        )


def test_finding_created_event_type_exists() -> None:
    """Plan slice WKP-A step 5: `FINDING_CREATED` is added to
    EventType enum (was missing — only FINDING_STATUS_CHANGED
    existed)."""
    assert EventType.FINDING_CREATED.value == "finding.created"
