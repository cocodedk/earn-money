---
tier: APEX
depends_on: [16-controller-loop, 18-mission-profiles]
files:
  creates:
    - backend/apps/agent/tests/test_integration.py
  modifies: []
allow_extra_files: false
---

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
        {"action": "request_phase_transition", "goal": "Move to report",
         "args": {"from_phase": "enumerate", "to_phase": "report",
                  "reason": "Scoreboard page observed", "evidence_refs": ["obs_1"]}},
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
    driver = _scripted_driver()

    controller = MissionController(
        provider=_scripted_provider(),
        driver=driver,
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
    assert session.current_phase == "report"
    assert session.consumed_budget["turns"] == 7
    assert session.consumed_budget["asset_inspections"] == 1
    assert session.consumed_budget["http_requests"] >= 1

    # All turns persisted with artifact refs and tokens
    turns = AgentTurn.objects.filter(session=session).order_by("index")
    assert turns.count() == 7
    for turn in turns:
        assert turn.prompt_artifact_ref != ""
        assert turn.response_artifact_ref != ""
        assert turn.input_tokens > 0

    # Actions persisted
    actions = AgentAction.objects.filter(turn__session=session)
    assert actions.count() == 7

    # Observations persisted for observe_page, navigate, inspect_asset
    observations = AgentObservation.objects.filter(action__turn__session=session)
    assert observations.count() >= 3
    driver.fetch_asset.assert_awaited_with("/main.js")

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
    assert phase_events.count() >= 2
```

- [ ] **Step 2: Run test**

Run: `cd backend && python -m pytest apps/agent/tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/apps/agent/tests/test_integration.py
git commit -m "test(agent): add full scoreboard mission integration test"
```
