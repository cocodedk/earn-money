---
tier: APEX
depends_on: [08-celery-task-impl]
files:
  creates:
    - backend/apps/agent/tasks.py
  modifies: []
  deletes: []
  renames: []
  generated: []
exports:
  - name: run_agent_session
    file: backend/apps/agent/tasks.py
imports:
  - module: "apps.agent.controller.MissionController"
    file: backend/apps/agent/tasks.py
  - module: "apps.agent.mission_profiles.get_profile"
    file: backend/apps/agent/tasks.py
allow_extra_files: false
---

# Task 8B: Celery Task — Full Implementation Code

Referenced by [08-celery-task-impl.md](08-celery-task-impl.md) Step 3.

**Files:**
- Create: `backend/apps/agent/tasks.py`

---

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
_SESSION_TERMINAL = (
    SessionStatus.COMPLETED, SessionStatus.STOPPED, SessionStatus.FAILED,
)


@shared_task(bind=True, max_retries=0)
def run_agent_session(self, session_id: str) -> None:
    _execute_agent_session(session_id)


def _execute_agent_session(session_id: str) -> None:
    session = AgentSession.objects.select_related(
        "scan_target_run", "scan_run", "target",
    ).get(id=session_id)
    target_run = session.scan_target_run
    scan_run = session.scan_run
    if target_run.status in _TERMINAL:
        _finalize_target_run(target_run, scan_run, target_run.status)
        return
    if session.status in _SESSION_TERMINAL:
        run_status = _SESSION_TO_RUN_STATUS.get(session.status, RunStatus.DONE)
        _finalize_target_run(target_run, scan_run, run_status)
        return

    _start_target_run(target_run, scan_run)

    driver = None
    try:
        provider = _build_provider(session.model_policy)
        driver = _build_driver(session.target)

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
            SessionStatus.COMPLETED,
            SessionStatus.STOPPED,
            SessionStatus.FAILED,
        ):
            from .persistence import finish_session
            consumed = session.consumed_budget or {}
            finish_session(session, SessionStatus.FAILED, consumed)
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
    target_run.refresh_from_db()
    if target_run.status in _TERMINAL:
        return
    with transaction.atomic():
        target_run.status = RunStatus.RUNNING
        target_run.started_at = timezone.now()
        target_run.save(
            update_fields=["status", "started_at", "updated_at"],
        )
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
    if target_run.status not in _TERMINAL:
        with transaction.atomic():
            target_run.status = run_status
            target_run.finished_at = timezone.now()
            target_run.save(
                update_fields=["status", "finished_at", "updated_at"],
            )
            Event.log(
                type=_RUN_STATUS_TO_TR_EVENT[run_status],
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
        scan_run.save(
            update_fields=["status", "finished_at", "updated_at"],
        )
        Event.log(
            type=_RUN_STATUS_TO_SR_EVENT[run_status],
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
        return AnthropicProvider(
            model=model_policy.get("model", "claude-sonnet-4-5"),
        )
    if provider_name == "openrouter":
        from .llm.providers import OpenRouterProvider
        return OpenRouterProvider(
            model=model_policy.get("model", ""),
        )
    return MockProvider()


def _build_driver(target):
    from .browser.driver import PlaywrightDriver
    target_origin = target.base_url or f"https://{target.host}"
    return PlaywrightDriver(target_origin=target_origin)
```
