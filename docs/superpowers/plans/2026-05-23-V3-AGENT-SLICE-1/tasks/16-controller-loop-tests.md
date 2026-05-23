# Task 16 — Controller Tests

Part of [Task 16](16-controller-loop.md). Test code for Step 1.

```python
# backend/apps/agent/tests/test_controller.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import AgentSession, SessionStatus, AgentNote
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


def _mock_provider(responses: list[dict]) -> AsyncMock:
    provider = AsyncMock()
    call_count = 0

    async def complete(system_prompt, messages):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return LLMResponse(
            raw_text=json.dumps(responses[idx]),
            input_tokens=100, output_tokens=50, model="mock",
        )

    provider.complete = complete
    return provider


def _mock_driver() -> AsyncMock:
    driver = AsyncMock()
    driver.page = AsyncMock()
    driver.page.url = "https://juiceshop.cocode.dk/"
    driver.page.title = AsyncMock(return_value="Juice Shop")
    driver.page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea", "name": "Juice Shop", "children": [],
    })
    driver.page.context.cookies = AsyncMock(return_value=[])
    driver.drain_network_log = MagicMock(return_value=[])
    driver.navigate = AsyncMock(return_value="https://juiceshop.cocode.dk/")
    driver.fetch_asset = AsyncMock(return_value=("content", 100, False))
    driver.is_in_scope = MagicMock(return_value=True)
    driver.start = AsyncMock()
    driver.stop = AsyncMock()
    return driver


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_stop_action_ends_mission(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "observe_page", "goal": "See page", "args": {}},
        {"action": "stop", "goal": "Done", "args": {"reason": "nothing to do"}},
    ])
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 25},
        phase_budgets={
            "recon": {"max_turns": 6},
            "enumerate": {"max_turns": 14},
            "report": {"max_turns": 3},
        },
    )
    session = await controller.run()
    assert session.status == SessionStatus.COMPLETED


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_budget_exhaustion_stops(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "observe_page", "goal": "See", "args": {}},
    ] * 5)
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 3},
        phase_budgets={
            "recon": {"max_turns": 3},
            "enumerate": {"max_turns": 3},
            "report": {"max_turns": 1},
        },
    )
    session = await controller.run()
    assert session.status == SessionStatus.STOPPED


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_phase_transition(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "observe_page", "goal": "See", "args": {}},
        {"action": "request_phase_transition", "goal": "Move on",
         "args": {"from_phase": "recon", "to_phase": "enumerate",
                  "reason": "Baseline done", "evidence_refs": []}},
        {"action": "request_phase_transition", "goal": "Report",
         "args": {"from_phase": "enumerate", "to_phase": "report",
                  "reason": "Candidate found", "evidence_refs": []}},
        {"action": "stop", "goal": "Done",
         "args": {"reason": "finished"}},
    ])
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 25},
        phase_budgets={
            "recon": {"max_turns": 6},
            "enumerate": {"max_turns": 14},
            "report": {"max_turns": 3},
        },
    )
    session = await controller.run()
    assert session.current_phase == "report"
    assert session.status == SessionStatus.COMPLETED


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_controller_denied_action_persisted(scan_context):
    scan_run, target_run, target = scan_context
    provider = _mock_provider([
        {"action": "submit_candidate", "goal": "Report finding",
         "args": {"category": "xss", "description": "test",
                  "evidence_refs": []}},
        {"action": "stop", "goal": "Done",
         "args": {"reason": "gave up"}},
    ])
    driver = _mock_driver()
    controller = MissionController(
        provider=provider, driver=driver,
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test",
        mission_budget={"max_turns": 25},
        phase_budgets={
            "recon": {"max_turns": 6},
            "enumerate": {"max_turns": 14},
            "report": {"max_turns": 3},
        },
    )
    session = await controller.run()
    from apps.agent.models import AgentAction, ValidationStatus
    denied = AgentAction.objects.filter(
        validation_status=ValidationStatus.DENIED_PHASE,
    )
    assert denied.count() >= 1
```
