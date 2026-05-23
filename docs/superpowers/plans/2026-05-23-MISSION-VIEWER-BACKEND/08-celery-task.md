# Task 8: Celery Task — run_agent_session with Lifecycle

**Files:**
- Create: `backend/apps/agent/tasks.py`
- Create: `backend/apps/agent/tests/test_tasks.py`

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
    """Create a complete session hierarchy for task tests."""
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
            # Simulate controller finishing the session
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

Create `backend/apps/agent/tasks.py`:

```python
from __future__ import annotations

import asyncio
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.events.models import Event
from apps.events.types import EventType
from apps.scans.models import RunStatus

from .controller import MissionController
from .mission_profiles import get_profile
from .models import AgentSession, SessionStatus

logger = logging.getLogger(__name__)

_SESSION_TO_RUN_STATUS = {
    SessionStatus.COMPLETED: RunStatus.DONE,
    SessionStatus.STOPPED: RunStatus.STOPPED,
    SessionStatus.FAILED: RunStatus.FAILED,
}

_RUN_STATUS_TO_TR_EVENT = {
    RunStatus.DONE: EventType.SCAN_TARGET_RUN_DONE,
    RunStatus.STOPPED: EventType.SCAN_TARGET_RUN_STOPPED,
    RunStatus.FAILED: EventType.SCAN_TARGET_RUN_FAILED,
}

_RUN_STATUS_TO_SR_EVENT = {
    RunStatus.DONE: EventType.SCAN_RUN_DONE,
    RunStatus.STOPPED: EventType.SCAN_RUN_STOPPED_FINAL,
    RunStatus.FAILED: EventType.SCAN_RUN_FAILED,
}

_TERMINAL = (RunStatus.DONE, RunStatus.STOPPED, RunStatus.FAILED)


@shared_task(bind=True, max_retries=0)
def run_agent_session(self, session_id: str) -> None:
    _execute_agent_session(session_id)


def _execute_agent_session(session_id: str) -> None:
    session = AgentSession.objects.select_related(
        "scan_target_run", "scan_run", "target",
    ).get(id=session_id)
    target_run = session.scan_target_run
    scan_run = session.scan_run

    _start_target_run(target_run, scan_run)

    driver = None
    try:
        provider = _build_provider(session.model_policy)
        driver = _build_driver(session.target.host)

        profile = get_profile(session.mission_profile)
        ctrl = MissionController(
            session=session,
            provider=provider,
            driver=driver,
            objective=profile.objective,
            mission_budget=profile.mission_budget,
            phase_budgets=profile.phase_budgets,
            model_name=session.model_policy.get("model", "mock"),
        )
        asyncio.run(ctrl.run())
    except Exception:
        logger.exception("Agent session %s failed", session_id)
        session.refresh_from_db()
        if session.status not in (
            SessionStatus.COMPLETED, SessionStatus.STOPPED, SessionStatus.FAILED,
        ):
            from .persistence import finish_session
            finish_session(session, SessionStatus.FAILED, {})
        _finalize_target_run(target_run, scan_run, RunStatus.FAILED)
        raise
    else:
        session.refresh_from_db()
        run_status = _SESSION_TO_RUN_STATUS.get(
            session.status, RunStatus.DONE,
        )
        _finalize_target_run(target_run, scan_run, run_status)
    finally:
        if driver is not None:
            asyncio.run(driver.stop())


def _start_target_run(target_run, scan_run) -> None:
    with transaction.atomic():
        target_run.status = RunStatus.RUNNING
        target_run.started_at = timezone.now()
        target_run.save(update_fields=["status", "started_at", "updated_at"])
        Event.log(
            type=EventType.SCAN_TARGET_RUN_STARTED,
            scan_run=scan_run,
            target=target_run.target,
            subject=target_run,
            data={
                "id": str(target_run.id),
                "scan_run_id": str(scan_run.id),
                "target_id": str(target_run.target_id),
            },
        )


def _finalize_target_run(target_run, scan_run, run_status) -> None:
    target_run.refresh_from_db()
    if target_run.status in _TERMINAL:
        return

    with transaction.atomic():
        target_run.status = run_status
        target_run.finished_at = timezone.now()
        target_run.save(update_fields=["status", "finished_at", "updated_at"])
        tr_event = _RUN_STATUS_TO_TR_EVENT[run_status]
        Event.log(
            type=tr_event,
            scan_run=scan_run,
            target=target_run.target,
            subject=target_run,
            data={
                "id": str(target_run.id),
                "scan_run_id": str(scan_run.id),
                "finished_at": str(target_run.finished_at),
            },
        )

    scan_run.refresh_from_db()
    if scan_run.status in _TERMINAL:
        return

    with transaction.atomic():
        scan_run.status = run_status
        scan_run.finished_at = timezone.now()
        scan_run.save(update_fields=["status", "finished_at", "updated_at"])
        sr_event = _RUN_STATUS_TO_SR_EVENT[run_status]
        Event.log(
            type=sr_event,
            scan_run=scan_run,
            subject=scan_run,
            data={"id": str(scan_run.id)},
        )


def _build_provider(model_policy: dict):
    from .llm.providers import MockProvider
    provider_name = model_policy.get("provider", "mock")
    if provider_name == "mock":
        return MockProvider()
    if provider_name == "anthropic":
        from .llm.providers import AnthropicProvider
        return AnthropicProvider(model=model_policy.get("model", "claude-sonnet-4-5"))
    if provider_name == "openrouter":
        from .llm.providers import OpenRouterProvider
        return OpenRouterProvider(model=model_policy.get("model", ""))
    return MockProvider()


def _build_driver(host: str):
    from .browser.driver import PlaywrightDriver
    return PlaywrightDriver(target_origin=f"https://{host}")
```

