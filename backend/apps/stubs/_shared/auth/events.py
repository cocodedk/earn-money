"""Shared event-emission helpers for Phase 2 auth stubs.

`log_finding_candidate` files the canonical AUTH_FINDING_CANDIDATE
event filed when a stub creates a candidate Finding. All Phase 2
stubs use this — the data payload shape is contract for the
em-frontend dashboard.
"""
from __future__ import annotations

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding


def log_finding_candidate(finding: Finding, *, stub_id: str) -> None:
    """Emit AUTH_FINDING_CANDIDATE for a freshly-created Finding."""
    Event.log(
        type=EventType.AUTH_FINDING_CANDIDATE,
        scan_run=finding.scan_run,
        target=finding.target,
        subject=finding,
        data={"finding_id": str(finding.id), "stub": stub_id},
    )
