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
async def test_invalid_json_recovers_after_retries(db_objects):
    c = _ctrl(db_objects, [
        "not json", "not json", "not json",  # 1 attempt + 2 retries exhausted
        _action_json("stop"),
    ])
    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.COMPLETED
    assert AgentAction.objects.filter(
        validation_status=ValidationStatus.INVALID_SCHEMA,
    ).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(db_objects):
    c = _ctrl(db_objects, [
        "{}",  # empty object → retry
        _action_json("stop"),  # valid on retry
    ])
    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.COMPLETED
    assert not AgentAction.objects.filter(
        validation_status=ValidationStatus.INVALID_SCHEMA,
    ).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_retry_succeeds_on_third_attempt(db_objects):
    c = _ctrl(db_objects, [
        '{"action": "http_request"}',  # missing fields → retry
        "{}",  # empty → retry
        _action_json("stop"),  # valid on 3rd attempt
    ])
    await c.run()
    c.session.refresh_from_db()
    assert c.session.status == SessionStatus.COMPLETED
    assert not AgentAction.objects.filter(
        validation_status=ValidationStatus.INVALID_SCHEMA,
    ).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_retry_tokens_accumulate(db_objects):
    c = _ctrl(db_objects, [
        "{}",  # retry 1
        _action_json("stop"),  # success
    ])
    await c.run()
    from apps.agent.models import AgentTurn
    turn = AgentTurn.objects.filter(session=c.session).first()
    assert turn.input_tokens == 20  # 10 per call × 2 calls


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

    @pytest.mark.asyncio
    async def test_budget_persisted_after_denied_turn(self, db_objects):
        """Denied action path also persists consumed_budget via finally."""
        session_obj = _ctrl(db_objects, responses=[
            _action_json("submit_candidate", category="xss", description="t",
                         evidence_refs=[]),
            _action_json("stop"),
        ], budget={"max_turns": 10})
        await session_obj.run()
        session_obj.session.refresh_from_db()
        assert session_obj.session.consumed_budget["mission"]["turns"] >= 1

    @pytest.mark.asyncio
    async def test_budget_persisted_after_invalid_turn(self, db_objects):
        """Invalid JSON path also persists consumed_budget via finally."""
        session_obj = _ctrl(
            db_objects,
            responses=[
                "not json", "not json", "not json",  # exhaust retries
                _action_json("stop"),
            ],
            budget={"max_turns": 10},
        )
        await session_obj.run()
        session_obj.session.refresh_from_db()
        assert session_obj.session.consumed_budget["mission"]["turns"] >= 1


@pytest.mark.django_db(transaction=True)
class TestFillFormExecution:
    @pytest.mark.asyncio
    async def test_fill_form_calls_driver_fill(self, db_objects):
        fill_json = _action_json(
            action="fill_form", element_id="input_0", value="admin",
        )
        ctrl = _ctrl(
            db_objects,
            responses=[fill_json],
            budget={
                "max_turns": 5,
                "max_browser_actions": 5,
                "max_form_fills": 5,
            },
        )
        ctrl.session.current_phase = "enumerate"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.fill = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.fill.assert_awaited_once_with("input_0", "admin")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()


@pytest.mark.django_db(transaction=True)
class TestSubmitFormExecution:
    @pytest.mark.asyncio
    async def test_submit_form_calls_driver_click(self, db_objects):
        submit_json = _action_json(
            action="submit_form", element_id="btn_0",
        )
        ctrl = _ctrl(
            db_objects,
            responses=[submit_json],
            budget={
                "max_turns": 5,
                "max_browser_actions": 5,
                "max_form_submits": 5,
            },
        )
        ctrl.session.current_phase = "probe"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.click = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.click.assert_awaited_once_with("btn_0")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()


@pytest.mark.django_db(transaction=True)
class TestClickExecution:
    @pytest.mark.asyncio
    async def test_click_persists_page_observation(self, db_objects):
        click_json = _action_json(
            action="click", element_id="link_0",
        )
        ctrl = _ctrl(db_objects, responses=[click_json], budget={"max_turns": 5})
        ctrl.session.current_phase = "probe"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.click = AsyncMock()

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.click.assert_awaited_once_with("link_0")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="page",
        ).exists()


