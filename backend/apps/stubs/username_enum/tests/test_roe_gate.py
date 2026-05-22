"""Tests for stub 2.1's RoE gating — refuses when
`roe.allow_active_login_probes` is False.

The fetcher-level / submit-level paths are tested separately so this
file stays focused on the RoE decision + event emission.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import get_registry
from apps.stubs._test_factories import seed_target_run
from apps.stubs.username_enum.runner import run
from apps.stubs.username_enum.tests._helpers import _program


@pytest.mark.django_db
def test_runner_refuses_when_roe_disabled() -> None:
    """RoE.allow_active_login_probes=False emits AUTH_PROBE_REFUSED
    with reason="roe_disabled" and makes ZERO HTTP requests."""
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )
    prog = _program(login_probes=False)

    with patch.object(get_registry(), "find_for_host", return_value=prog):
        run(scan_run, target_run)

    refused = Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert refused.count() == 1
    ev = refused.first()
    assert ev.data["reason"] == "roe_disabled"
    assert ev.data["stub"] == "2.1"
    assert ev.data["would_have_submitted"] is False
    assert ev.data["knob"] == "allow_active_login_probes"
    assert str(ev.subject_id) == str(target_run.id)


@pytest.mark.django_db
def test_runner_proceeds_when_roe_enabled() -> None:
    """RoE.allow_active_login_probes=True means the RoE gate doesn't
    fire — the runner proceeds (and will subsequently halt on the
    fixture-required guard since slice 02 chunk 1 doesn't ship the
    fetcher yet)."""
    scan_run, target_run = seed_target_run(
        host="x.example", stub_slug="2.1",
    )
    prog = _program(login_probes=True)

    with patch.object(get_registry(), "find_for_host", return_value=prog):
        run(scan_run, target_run)

    # No RoE refusal event — RoE is permissive.
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
        data__contains={"reason": "roe_disabled"},
    ).count() == 0
