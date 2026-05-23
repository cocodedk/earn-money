---
tier: CAPABLE
depends_on: [14-persistence]
files:
  creates:
    - backend/apps/agent/event_log.py
    - backend/apps/agent/tests/test_event_log.py
  modifies:
    - backend/apps/events/types.py
allow_extra_files: false
---

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