@pytest.mark.django_db(transaction=True)
class TestHttpRequestExecution:
    @pytest.mark.asyncio
    async def test_http_request_persists_http_observation(self, db_objects):
        req_json = _action_json(
            action="http_request", method="GET", path="/api/test",
        )
        ctrl = _ctrl(db_objects, responses=[req_json], budget={"max_turns": 5})
        ctrl.session.current_phase = "probe"
        ctrl.session.save(update_fields=["current_phase"])
        ctrl.driver.http_request = AsyncMock(return_value={
            "url": "https://test.example.com/api/test",
            "method": "GET", "status": 200,
            "content_type": "application/json",
            "redirected": False, "final_url": "https://test.example.com/api/test",
            "body_excerpt": '{"ok": true}', "body_truncated": False,
            "trust": "untrusted_target_content",
        })

        from apps.agent.controller_turn import run_turn
        await run_turn(ctrl)

        ctrl.driver.http_request.assert_awaited_once_with("GET", "/api/test")
        from apps.agent.models import AgentObservation
        assert AgentObservation.objects.filter(
            action__turn__session=ctrl.session,
            observation_type="http",
        ).exists()


@pytest.mark.django_db(transaction=True)
class TestVerifyPhaseGate:
    @pytest.mark.asyncio
    async def test_verify_transition_denied_without_candidate(self, db_objects):
        """Transition to verify is denied if no submit_candidate exists."""
        c = _ctrl(db_objects, [
            _action_json(
                "request_phase_transition", from_phase="probe",
                to_phase="verify", evidence_refs=[],
            ),
            _action_json("stop"),
        ])
        c.session.current_phase = "probe"
        c.session.save(update_fields=["current_phase"])
        c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
        await c.run()
        c.session.refresh_from_db()
        assert c.session.current_phase == "probe"

    @pytest.mark.asyncio
    async def test_verify_transition_allowed_with_candidate(self, db_objects):
        """Transition to verify is allowed when a submit_candidate action exists."""
        c = _ctrl(db_objects, [
            _action_json(
                "submit_candidate", category="xss",
                description="test", evidence_refs=[],
            ),
            _action_json(
                "request_phase_transition", from_phase="probe",
                to_phase="verify", evidence_refs=[],
            ),
            _action_json("stop"),
        ])
        c.session.current_phase = "probe"
        c.session.save(update_fields=["current_phase"])
        c._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]
        await c.run()
        c.session.refresh_from_db()
        assert c.session.status == "completed"
        assert c.session.current_phase == "verify"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_full_form_flow_with_verify(db_objects):
    """
    End-to-end: navigate → fill×2 → submit → candidate → transition verify
    → navigate → fill → submit → stop.

    Asserts status=completed, current_phase=verify,
    3 fill_form actions and 2 submit_form actions recorded.
    """
    budget = {
        "max_turns": 20,
        "max_llm_calls": 20,
        "max_browser_actions": 20,
        "max_form_fills": 10,
        "max_form_submits": 10,
    }
    responses = [
        _action_json("navigate", path="/login"),
        _action_json("fill_form", element_id="input_email", value="admin@example.com"),
        _action_json("fill_form", element_id="input_password", value="admin"),
        _action_json("submit_form", element_id="btn_login"),
        _action_json(
            "submit_candidate", category="broken_auth",
            description="login form exposes credentials in URL", evidence_refs=[],
        ),
        _action_json(
            "request_phase_transition", from_phase="probe",
            to_phase="verify", evidence_refs=[],
        ),
        _action_json("navigate", path="/login"),
        _action_json("fill_form", element_id="input_email", value="victim@example.com"),
        _action_json("submit_form", element_id="btn_login"),
        _action_json("stop"),
    ]

    driver = _mock_driver()
    driver.fill = AsyncMock()
    driver.click = AsyncMock()

    ctrl = _ctrl(db_objects, responses, driver=driver, budget=budget)
    ctrl.session.current_phase = "probe"
    ctrl.session.save(update_fields=["current_phase"])
    ctrl._mission_phases = ["recon", "enumerate", "probe", "verify", "report"]

    from unittest.mock import patch
    from apps.agent.plateau import PlateauDetector

    lenient = {"max_turns_without_new_route": 20,
               "max_turns_without_new_interactive_element": 20}

    def _lenient_plateau(*_args, **_kw):
        return PlateauDetector(**lenient)

    ctrl.plateau = PlateauDetector(**lenient)
    with patch("apps.agent.controller.PlateauDetector", side_effect=_lenient_plateau):
        await ctrl.run()

    ctrl.session.refresh_from_db()
    assert ctrl.session.status == SessionStatus.COMPLETED
    assert ctrl.session.current_phase == "verify"

    fill_count = AgentAction.objects.filter(
        turn__session=ctrl.session, action_type="fill_form",
    ).count()
    submit_count = AgentAction.objects.filter(
        turn__session=ctrl.session, action_type="submit_form",
    ).count()
    assert fill_count == 3
    assert submit_count == 2
