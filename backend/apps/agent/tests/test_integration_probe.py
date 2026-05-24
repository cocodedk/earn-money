"""Integration test: full probe flow (recon → enumerate → probe → report)."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import AgentObservation, SessionStatus
from apps.agent.persistence import create_session


# ---------------------------------------------------------------------------
# Helpers (mirror test_controller.py conventions)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db_objects(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget

    project = Project.objects.create(name="probe-integration-test")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return {"scan_run": scan_run, "target_run": target_run, "target": target}


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestProbeMissionFlow:
    """End-to-end: recon → enumerate → probe → report with click + http_request."""

    @pytest.mark.asyncio
    async def test_scoreboard_with_probe(self, db_objects):
        """Agent discovers scoreboard, probes it, submits candidate with evidence."""
        responses = [
            # recon: observe page
            _action_json(action="observe_page"),
            # recon → enumerate transition
            _action_json(
                action="request_phase_transition",
                from_phase="recon", to_phase="enumerate",
                reason="found JS bundles", evidence_refs=[],
            ),
            # enumerate: navigate to scoreboard
            _action_json(action="navigate", path="/#!/score-board"),
            # enumerate → probe transition
            _action_json(
                action="request_phase_transition",
                from_phase="enumerate", to_phase="probe",
                reason="found scoreboard", evidence_refs=[],
            ),
            # probe: click an element
            _action_json(action="click", element_id="link_0"),
            # probe: http_request
            _action_json(
                action="http_request", method="GET",
                path="/api/Challenges",
            ),
            # probe: submit candidate with evidence
            _action_json(
                action="submit_candidate",
                category="hidden_route_discovered",
                description="Scoreboard accessible without auth",
                evidence_refs=["obs_1", "obs_2"],
            ),
            # probe → report
            _action_json(
                action="request_phase_transition",
                from_phase="probe", to_phase="report",
                reason="evidence collected", evidence_refs=[],
            ),
            # report: stop
            _action_json(action="stop", reason="mission complete"),
        ]

        ctrl = _ctrl(
            db_objects, responses=responses,
            budget={"max_turns": 20},
        )
        ctrl._mission_phases = ["recon", "enumerate", "probe", "report"]
        ctrl.driver.click = AsyncMock()
        ctrl.driver.http_request = AsyncMock(return_value={
            "url": "https://test.example.com/api/Challenges",
            "method": "GET", "status": 200,
            "content_type": "application/json",
            "redirected": False,
            "final_url": "https://test.example.com/api/Challenges",
            "body_excerpt": '{"data": []}',
            "body_truncated": False,
            "trust": "untrusted_target_content",
        })

        await ctrl.run()

        ctrl.session.refresh_from_db()
        assert ctrl.session.status == "completed"

        http_obs = AgentObservation.objects.filter(
            observation_type="http",
        ).count()
        assert http_obs >= 1

        ctrl.driver.click.assert_awaited_once()
        ctrl.driver.http_request.assert_awaited_once_with(
            "GET", "/api/Challenges",
        )
