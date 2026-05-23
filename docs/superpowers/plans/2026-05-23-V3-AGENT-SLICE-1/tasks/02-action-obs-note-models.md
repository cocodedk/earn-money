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
