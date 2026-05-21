"""Unit test for `_shared/auth/events.log_finding_candidate`."""
from __future__ import annotations

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._test_factories import seed_target_run


@pytest.mark.django_db
def test_log_finding_candidate_emits_event() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.x")
    finding = Finding.objects.create(
        scan_run=scan_run, target=target_run.target, stub_slug="2.x",
        title="probe found something", category="auth_test",
        severity="low", confidence="low", status=FindingStatus.CANDIDATE,
        data={},
    )
    log_finding_candidate(finding, stub_id="2.x")
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    )
    assert ev.data["finding_id"] == str(finding.id)
    assert ev.data["stub"] == "2.x"
