from __future__ import annotations

from django.utils import timezone

from .models import (
    AgentAction,
    AgentNote,
    AgentObservation,
    AgentSession,
    AgentTurn,
    ExecutionStatus,
    NoteType,
    ObservationType,
    SessionStatus,
    TurnStatus,
    ValidationStatus,
)


def create_session(
    scan_run,
    target_run,
    target,
    mission_profile: str,
    model_policy: dict,
    mission_budget: dict,
) -> AgentSession:
    """Create and return a new RUNNING AgentSession."""
    from .models import AgentPhase, AutonomyMode
    return AgentSession.objects.create(
        scan_run=scan_run,
        scan_target_run=target_run,
        target=target,
        autonomy_mode=AutonomyMode.LAB_FREE_RUN,
        current_phase=AgentPhase.RECON,
        status=SessionStatus.RUNNING,
        mission_profile=mission_profile,
        model_policy=model_policy,
        mission_budget=mission_budget,
        roe_snapshot={},
        consumed_budget={},
        progress_counters={},
        started_at=timezone.now(),
    )


def create_turn(session: AgentSession, model: str) -> AgentTurn:
    """Create the next turn for session, auto-incrementing index."""
    last = session.turns.order_by("-index").first()
    index = (last.index + 1) if last else 0
    return AgentTurn.objects.create(
        session=session,
        index=index,
        phase=session.current_phase,
        model=model,
        status=TurnStatus.STARTED,
    )


def record_action(
    turn: AgentTurn,
    action_type: str,
    args_redacted: dict,
    goal: str = "",
    reason: str = "",
    hypothesis: str = "",
    validation_status: str = ValidationStatus.VALID,
) -> AgentAction:
    """Persist a proposed action on a turn."""
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
    action: AgentAction,
    observation_type: str,
    data: dict,
    content_hash: str = "",
    artifact_refs: dict | None = None,
    redactions: list | None = None,
    is_delta: bool = False,
) -> AgentObservation:
    """Persist an observation produced by executing an action."""
    return AgentObservation.objects.create(
        action=action,
        observation_type=observation_type,
        data=data,
        content_hash=content_hash,
        artifact_refs=artifact_refs or {},
        redactions=redactions or [],
        is_delta=is_delta,
    )


def record_note(
    session: AgentSession,
    turn: AgentTurn,
    note_type: str,
    content: dict,
    evidence_refs: list | None = None,
) -> AgentNote:
    """Persist an agent-generated note."""
    return AgentNote.objects.create(
        session=session,
        turn=turn,
        note_type=note_type,
        content=content,
        evidence_refs=evidence_refs or [],
    )


def finish_turn(turn: AgentTurn, status: str) -> None:
    """Set turn status and finished_at timestamp."""
    turn.status = status
    turn.finished_at = timezone.now()
    turn.save(update_fields=["status", "finished_at"])


def finish_session(
    session: AgentSession,
    status: str,
    consumed: dict,
) -> None:
    """Close an agent session with final status and consumed budget."""
    session.status = status
    session.consumed_budget = consumed
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "consumed_budget", "finished_at"])
