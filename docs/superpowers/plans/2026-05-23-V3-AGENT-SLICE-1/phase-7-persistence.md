# Phase 7 — Persistence & Event Logging

### Task 14: Persistence layer

**Files:**
- Create: `backend/apps/agent/persistence.py`
- Create: `backend/apps/agent/tests/test_persistence.py`

- [ ] **Step 1: Write tests for persistence helpers**

```python
# backend/apps/agent/tests/test_persistence.py
import pytest
from apps.agent.persistence import (
    create_session, create_turn, record_action,
    record_observation, record_note, finish_turn, finish_session,
)
from apps.agent.models import (
    AgentSession, AgentTurn, AgentAction, AgentObservation, AgentNote,
    SessionStatus, TurnStatus, ValidationStatus, ExecutionStatus,
)
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project


@pytest.fixture
def scan_context():
    project = Project.objects.create(name="test")
    target = ScanTarget.objects.create(host="juiceshop.cocode.dk", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return scan_run, target_run, target


@pytest.mark.django_db
def test_create_session(scan_context):
    scan_run, target_run, target = scan_context
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="juice_shop_scoreboard",
        model_policy={"primary_model": "claude-sonnet-4-6"},
        mission_budget={"max_turns": 25},
    )
    assert session.status == SessionStatus.RUNNING
    assert session.current_phase == "recon"
    assert session.started_at is not None


@pytest.mark.django_db
def test_create_turn(scan_context):
    scan_run, target_run, target = scan_context
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    turn = create_turn(session=session, model="claude-sonnet-4-6")
    assert turn.index == 0
    assert turn.status == TurnStatus.STARTED
    assert turn.phase == session.current_phase


@pytest.mark.django_db
def test_create_sequential_turns(scan_context):
    scan_run, target_run, target = scan_context
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    t0 = create_turn(session=session, model="m")
    t1 = create_turn(session=session, model="m")
    assert t0.index == 0
    assert t1.index == 1


@pytest.mark.django_db
def test_record_action(scan_context):
    scan_run, target_run, target = scan_context
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    turn = create_turn(session=session, model="m")
    action = record_action(
        turn=turn, action_type="observe_page", args_redacted={},
        goal="See page", validation_status=ValidationStatus.VALID,
    )
    assert action.action_type == "observe_page"
    assert action.execution_status == ExecutionStatus.PENDING


@pytest.mark.django_db
def test_record_observation(scan_context):
    scan_run, target_run, target = scan_context
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    turn = create_turn(session=session, model="m")
    action = record_action(
        turn=turn, action_type="observe_page", args_redacted={},
        goal="See", validation_status=ValidationStatus.VALID,
    )
    obs = record_observation(
        action=action, observation_type="page",
        data={"page": {"path": "/"}}, content_hash="abc",
    )
    assert obs.observation_type == "page"


@pytest.mark.django_db
def test_record_note(scan_context):
    scan_run, target_run, target = scan_context
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    turn = create_turn(session=session, model="m")
    note = record_note(
        session=session, turn=turn, note_type="candidate",
        content={"category": "hidden_route", "path": "/score-board"},
        evidence_refs=["obs_1"],
    )
    assert note.note_type == "candidate"


@pytest.mark.django_db
def test_finish_session(scan_context):
    scan_run, target_run, target = scan_context
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    finish_session(session, status=SessionStatus.COMPLETED, consumed={"turns": 5})
    session.refresh_from_db()
    assert session.status == SessionStatus.COMPLETED
    assert session.finished_at is not None
    assert session.consumed_budget == {"turns": 5}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_persistence.py -v`
Expected: FAIL

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

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_persistence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/persistence.py backend/apps/agent/tests/test_persistence.py
git commit -m "feat(agent): add persistence layer for agent models"
```

### Task 15: Event logging helpers + event types

**Files:**
- Modify: `backend/apps/events/types.py`
- Create: `backend/apps/agent/event_log.py`
- Create: `backend/apps/agent/tests/test_event_log.py`

- [ ] **Step 1: Write tests for event emission**

```python
# backend/apps/agent/tests/test_event_log.py
import pytest
from apps.agent.event_log import emit_session_started, emit_action_executed, emit_mission_finished
from apps.agent.models import AgentSession, SessionStatus
from apps.events.models import Event
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project
from apps.agent.persistence import create_session


