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


See [14-persistence-impl.md](14-persistence-impl.md) for Step 3 implementation code.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_persistence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/persistence.py backend/apps/agent/tests/test_persistence.py
git commit -m "feat(agent): add persistence layer for agent models"
```
