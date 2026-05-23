"""Tests for MissionController — the core agent loop."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import AgentAction, AgentNote, SessionStatus, ValidationStatus
from apps.agent.persistence import create_session


def _action_json(action: str, **extra) -> str:
    base = {"action": action, "goal": "g", "reason": "r", "hypothesis": "h"}
    base.update(extra)
    return json.dumps(base)


def _mock_provider(responses: list[str]):
    p = AsyncMock()
    p.complete = AsyncMock(side_effect=[
        LLMResponse(raw_text=r, input_tokens=10, output_tokens=10, model="mock")
        for r in responses
    ])
    return p


def _mock_driver():
    d = AsyncMock()
    page = MagicMock()
    page.url = "https://test.example.com/"
    page.title = AsyncMock(return_value="Test")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value={"children": []})
    page.context = MagicMock()
    page.context.cookies = AsyncMock(return_value=[])
    type(d).page = PropertyMock(return_value=page)
    d.navigate = AsyncMock()
    d.drain_network_log = MagicMock(return_value=[])
    return d


def _ctrl(db_objects, responses, driver=None, budget=None):
    budget = budget or {"max_turns": 10}
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="controller", model_policy={}, mission_budget=budget,
    )
    return MissionController(
        session=session, provider=_mock_provider(responses),
        driver=driver or _mock_driver(),
        objective="Test", mission_budget=budget, model_name="mock",
    )


@pytest.fixture
def db_objects(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget

    project = Project.objects.create(name="ctrl-test")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return {"scan_run": scan_run, "target_run": target_run, "target": target}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_stop_action_ends_mission(db_objects):
    c = _ctrl(db_objects, [_action_json("observe_page"), _action_json("stop")])
    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.COMPLETED


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_budget_exhaustion_stops(db_objects):
    c = _ctrl(
        db_objects, [_action_json("observe_page")] * 5, budget={"max_turns": 3},
    )
    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.STOPPED


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_phase_transition(db_objects):
    c = _ctrl(db_objects, [
        _action_json(
            "request_phase_transition", from_phase="recon",
            to_phase="enumerate", evidence_refs=[],
        ),
        _action_json("stop"),
    ])
    await c.run()
    c.session.refresh_from_db()
    assert c.session.current_phase == "enumerate"
    assert c.session.status == SessionStatus.COMPLETED


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_denied_action_persisted(db_objects):
    c = _ctrl(db_objects, [
        _action_json("submit_candidate", category="xss", description="t", evidence_refs=[]),
        _action_json("stop"),
    ])
    await c.run()
    denied = AgentAction.objects.filter(validation_status=ValidationStatus.DENIED_PHASE)
    assert denied.exists()
    assert denied.first().action_type == "submit_candidate"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_invalid_json_recovers(db_objects):
    c = _ctrl(db_objects, ["not json", _action_json("stop")])
    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.COMPLETED
    assert AgentAction.objects.filter(
        validation_status=ValidationStatus.INVALID_SCHEMA,
    ).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_navigate_calls_driver(db_objects):
    driver = _mock_driver()
    c = _ctrl(
        db_objects,
        [_action_json("navigate", path="/login"), _action_json("stop")],
        driver,
    )
    await c.run()
    driver.navigate.assert_awaited_once_with("/login")


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_store_note_persists(db_objects):
    c = _ctrl(db_objects, [
        _action_json("store_note", note_type="hypothesis", content={"t": 1}),
        _action_json("stop"),
    ])
    await c.run()
    assert AgentNote.objects.filter(session=c.session).exists()


@pytest.mark.django_db(transaction=True)
class TestConsumedBudgetPersistence:
    """consumed_budget must be written to DB after every turn path."""

    @pytest.mark.asyncio
    async def test_budget_persisted_after_executed_turn(self, db_objects):
        """Provider returns a stop action so the controller finishes after one turn."""
        session_obj = _ctrl(
            db_objects,
            responses=[_action_json(action="stop", reason="done")],
            budget={"max_turns": 10},
        )
        await session_obj.run()
        session_obj.session.refresh_from_db()
        assert session_obj.session.consumed_budget["mission"]["turns"] >= 1
