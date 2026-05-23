# Phase 1 — Django Models

### Task 1: AgentSession and AgentTurn models

**Files:**
- Create: `backend/apps/agent/__init__.py`
- Create: `backend/apps/agent/apps.py`
- Create: `backend/apps/agent/models.py`
- Create: `backend/apps/agent/tests/__init__.py`
- Create: `backend/apps/agent/tests/test_models.py`

- [ ] **Step 1: Write test for AgentSession creation**

```python
# backend/apps/agent/tests/test_models.py
import pytest
from apps.agent.models import AgentSession, AutonomyMode, AgentPhase, SessionStatus
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project

@pytest.mark.django_db
def test_agent_session_creation():
    project = Project.objects.create(name="test")
    target = ScanTarget.objects.create(host="juiceshop.cocode.dk", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)

    session = AgentSession.objects.create(
        scan_target_run=target_run,
        scan_run=scan_run,
        target=target,
        autonomy_mode=AutonomyMode.LAB_FREE_RUN,
        current_phase=AgentPhase.RECON,
        status=SessionStatus.PENDING,
        mission_profile="juice_shop_scoreboard",
        model_policy={"primary_model": "claude-sonnet-4-6"},
        roe_snapshot={},
        mission_budget={"max_turns": 25},
        consumed_budget={"turns": 0},
        progress_counters={"routes": 0},
    )
    assert session.pk is not None
    assert session.scan_target_run == target_run
    assert session.autonomy_mode == AutonomyMode.LAB_FREE_RUN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest apps/agent/tests/test_models.py::test_agent_session_creation -v`
Expected: FAIL — module not found

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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest apps/agent/tests/test_models.py::test_agent_session_creation -v`
Expected: PASS

- [ ] **Step 5: Write test for AgentTurn with unique_together constraint**

```python
# append to backend/apps/agent/tests/test_models.py
from apps.agent.models import AgentTurn, TurnStatus

@pytest.mark.django_db
def test_agent_turn_unique_index(create_session):
    session = create_session()
    AgentTurn.objects.create(
        session=session, index=0, phase="recon",
        model="claude-sonnet-4-6", prompt_artifact_ref="ref_0",
        response_artifact_ref="ref_1", prompt_hash="h0",
        response_hash="h1", input_tokens=100, output_tokens=50,
        status=TurnStatus.COMPLETED,
    )
    with pytest.raises(Exception):
        AgentTurn.objects.create(
            session=session, index=0, phase="recon",
            model="claude-sonnet-4-6", prompt_artifact_ref="ref_2",
            response_artifact_ref="ref_3", prompt_hash="h2",
            response_hash="h3", input_tokens=100, output_tokens=50,
            status=TurnStatus.COMPLETED,
        )
```

- [ ] **Step 6: Write AgentTurn model**

Add to `backend/apps/agent/models.py`:

```python
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
                fields=("session", "index"),
                name="uniq_turn_index_per_session",
            )
        ]
        ordering = ("session", "index")
```

- [ ] **Step 7: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_models.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/apps/agent/
git commit -m "feat(agent): add AgentSession and AgentTurn models"
```

### Task 2: AgentAction, AgentObservation, AgentNote models

**Files:**
- Modify: `backend/apps/agent/models.py`
- Modify: `backend/apps/agent/tests/test_models.py`

- [ ] **Step 1: Write tests for remaining models**

```python
# append to backend/apps/agent/tests/test_models.py
from apps.agent.models import (
    AgentAction, ValidationStatus, ExecutionStatus,
    AgentObservation, ObservationType,
    AgentNote, NoteType,
)

@pytest.mark.django_db
def test_agent_action_creation(create_turn):
    turn = create_turn()
    action = AgentAction.objects.create(
        turn=turn, action_type="observe_page",
        args_redacted={}, goal="See the page",
        validation_status=ValidationStatus.VALID,
        execution_status=ExecutionStatus.EXECUTED,
    )
    assert action.turn == turn
    assert action.action_type == "observe_page"


@pytest.mark.django_db
def test_agent_observation_creation(create_action):
    action = create_action()
    obs = AgentObservation.objects.create(
        action=action, observation_type=ObservationType.PAGE,
        data={"page": {"path": "/"}}, content_hash="abc123",
    )
    assert obs.observation_type == ObservationType.PAGE


@pytest.mark.django_db
def test_agent_note_creation(create_session, create_turn):
    session = create_session()
    turn = create_turn(session=session)
    note = AgentNote.objects.create(
        session=session, turn=turn, note_type=NoteType.HYPOTHESIS,
        content={"text": "This looks interesting"},
    )
    assert note.note_type == NoteType.HYPOTHESIS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_models.py -v`
