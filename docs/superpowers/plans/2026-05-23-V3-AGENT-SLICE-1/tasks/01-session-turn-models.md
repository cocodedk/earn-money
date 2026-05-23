---
tier: CAPABLE
depends_on: []
files:
  creates:
    - backend/apps/agent/__init__.py
    - backend/apps/agent/apps.py
    - backend/apps/agent/models.py
    - backend/apps/agent/tests/__init__.py
    - backend/apps/agent/tests/conftest.py
    - backend/apps/agent/tests/test_models.py
  modifies: []
allow_extra_files: false
---

### Task 1: AgentSession and AgentTurn models

**Files:**
- Create: `backend/apps/agent/__init__.py`
- Create: `backend/apps/agent/apps.py`
- Create: `backend/apps/agent/models.py`
- Create: `backend/apps/agent/tests/__init__.py`
- Create: `backend/apps/agent/tests/conftest.py`
- Create: `backend/apps/agent/tests/test_models.py`

**Prerequisite:** Create `conftest.py` with shared fixtures — see
[01-session-turn-models-conftest.md](01-session-turn-models-conftest.md).

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


See [01-session-turn-models-impl.md](01-session-turn-models-impl.md) for Step 3 implementation code.

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
