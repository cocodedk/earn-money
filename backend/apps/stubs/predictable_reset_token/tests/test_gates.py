"""Gate tests for stub 2.5 (predictable-reset-token).

The fixture-secret + mailbox-backend gates moved into the detection
chain (test_detection.py). This file covers only the two pre-flight
gates: RoE knob + authorised test account.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import get_registry
from apps.stubs._test_factories import seed_target_run
from apps.stubs.predictable_reset_token.runner import run
from apps.stubs.predictable_reset_token.tests._helpers import _program


@pytest.mark.django_db
def test_roe_disabled() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(reset_probes=False)):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "roe_disabled"


@pytest.mark.django_db
def test_no_authorized_accounts() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program(accounts=[])):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["detail"] == "no_authorized_test_accounts"