Expected: FAIL — classes not defined

- [ ] **Step 3: Write remaining models**

Add to `backend/apps/agent/models.py`:

```python
class ValidationStatus(models.TextChoices):
    VALID = "valid", "Valid"
    INVALID_SCHEMA = "invalid_schema", "Invalid schema"
    DENIED_PHASE = "denied_phase", "Denied by phase"
    DENIED_ROE = "denied_roe", "Denied by RoE"
    DENIED_BUDGET = "denied_budget", "Denied by budget"
    DENIED_SCOPE = "denied_scope", "Denied by scope"


class ExecutionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SKIPPED = "skipped", "Skipped"
    EXECUTED = "executed", "Executed"
    FAILED = "failed", "Failed"


class AgentAction(TimestampedUUIDModel):
    turn = models.ForeignKey(
        AgentTurn, on_delete=models.CASCADE, related_name="actions",
    )
    action_type = models.CharField(max_length=32)
    args_redacted = models.JSONField(default=dict)
    goal = models.TextField(blank=True, default="")
    reason = models.TextField(blank=True, default="")
    hypothesis = models.TextField(blank=True, default="")
    validation_status = models.CharField(
        max_length=20, choices=ValidationStatus.choices,
    )
    execution_status = models.CharField(
        max_length=16, choices=ExecutionStatus.choices,
        default=ExecutionStatus.PENDING,
    )
    denial_reason = models.TextField(blank=True, default="")
    executed_at = models.DateTimeField(null=True, blank=True)


class ObservationType(models.TextChoices):
    PAGE = "page", "Page"
    HTTP = "http", "HTTP"
    STUB = "stub", "Stub"
    TOOL = "tool", "Tool"
    ASSET = "asset", "Asset"


class AgentObservation(TimestampedUUIDModel):
    action = models.ForeignKey(
        AgentAction, on_delete=models.CASCADE, related_name="observations",
    )
    observation_type = models.CharField(
        max_length=8, choices=ObservationType.choices,
    )
    data = models.JSONField(default=dict)
    artifact_refs = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    redactions = models.JSONField(default=list, blank=True)
    is_delta = models.BooleanField(default=False)


class NoteType(models.TextChoices):
    HYPOTHESIS = "hypothesis", "Hypothesis"
    GAP = "gap", "Gap"
    CREDENTIAL_LABEL = "credential_label", "Credential label"
    ROUTE = "route", "Route"
    PARAMETER = "parameter", "Parameter"
    CANDIDATE = "candidate", "Candidate"


class AgentNote(TimestampedUUIDModel):
    session = models.ForeignKey(
        AgentSession, on_delete=models.CASCADE, related_name="notes",
    )
    turn = models.ForeignKey(
        AgentTurn, on_delete=models.CASCADE, related_name="notes",
    )
    note_type = models.CharField(max_length=20, choices=NoteType.choices)
    content = models.JSONField(default=dict)
    evidence_refs = models.JSONField(default=list, blank=True)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/models.py backend/apps/agent/tests/test_models.py
git commit -m "feat(agent): add AgentAction, AgentObservation, AgentNote models"
```

### Task 3: Migrations and app registration

**Files:**
- Modify: `backend/config/settings.py`
- Create: `backend/apps/agent/migrations/` (generated)

- [ ] **Step 1: Add app to INSTALLED_APPS**

In `backend/config/settings.py`, add `"apps.agent"` after `"apps.stubs"`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    "apps.stubs",
    "apps.agent",
]
```

- [ ] **Step 2: Generate and run migrations**

Run: `cd backend && python manage.py makemigrations agent && python manage.py migrate`
Expected: Migration created and applied successfully

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest apps/agent/tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/config/settings.py backend/apps/agent/migrations/
git commit -m "feat(agent): register app and generate initial migration"
```
