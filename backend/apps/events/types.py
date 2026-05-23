"""Typed event keys.

Every emit-site uses a value from this enum. Adding a new event type
means adding it here first, then writing the test that asserts a caller
emits it. Freeform strings are refused at the model layer via choices=.

New types land alongside the feature that emits them — keep the enum
lean. See [[project-event-log-medium-done-well]] for the rule.
"""
from __future__ import annotations

from django.db import models


class EventType(models.TextChoices):
    # Sanity / test fixture — kept for system-test events and tests.
    SYSTEM_TEST = "system.test", "System test event"
    # Project lifecycle
    PROJECT_CREATED = "project.created", "Project created"
    PROJECT_UPDATED = "project.updated", "Project updated"
    PROJECT_DELETED = "project.deleted", "Project deleted"
    # Target lifecycle
    TARGET_CREATED = "target.created", "Target created"
    TARGET_UPDATED = "target.updated", "Target updated"
    TARGET_DELETED = "target.deleted", "Target deleted"
    # Scan-run lifecycle
    SCAN_RUN_CREATED = "scan_run.created", "Scan run created"
    SCAN_RUN_STARTED = "scan_run.started", "Scan run started"
    SCAN_RUN_PAUSED = "scan_run.paused", "Scan run paused"
    SCAN_RUN_RESUMED = "scan_run.resumed", "Scan run resumed"
    SCAN_RUN_STOPPED = "scan_run.stopped", "Scan run stopped"
    SCAN_RUN_STOPPED_FINAL = "scan_run.stopped_final", "Scan run finalised after stop"
    SCAN_RUN_DONE = "scan_run.done", "Scan run completed"
    SCAN_RUN_FAILED = "scan_run.failed", "Scan run failed"
    # Per-target progress emitted by the worker simulator (will be reused
    # by real stub runners once they land).
    SCAN_TARGET_RUN_STARTED = "scan_target_run.started", "Scan target run started"
    SCAN_TARGET_RUN_DONE = "scan_target_run.done", "Scan target run completed"
    SCAN_TARGET_RUN_STOPPED = "scan_target_run.stopped", "Scan target run stopped"
    SCAN_TARGET_RUN_FAILED = "scan_target_run.failed", "Scan target run failed"
    # Finding emitted by a stub runner (new candidate persisted).
    FINDING_CREATED = "finding.created", "Finding created"
    # Finding triage by the operator (candidate → confirmed/rejected/stale).
    FINDING_STATUS_CHANGED = "finding.status_changed", "Finding status changed"
    # Scope-enforcement: fetcher refused a candidate URL outside the
    # resolved program's scope. Recon halts for that candidate; the
    # event is the audit trail.
    OUT_OF_SCOPE_REJECTED = "scan.out_of_scope_rejected", "Out-of-scope candidate URL rejected"
    # Post-scan signal: a known CDN/WAF returned 4xx for most probes
    # so the origin was never reached. Surfaces in the dashboard as
    # an explanatory banner instead of a silent "0 findings" outcome.
    EDGE_BLOCKING_DETECTED = "scan.edge_blocking_detected", "Edge / WAF blocked probes before origin"
    # Phase 2 — authentication scanning. Reserved here in slice 01;
    # first emit lands in slice 02 (stub 2.1 canary).
    AUTH_PROBE_REFUSED = "auth.probe_refused", "Active auth probe refused by RoE / safety gate"
    AUTH_FINDING_CANDIDATE = "auth.finding_candidate", "Auth Finding emitted with status=candidate"
    AUTH_FIXTURE_REQUIRED = "auth.fixture_required", "Stub refused live target — fixture validation missing"
    # V3 Agent lifecycle
    AGENT_SESSION_STARTED = "agent.session_started", "Agent session started"
    AGENT_ACTION_EXECUTED = "agent.action_executed", "Agent action executed"
    AGENT_ACTION_DENIED = "agent.action_denied", "Agent action denied"
    AGENT_PHASE_CHANGED = "agent.phase_changed", "Agent phase changed"
    AGENT_NOTE_CREATED = "agent.note_created", "Agent note created"
    AGENT_MISSION_FINISHED = "agent.mission_finished", "Agent mission finished"
