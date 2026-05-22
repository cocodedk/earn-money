"""Contract tests for `apps.events.types.EventType` string values.

The dashboard, SSE stream, and any frontend consumer keys off the
string values — not the enum-member names. Renaming a value silently
breaks the contract; these tests lock the value strings in.
"""
from __future__ import annotations

from apps.events.types import EventType


def test_scope_enforcement_event_values_stable() -> None:
    """Slice E (scope-enforcement) + slice H (post-scan analytics)
    event-type strings — frontend depends on these literals."""
    assert EventType.OUT_OF_SCOPE_REJECTED.value == "scan.out_of_scope_rejected"
    assert EventType.EDGE_BLOCKING_DETECTED.value == "scan.edge_blocking_detected"


def test_phase_2_auth_event_values_stable() -> None:
    """Phase 2 auth event strings — reserved in slice 01, first emit
    in slice 02. Renames here are an em-frontend contract break."""
    assert EventType.AUTH_PROBE_REFUSED.value == "auth.probe_refused"
    assert EventType.AUTH_FINDING_CANDIDATE.value == "auth.finding_candidate"
    assert EventType.AUTH_FIXTURE_REQUIRED.value == "auth.fixture_required"


def test_finding_lifecycle_event_values_stable() -> None:
    assert EventType.FINDING_CREATED.value == "finding.created"
    assert EventType.FINDING_STATUS_CHANGED.value == "finding.status_changed"
