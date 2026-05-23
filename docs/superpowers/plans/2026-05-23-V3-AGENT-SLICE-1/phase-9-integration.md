# Phase 9 — Integration & Live Run

### Task 19: Integration test (mocked LLM, real DB)

**Files:**
- Create: `backend/apps/agent/tests/test_integration.py`

This test runs the full controller loop with a mock LLM that follows the
scoreboard-finding script and a mock browser. It verifies the complete
persistence spine end-to-end.

- [ ] **Step 1: Write integration test**

```python
# backend/apps/agent/tests/test_integration.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import (
    AgentSession, AgentTurn, AgentAction, AgentObservation, AgentNote,
    SessionStatus, TurnStatus, ValidationStatus,
)
from apps.events.models import Event
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project


def _scripted_provider() -> AsyncMock:
    """LLM that follows the scoreboard-finding script."""
    script = [
        {"action": "observe_page", "goal": "Initial page scan", "args": {}},
        {"action": "inspect_asset", "goal": "Check JS for routes",
         "args": {"asset_ref": "asset_0"}},
        {"action": "request_phase_transition", "goal": "Move to enumerate",
         "args": {"from_phase": "recon", "to_phase": "enumerate",
                  "reason": "Found JS bundle with routes", "evidence_refs": ["obs_0"]}},
        {"action": "navigate", "goal": "Go to scoreboard",
         "args": {"path": "/#/score-board"}},
        {"action": "submit_candidate", "goal": "Report finding",
         "args": {"category": "hidden_route_discovered",
                  "description": "Found scoreboard at /#/score-board",
                  "evidence_refs": ["obs_0", "obs_1"]}},
        {"action": "stop", "goal": "Mission complete",
         "args": {"reason": "Scoreboard found and reported"}},
    ]
    call_count = 0

    async def complete(system_prompt, messages):
        nonlocal call_count
        idx = min(call_count, len(script) - 1)
        call_count += 1
        return LLMResponse(
            raw_text=json.dumps(script[idx]),
            input_tokens=500, output_tokens=100, model="mock",
        )

    provider = AsyncMock()
    provider.complete = complete
    return provider


def _scripted_driver() -> AsyncMock:
    driver = AsyncMock()
    driver.page = AsyncMock()
    driver.page.url = "https://juiceshop.cocode.dk/"
    driver.page.title = AsyncMock(return_value="OWASP Juice Shop")
    driver.page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea", "name": "OWASP Juice Shop",
        "children": [
            {"role": "link", "name": "About Us", "url": "/about"},
            {"role": "button", "name": "Account", "disabled": False},
        ],
    })
    driver.page.context.cookies = AsyncMock(return_value=[
        {"name": "language", "domain": "juiceshop.cocode.dk",
         "path": "/", "secure": True, "httpOnly": False,
         "sameSite": "Lax", "value": "en"},
    ])
    driver.page.evaluate = AsyncMock(return_value=[])
    driver.drain_network_log = MagicMock(return_value=[
        {"url": "https://juiceshop.cocode.dk/main.js", "method": "GET",
         "status": 200, "resource_type": "script",
         "content_type": "application/javascript"},
    ])
    driver.navigate = AsyncMock(return_value="https://juiceshop.cocode.dk/#/score-board")
    driver.fetch_asset = AsyncMock(return_value=(
        "angular.module('juiceShop').config(function($routeProvider){"
        "$routeProvider.when('/score-board',{templateUrl:'views/ScoreBoard.html'});"
        "$routeProvider.when('/administration',{templateUrl:'views/Administration.html'});"
        "})",
        2048, False,
    ))
    driver.is_in_scope = MagicMock(return_value=True)
    driver.start = AsyncMock()
    driver.stop = AsyncMock()
    return driver


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_full_scoreboard_mission():
    project = Project.objects.create(name="integration-test")
    target = ScanTarget.objects.create(host="juiceshop.cocode.dk", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)

    controller = MissionController(
        provider=_scripted_provider(),
        driver=_scripted_driver(),
        scan_run=scan_run,
        target_run=target_run,
        target=target,
        mission_profile="juice_shop_scoreboard",
        mission_budget={"max_turns": 25, "max_http_requests": 60, "max_asset_inspections": 10},
        phase_budgets={
            "recon": {"max_turns": 6, "max_http_requests": 20, "max_asset_inspections": 5},
            "enumerate": {"max_turns": 14, "max_http_requests": 35, "max_asset_inspections": 5},
            "report": {"max_turns": 3, "max_http_requests": 0, "max_asset_inspections": 0},
        },
    )
    session = await controller.run()

    # Session completed successfully
    assert session.status == SessionStatus.COMPLETED
    assert session.finished_at is not None

    # All turns persisted with artifact refs and tokens
    turns = AgentTurn.objects.filter(session=session).order_by("index")
    assert turns.count() == 6
    for turn in turns:
        assert turn.prompt_artifact_ref != ""
        assert turn.response_artifact_ref != ""
        assert turn.input_tokens > 0

    # Actions persisted
    actions = AgentAction.objects.filter(turn__session=session)
    assert actions.count() == 6

    # Observations persisted for observe_page, navigate, inspect_asset
    observations = AgentObservation.objects.filter(action__turn__session=session)
    assert observations.count() >= 3

    # Candidate note persisted
    candidates = AgentNote.objects.filter(session=session, note_type="candidate")
    assert candidates.count() == 1
    assert candidates[0].content["category"] == "hidden_route_discovered"

    # Events emitted
    events = Event.objects.filter(scan_run=scan_run)
    event_types = set(events.values_list("type", flat=True))
    assert "agent.session_started" in event_types
    assert "agent.action_executed" in event_types
    assert "agent.phase_changed" in event_types
    assert "agent.note_created" in event_types
    assert "agent.mission_finished" in event_types

    # Phase transitions happened
    phase_events = events.filter(type="agent.phase_changed")
    assert phase_events.count() >= 1
```

