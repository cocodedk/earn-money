# 01-session-turn-models — Implementation Code

Part of [Task 01](01-session-turn-models.md). This file contains Step 3.

- [ ] **Step 3: Write AgentSession model**

```python
# backend/apps/agent/__init__.py
# (empty)

# backend/apps/agent/apps.py
from django.apps import AppConfig

class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agent"
    verbose_name = "V3 Agent"
```

```python
# backend/apps/agent/models.py
from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedUUIDModel
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


class AutonomyMode(models.TextChoices):
    LAB_FREE_RUN = "lab_free_run", "Lab free run"
    REAL_CHECKPOINTED = "real_checkpointed", "Real checkpointed"


class AgentPhase(models.TextChoices):
    RECON = "recon", "Recon"
    ENUMERATE = "enumerate", "Enumerate"
    PROBE = "probe", "Probe"
    VERIFY = "verify", "Verify"
    REPORT = "report", "Report"


class SessionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    STOPPED = "stopped", "Stopped"


class AgentSession(TimestampedUUIDModel):
    scan_target_run = models.OneToOneField(
        ScanTargetRun, on_delete=models.CASCADE, related_name="agent_session",
    )
    scan_run = models.ForeignKey(
        ScanRun, on_delete=models.CASCADE, related_name="agent_sessions",
    )
    target = models.ForeignKey(
        ScanTarget, on_delete=models.CASCADE, related_name="agent_sessions",
    )
    autonomy_mode = models.CharField(
        max_length=20, choices=AutonomyMode.choices,
    )
    current_phase = models.CharField(
        max_length=16, choices=AgentPhase.choices,
    )
    status = models.CharField(
        max_length=16, choices=SessionStatus.choices, default=SessionStatus.PENDING,
    )
    mission_profile = models.CharField(max_length=64)
    model_policy = models.JSONField(default=dict)
    roe_snapshot = models.JSONField(default=dict)
    mission_budget = models.JSONField(default=dict)
    consumed_budget = models.JSONField(default=dict)
    progress_counters = models.JSONField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
```

