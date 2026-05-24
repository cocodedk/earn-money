"""Tests for MissionController warm-start wiring (target_intel integration)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone as dt_timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from apps.agent.controller import MissionController
from apps.agent.llm.providers import LLMResponse
from apps.agent.models import SessionStatus
from apps.agent.persistence import create_session
from apps.agent.target_intel import TargetIntel


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


def _ctrl(db_objects, responses, target_intel=None, budget=None):
    budget = budget or {"max_turns": 10}
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="controller", model_policy={}, mission_budget=budget,
    )
    return MissionController(
        session=session,
        provider=_mock_provider(responses),
        driver=_mock_driver(),
        objective="Test",
        mission_budget=budget,
        model_name="mock",
        target_intel=target_intel,
    )


def _make_intel(routes=None) -> TargetIntel:
    return TargetIntel(
        source_session_id="abc123",
        source_completed_at=datetime(2026, 5, 1, 12, 0, tzinfo=dt_timezone.utc),
        is_stale=False,
        known_routes=set(routes or ["/login", "/api/products"]),
    )


@pytest.fixture
def db_objects(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget

    project = Project.objects.create(name="warm-start-test")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return {"scan_run": scan_run, "target_run": target_run, "target": target}


@pytest.mark.django_db(transaction=True)
class TestWarmStart:
    def test_prior_intel_in_system_prompt(self, db_objects):
        """system_prompt includes Prior Target Intel section when intel is supplied."""
        intel = _make_intel(["/login", "/api/products"])
        ctrl = _ctrl(db_objects, [_action_json("stop")], target_intel=intel)
        prompt = ctrl.system_prompt
        assert "Prior Target Intel" in prompt
        assert "/login" in prompt
        assert "/api/products" in prompt

    def test_no_intel_means_no_section(self, db_objects):
        """system_prompt has no intel section when target_intel is None."""
        ctrl = _ctrl(db_objects, [_action_json("stop")], target_intel=None)
        prompt = ctrl.system_prompt
        assert "Prior Target Intel" not in prompt

    def test_advance_phase_preserves_known_routes(self, db_objects):
        """After advance_phase, the new PlateauDetector still has the known_routes baseline."""
        intel = _make_intel(["/login", "/api/products"])
        ctrl = _ctrl(db_objects, [_action_json("stop")], target_intel=intel)

        # Both routes are in the baseline — a turn with them is not "novel"
        ctrl.advance_phase("enumerate", "test")

        # Record a turn that only discovers a known route
        ctrl.plateau.record_turn(
            new_routes=1,
            new_elements=0,
            route_paths=["/login"],
        )
        # Should not reset the no-route counter because /login is in known_routes
        assert ctrl.plateau._turns_no_route == 1