- [ ] **Step 2: Run test**

Run: `cd backend && python -m pytest apps/agent/tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/apps/agent/tests/test_integration.py
git commit -m "test(agent): add full scoreboard mission integration test"
```

### Task 20: Live Juice Shop run (manual verification)

**Files:** No new files — this is a manual verification step.

This task runs the agent against the real Juice Shop at
`juiceshop.cocode.dk`. It requires a real LLM API key and Playwright
installed. Run only after all unit/integration tests pass.

- [ ] **Step 1: Create a runner script**

```python
# backend/live_test_agent.py
"""One-shot live test: run the V3 agent against Juice Shop.

Usage:
    ANTHROPIC_API_KEY=sk-... python live_test_agent.py
"""
import asyncio
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.agent.controller import MissionController
from apps.agent.llm.providers import create_provider
from apps.agent.browser.driver import PlaywrightDriver
from apps.agent.mission_profiles import get_profile
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project


async def main():
    profile = get_profile("juice_shop_scoreboard")
    project, _ = Project.objects.get_or_create(name="v3-live-test")
    target, _ = ScanTarget.objects.get_or_create(
        host=profile.target, project=project,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)

    provider = create_provider(
        model="claude-sonnet-4-6",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        provider_type="anthropic",
    )
    driver = PlaywrightDriver()
    await driver.start(f"https://{profile.target}")

    try:
        controller = MissionController(
            provider=provider, driver=driver,
            scan_run=scan_run, target_run=target_run, target=target,
            mission_profile=profile.name,
            mission_budget=profile.mission_budget,
            phase_budgets=profile.phase_budgets,
            objective=profile.objective,
        )
        session = await controller.run()
        print(f"Mission finished: {session.status}")
        print(f"Phase: {session.current_phase}")
        print(f"Consumed: {session.consumed_budget}")

        from apps.agent.models import AgentNote
        candidates = AgentNote.objects.filter(session=session, note_type="candidate")
        for c in candidates:
            print(f"Candidate: {c.content}")
    finally:
        await driver.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run against live Juice Shop**

Run: `cd backend && ANTHROPIC_API_KEY=sk-... python live_test_agent.py`

Expected: Agent discovers `/score-board` or `/#/score-board` route, submits a
candidate with category `hidden_route_discovered`, and completes within budget.

- [ ] **Step 3: Verify acceptance criteria**

Check that:
1. Agent observed the page and discovered JS assets
2. Agent inspected a JS bundle and found a route containing "score-board"
3. Agent navigated to the scoreboard view
4. A candidate note with `hidden_route_discovered` was persisted
5. All turns have artifact refs and token counts
6. Mission completed within budget

- [ ] **Step 4: Commit runner script**

```bash
git add backend/live_test_agent.py
git commit -m "test(agent): add live Juice Shop runner script"
```