@pytest.fixture
def session():
    project = Project.objects.create(name="test")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )


@pytest.mark.django_db
def test_emit_session_started(session):
    emit_session_started(session)
    events = Event.objects.filter(type="agent.session_started")
    assert events.count() == 1
    assert events[0].data["mission_profile"] == "test"


@pytest.mark.django_db
def test_emit_action_executed(session):
    emit_action_executed(
        session=session, turn_index=0, action_type="observe_page",
    )
    events = Event.objects.filter(type="agent.action_executed")
    assert events.count() == 1


@pytest.mark.django_db
def test_emit_mission_finished(session):
    emit_mission_finished(session, status="completed", reason="objective met")
    events = Event.objects.filter(type="agent.mission_finished")
    assert events.count() == 1
    assert events[0].data["reason"] == "objective met"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_event_log.py -v`
Expected: FAIL

- [ ] **Step 3: Add agent event types**

Append to `backend/apps/events/types.py`:

```python
    # V3 Agent lifecycle
    AGENT_SESSION_STARTED = "agent.session_started", "Agent session started"
    AGENT_ACTION_EXECUTED = "agent.action_executed", "Agent action executed"
    AGENT_ACTION_DENIED = "agent.action_denied", "Agent action denied"
    AGENT_PHASE_CHANGED = "agent.phase_changed", "Agent phase changed"
    AGENT_NOTE_CREATED = "agent.note_created", "Agent note created"
    AGENT_MISSION_FINISHED = "agent.mission_finished", "Agent mission finished"
```

- [ ] **Step 4: Implement event_log.py**

```python
# backend/apps/agent/event_log.py
from __future__ import annotations

from apps.events.models import Event
from .models import AgentSession


def emit_session_started(session: AgentSession) -> Event:
    return Event.log(
        type="agent.session_started",
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Agent session started: {session.mission_profile}",
        data={
            "mission_profile": session.mission_profile,
            "autonomy_mode": session.autonomy_mode,
            "phase": session.current_phase,
        },
    )


def emit_action_executed(
    session: AgentSession, turn_index: int, action_type: str,
) -> Event:
    return Event.log(
        type="agent.action_executed",
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Turn {turn_index}: {action_type}",
        data={"turn_index": turn_index, "action_type": action_type},
    )


def emit_action_denied(
    session: AgentSession, turn_index: int,
    action_type: str, reason: str,
) -> Event:
    return Event.log(
        type="agent.action_denied",
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        level="warning",
        message=f"Turn {turn_index}: {action_type} denied — {reason}",
        data={"turn_index": turn_index, "action_type": action_type, "reason": reason},
    )


def emit_phase_changed(
    session: AgentSession, from_phase: str, to_phase: str, reason: str,
) -> Event:
    return Event.log(
        type="agent.phase_changed",
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Phase: {from_phase} → {to_phase}",
        data={"from_phase": from_phase, "to_phase": to_phase, "reason": reason},
    )


def emit_note_created(
    session: AgentSession, note_type: str, turn_index: int,
) -> Event:
    return Event.log(
        type="agent.note_created",
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Note: {note_type} at turn {turn_index}",
        data={"note_type": note_type, "turn_index": turn_index},
    )


def emit_mission_finished(
    session: AgentSession, status: str, reason: str,
) -> Event:
    return Event.log(
        type="agent.mission_finished",
        scan_run=session.scan_run,
        target=session.target,
        subject=session,
        message=f"Mission {status}: {reason}",
        data={"status": status, "reason": reason},
    )
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_event_log.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/events/types.py backend/apps/agent/event_log.py backend/apps/agent/tests/test_event_log.py
git commit -m "feat(agent): add agent event types and emission helpers"
```
