---
tier: APEX
depends_on: [01-event-type, 07-budget-persist]
files:
  creates:
    - backend/apps/agent/tests/test_tasks.py
  modifies: []
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 8A: Celery Task — Implementation

**Files:**
- Create: `backend/apps/agent/tasks.py`
- Create: `backend/apps/agent/tests/test_tasks.py`

**Prerequisites:**
- Task 1 must be complete so `EventType.SCAN_RUN_FAILED` exists.
- Confirm these event types already exist before writing `tasks.py`:
  `SCAN_TARGET_RUN_STARTED`, `SCAN_TARGET_RUN_DONE`,
  `SCAN_TARGET_RUN_STOPPED`, `SCAN_TARGET_RUN_FAILED`,
  `SCAN_RUN_DONE`, and `SCAN_RUN_STOPPED_FINAL`.
- If any are missing, extend Task 1 before continuing; do not invent aliases in `tasks.py`.

---

- [ ] **Step 1: Write test for success path lifecycle**

Create `backend/apps/agent/tests/test_tasks.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase

from apps.agent.models import AgentSession, SessionStatus
from apps.agent.tasks import run_agent_session
from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project
from apps.scans.models import RunStatus, ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


def _create_session_for_task():
    from apps.agent.models import AutonomyMode, AgentPhase
    project = Project.objects.create(name="test")
    target = ScanTarget.objects.create(
        host="juiceshop.cocode.dk", project=project,
        base_url="https://juiceshop.cocode.dk",
    )
    scan_run = ScanRun.objects.create(
        project=project, stub_slug="agent.v3", status=RunStatus.RUNNING,
    )
    target_run = ScanTargetRun.objects.create(
        scan_run=scan_run, target=target,
    )
    session = AgentSession.objects.create(
        scan_target_run=target_run, scan_run=scan_run, target=target,
        autonomy_mode=AutonomyMode.LAB_FREE_RUN,
        current_phase=AgentPhase.RECON,
        status=SessionStatus.RUNNING,
        mission_profile="juice_shop_scoreboard",
        model_policy={"provider": "mock", "model": "mock"},
        mission_budget={"max_turns": 5},
    )
    return session, target_run, scan_run


@pytest.mark.django_db
class TestRunAgentSessionSuccess:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_marks_target_run_started_then_done(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value
            ctrl_instance.run = AsyncMock()
            def side_effect():
                session.status = SessionStatus.COMPLETED
                session.save(update_fields=["status"])
            ctrl_instance.run.side_effect = side_effect

            run_agent_session(str(session.id))

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.DONE
        assert scan_run.status == RunStatus.DONE
        assert target_run.started_at is not None
        assert target_run.finished_at is not None

    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_emits_target_started_and_done_events(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value
            ctrl_instance.run = AsyncMock()
            def side_effect():
                session.status = SessionStatus.COMPLETED
                session.save(update_fields=["status"])
            ctrl_instance.run.side_effect = side_effect

            run_agent_session(str(session.id))

        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED,
        ).exists()
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_DONE,
        ).exists()
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_DONE,
        ).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestRunAgentSessionSuccess -v`
Expected: FAIL — `ImportError: No module named 'apps.agent.tasks'`

- [ ] **Step 3: Write run_agent_session task**

Create `backend/apps/agent/tasks.py` with full implementation. See
[08-celery-task-code.md](08-celery-task-code.md) for the complete file.

- [ ] **Step 4: Run success tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestRunAgentSessionSuccess -v`
Expected: ALL PASS

Continues in [08-celery-task-edge-cases.md](08-celery-task-edge-cases.md).
