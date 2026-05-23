"""Full end-to-end integration test: scoreboard-finding mission."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import (
    AgentAction, AgentNote, AgentObservation, AgentTurn, SessionStatus,
)
from apps.agent.persistence import create_session
from apps.events.models import Event
from apps.events.types import EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _j(action: str, **kw) -> str:
    base = {"action": action, "goal": "g", "reason": "r", "hypothesis": "h"}
    base.update(kw)
    return json.dumps(base)


_SCRIPT_RESPONSES = [
    _j("observe_page"),
    _j("inspect_asset", asset_ref="asset-1"),
    _j(
        "request_phase_transition",
        from_phase="recon", to_phase="enumerate",
        evidence_refs=[], reason="recon done",
    ),
    _j("navigate", path="/#/score-board"),
    _j(
        "submit_candidate",
        category="hidden_route_discovered",
        description="Score-board route found via JS analysis",
        evidence_refs=["asset-1"],
    ),
    _j("stop", reason="Scoreboard found"),
]


def _scripted_provider():
    p = AsyncMock()
    p.complete = AsyncMock(side_effect=[
        LLMResponse(raw_text=r, input_tokens=5, output_tokens=5, model="mock")
        for r in _SCRIPT_RESPONSES
    ])
    return p


def _scripted_driver():
    d = AsyncMock()
    page = MagicMock()
    page.url = "https://juiceshop.cocode.dk/"
    page.title = AsyncMock(return_value="OWASP Juice Shop")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value={
        "children": [
            {"role": "link", "name": "Home", "url": "/"},
            {"role": "button", "name": "Account"},
        ],
    })
    page.context = MagicMock()
    page.context.cookies = AsyncMock(return_value=[])
    type(d).page = PropertyMock(return_value=page)
    d.navigate = AsyncMock()
    d.drain_network_log = MagicMock(return_value=[
        {"url": "https://juiceshop.cocode.dk/main.js", "resource_type": "script"},
    ])
    d.fetch_asset = AsyncMock(
        return_value='routerModule.forRoot([{path:"/#/score-board"}])',
    )
    return d


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db_objects(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget

    project = Project.objects.create(name="integration-test")
    target = ScanTarget.objects.create(
        host="juiceshop.cocode.dk", project=project,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return {"scan_run": scan_run, "target_run": target_run, "target": target}


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_scoreboard_mission_end_to_end(db_objects):
    """Full scoreboard-finding mission: 6 turns, phase change, candidate."""
    budget = {"max_turns": 10}
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="scoreboard_hunt",
        model_policy={},
        mission_budget=budget,
    )

    ctrl = MissionController(
        session=session,
        provider=_scripted_provider(),
        driver=_scripted_driver(),
        objective="Find the hidden score-board route on Juice Shop.",
        mission_budget=budget,
        model_name="mock",
    )

    await ctrl.run()

    # -- Session finalised ------------------------------------------------
    session.refresh_from_db()
    assert session.status == SessionStatus.COMPLETED
    assert session.finished_at is not None

    # -- 6 turns persisted -------------------------------------------------
    turns = list(AgentTurn.objects.filter(session=session).order_by("index"))
    assert len(turns) == 6
    for turn in turns:
        assert turn.input_tokens == 5
        assert turn.output_tokens == 5

    # -- 6 actions persisted -----------------------------------------------
    actions = list(AgentAction.objects.filter(turn__session=session).order_by("turn__index"))
    assert len(actions) == 6
    action_types = [a.action_type for a in actions]
    assert action_types == [
        "observe_page", "inspect_asset", "request_phase_transition",
        "navigate", "submit_candidate", "stop",
    ]

    # -- Observations for browser actions ----------------------------------
    obs_actions = AgentObservation.objects.filter(action__turn__session=session)
    # observe_page, inspect_asset, navigate, submit_candidate all produce observations
    assert obs_actions.count() == 4

    # -- submit_candidate action recorded ----------------------------------
    candidate = AgentAction.objects.get(
        turn__session=session, action_type="submit_candidate",
    )
    assert candidate is not None  # action persisted

    # -- Phase changed to enumerate ----------------------------------------
    session.refresh_from_db()
    assert session.current_phase == "enumerate"

    # -- Events emitted ----------------------------------------------------
    session_events = Event.objects.filter(
        scan_run=db_objects["scan_run"],
    )
    event_types = set(session_events.values_list("type", flat=True))

    assert EventType.AGENT_ACTION_EXECUTED in event_types
    assert EventType.AGENT_PHASE_CHANGED in event_types
    assert EventType.AGENT_MISSION_FINISHED in event_types

    finished_evt = session_events.get(type=EventType.AGENT_MISSION_FINISHED)
    assert finished_evt.data["status"] == SessionStatus.COMPLETED
    assert finished_evt.data["reason"] == "stop_action"