- [ ] **Step 4: Run success tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestRunAgentSessionSuccess -v`
Expected: ALL PASS

- [ ] **Step 5: Write test for stopped path**

Add to `test_tasks.py`:

```python
@pytest.mark.django_db
class TestRunAgentSessionStopped:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_stopped_maps_to_stopped_status(self, mock_provider, mock_driver):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value
            ctrl_instance.run = AsyncMock()
            def side_effect():
                session.status = SessionStatus.STOPPED
                session.save(update_fields=["status"])
            ctrl_instance.run.side_effect = side_effect

            run_agent_session(str(session.id))

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.STOPPED
        assert scan_run.status == RunStatus.STOPPED
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STOPPED,
        ).exists()
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_STOPPED_FINAL,
        ).exists()
```

- [ ] **Step 6: Run stopped test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestRunAgentSessionStopped -v`
Expected: PASS

- [ ] **Step 7: Write test for failure path**

Add to `test_tasks.py`:

```python
@pytest.mark.django_db
class TestRunAgentSessionFailure:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_failure_marks_all_failed_and_stops_driver(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value
            ctrl_instance.run = AsyncMock(side_effect=RuntimeError("boom"))

            with pytest.raises(RuntimeError, match="boom"):
                run_agent_session(str(session.id))

        session.refresh_from_db()
        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert session.status == SessionStatus.FAILED
        assert target_run.status == RunStatus.FAILED
        assert scan_run.status == RunStatus.FAILED
        driver.stop.assert_awaited_once()
        assert Event.objects.filter(type=EventType.SCAN_RUN_FAILED).exists()
```

- [ ] **Step 8: Run failure test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestRunAgentSessionFailure -v`
Expected: PASS

- [ ] **Step 9: Write test for idempotent finalization**

Add to `test_tasks.py`:

```python
@pytest.mark.django_db
class TestIdempotentFinalization:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_does_not_overwrite_terminal_target_run(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        target_run.status = RunStatus.DONE
        target_run.save(update_fields=["status"])
        scan_run.status = RunStatus.DONE
        scan_run.save(update_fields=["status"])

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
        assert target_run.status == RunStatus.DONE
```

- [ ] **Step 10: Run idempotent test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestIdempotentFinalization -v`
Expected: PASS

- [ ] **Step 11: Run full task test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py -v`
Expected: ALL PASS

- [ ] **Step 12: Commit**

```bash
git add backend/apps/agent/tasks.py backend/apps/agent/tests/test_tasks.py
git commit -m "feat(agent): add Celery task with ScanRun/ScanTargetRun lifecycle"
```
