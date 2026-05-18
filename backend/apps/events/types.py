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
    # Scan-run lifecycle — creation here; start/pause/resume/stop land later.
    SCAN_RUN_CREATED = "scan_run.created", "Scan run created"
