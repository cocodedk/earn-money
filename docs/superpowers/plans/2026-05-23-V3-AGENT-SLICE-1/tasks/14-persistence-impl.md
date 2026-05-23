# 14-persistence — Implementation Code

Part of [Task 14](14-persistence.md). This file contains Step 3.

- [ ] **Step 3: Implement persistence layer**

```python
# backend/apps/agent/persistence.py
from __future__ import annotations

from typing import Any

from django.utils import timezone

from .models import (
    AgentSession, AgentTurn, AgentAction, AgentObservation, AgentNote,
    AutonomyMode, AgentPhase, SessionStatus, TurnStatus,
    ValidationStatus, ExecutionStatus, ObservationType,
)
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


def create_session(
    *,
    scan_run: ScanRun,
    target_run: ScanTargetRun,
    target: ScanTarget,
    mission_profile: str,
    model_policy: dict[str, Any],
    mission_budget: dict[str, Any],
) -> AgentSession:
    return AgentSession.objects.create(
        scan_target_run=target_run,
        scan_run=scan_run,
        target=target,
        autonomy_mode=AutonomyMode.LAB_FREE_RUN,
        current_phase=AgentPhase.RECON,
        status=SessionStatus.RUNNING,
        mission_profile=mission_profile,
        model_policy=model_policy,
        roe_snapshot={},
        mission_budget=mission_budget,
        consumed_budget={},
        progress_counters={},
        started_at=timezone.now(),
    )


def create_turn(*, session: AgentSession, model: str) -> AgentTurn:
    last_index = (
        AgentTurn.objects.filter(session=session)
        .order_by("-index")
        .values_list("index", flat=True)
        .first()
    )
    next_index = 0 if last_index is None else last_index + 1
    return AgentTurn.objects.create(
        session=session,
        index=next_index,
        phase=session.current_phase,
        model=model,
        status=TurnStatus.STARTED,
    )


def record_action(
    *,
    turn: AgentTurn,
    action_type: str,
    args_redacted: dict[str, Any],
    goal: str = "",
    reason: str = "",
    hypothesis: str = "",
    validation_status: str = ValidationStatus.VALID,
) -> AgentAction:
    return AgentAction.objects.create(
        turn=turn,
        action_type=action_type,
        args_redacted=args_redacted,
        goal=goal,
        reason=reason,
        hypothesis=hypothesis,
        validation_status=validation_status,
        execution_status=ExecutionStatus.PENDING,
    )


def record_observation(
    *,
    action: AgentAction,
    observation_type: str,
    data: dict[str, Any],
    content_hash: str,
    artifact_refs: dict[str, Any] | None = None,
    redactions: list[str] | None = None,
) -> AgentObservation:
    return AgentObservation.objects.create(
        action=action,
        observation_type=observation_type,
        data=data,
        content_hash=content_hash,
        artifact_refs=artifact_refs or {},
        redactions=redactions or [],
        is_delta=False,
    )


def record_note(
    *,
    session: AgentSession,
    turn: AgentTurn,
    note_type: str,
    content: dict[str, Any],
    evidence_refs: list[str] | None = None,
) -> AgentNote:
    return AgentNote.objects.create(
        session=session,
        turn=turn,
        note_type=note_type,
        content=content,
        evidence_refs=evidence_refs or [],
    )


def finish_turn(turn: AgentTurn, status: str) -> None:
    turn.status = status
    turn.finished_at = timezone.now()
    turn.save(update_fields=["status", "finished_at", "updated_at"])


def finish_session(
    session: AgentSession,
    status: str,
    consumed: dict[str, Any],
) -> None:
    session.status = status
    session.consumed_budget = consumed
    session.finished_at = timezone.now()
    session.save(update_fields=[
        "status", "consumed_budget", "finished_at", "updated_at",
    ])
```

