"""Edge-case tests for MissionController — plateau, errors, invalid transitions."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import SessionStatus
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


def _ctrl(db_objects, responses, budget=None):
    budget = budget or {"max_turns": 10}
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="controller", model_policy={}, mission_budget=budget,
    )
    return MissionController(
        session=session, provider=_mock_provider(responses),
        driver=_mock_driver(),
        objective="Test", mission_budget=budget, model_name="mock",
    )


@pytest.fixture
def db_objects(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget

    project = Project.objects.create(name="ctrl-edge")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return {"scan_run": scan_run, "target_run": target_run, "target": target}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_plateau_stops_at_terminal_phase(db_objects):
    """Plateau in report phase (no next phase) stops the mission."""
    c = _ctrl(db_objects, [_action_json("observe_page")] * 10)
    c.session.current_phase = "report"
    c.session.save(update_fields=["current_phase"])
    c.plateau._max_no_route = 1
    c.plateau._max_no_element = 1
    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.STOPPED


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_exception_in_loop_marks_failed(db_objects):
    provider = _mock_provider(["{}"])
    provider.complete = AsyncMock(side_effect=RuntimeError("boom"))
    c = _ctrl(db_objects, [])
    c.provider = provider
    with pytest.raises(RuntimeError, match="boom"):
        await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.FAILED


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_invalid_phase_transition_ignored(db_objects):
    """Backward transition (enumerate->recon) is silently ignored."""
    c = _ctrl(db_objects, [
        _action_json(
            "request_phase_transition", from_phase="recon",
            to_phase="enumerate", evidence_refs=[],
        ),
        _action_json(
            "request_phase_transition", from_phase="enumerate",
            to_phase="recon", evidence_refs=[],
        ),
        _action_json("stop"),
    ])
    await c.run()
    c.session.refresh_from_db()
    assert c.session.current_phase == "enumerate"


def test_next_slice_phase_recon():
    assert MissionController._next_slice_phase("recon") == "enumerate"


def test_next_slice_phase_report_terminal():
    assert MissionController._next_slice_phase("report") is None


def test_next_slice_phase_unknown():
    assert MissionController._next_slice_phase("probe") is None
