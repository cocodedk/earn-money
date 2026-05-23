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
    autonomy_mode = models.CharField(max_length=20, choices=AutonomyMode.choices)
    current_phase = models.CharField(max_length=16, choices=AgentPhase.choices)
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


class TurnStatus(models.TextChoices):
    STARTED = "started", "Started"
    ACTION_PROPOSED = "action_proposed", "Action proposed"
    ACTION_DENIED = "action_denied", "Action denied"
    ACTION_EXECUTED = "action_executed", "Action executed"
    COMPLETED = "completed", "Completed"
    ERROR = "error", "Error"


class AgentTurn(TimestampedUUIDModel):
    session = models.ForeignKey(
        AgentSession, on_delete=models.CASCADE, related_name="turns",
    )
    index = models.PositiveIntegerField()
    phase = models.CharField(max_length=16, choices=AgentPhase.choices)
    model = models.CharField(max_length=128)
    prompt_artifact_ref = models.CharField(max_length=256, blank=True, default="")
    response_artifact_ref = models.CharField(max_length=256, blank=True, default="")
    prompt_hash = models.CharField(max_length=64, blank=True, default="")
    response_hash = models.CharField(max_length=64, blank=True, default="")
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_estimate = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True,
    )
    status = models.CharField(
        max_length=20, choices=TurnStatus.choices, default=TurnStatus.STARTED,
    )
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("session", "index"), name="uniq_turn_index_per_session",
            )
        ]
        ordering = ("session", "index")
