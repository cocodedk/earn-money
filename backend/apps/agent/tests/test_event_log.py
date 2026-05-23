from __future__ import annotations

import pytest

from apps.agent.event_log import (
    build_budget_snapshot,
    emit_action_denied,
    emit_action_executed,
    emit_mission_finished,
    emit_note_created,
    emit_phase_changed,
    emit_session_started,
    summarize_observation,
)
from apps.events.models import Event
from apps.events.types import EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session(create_session):
    return create_session()


# ---------------------------------------------------------------------------
# emit_session_started
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_emit_session_started_creates_event(session):
    event = emit_session_started(session)
    assert event.pk is not None
    assert event.type == EventType.AGENT_SESSION_STARTED


@pytest.mark.django_db
def test_emit_session_started_links_scan_run_and_target(session):
    event = emit_session_started(session)
    assert event.scan_run == session.scan_run
    assert event.target == session.target


@pytest.mark.django_db
def test_emit_session_started_subject_is_session(session):
    event = emit_session_started(session)
    assert event.subject_type == "agentsession"
    assert event.subject_id == session.pk


@pytest.mark.django_db
def test_emit_session_started_data_contains_profile(session):
    event = emit_session_started(session)
    assert event.data["mission_profile"] == session.mission_profile
    assert event.data["session_id"] == str(session.pk)


# ---------------------------------------------------------------------------
# emit_action_executed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_emit_action_executed_type(session):
    event = emit_action_executed(session, turn_index=0, action_type="observe_page")
    assert event.type == EventType.AGENT_ACTION_EXECUTED


@pytest.mark.django_db
def test_emit_action_executed_data(session):
    event = emit_action_executed(session, turn_index=2, action_type="click")
    assert event.data["turn_index"] == 2
    assert event.data["action_type"] == "click"


# ---------------------------------------------------------------------------
# emit_action_denied
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_emit_action_denied_type(session):
    event = emit_action_denied(session, 1, "navigate", "out of scope")
    assert event.type == EventType.AGENT_ACTION_DENIED


@pytest.mark.django_db
def test_emit_action_denied_data_includes_reason(session):
    event = emit_action_denied(session, 1, "navigate", "RoE violation")
    assert event.data["reason"] == "RoE violation"
    assert event.data["action_type"] == "navigate"


# ---------------------------------------------------------------------------
# emit_phase_changed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_emit_phase_changed_type(session):
    event = emit_phase_changed(session, "recon", "enumerate", "recon done")
    assert event.type == EventType.AGENT_PHASE_CHANGED


@pytest.mark.django_db
def test_emit_phase_changed_data(session):
    event = emit_phase_changed(session, "recon", "probe", "enough routes")
    assert event.data["from_phase"] == "recon"
    assert event.data["to_phase"] == "probe"
    assert event.data["reason"] == "enough routes"


# ---------------------------------------------------------------------------
# emit_note_created
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_emit_note_created_type(session):
    event = emit_note_created(session, note_type="hypothesis", turn_index=3)
    assert event.type == EventType.AGENT_NOTE_CREATED


@pytest.mark.django_db
def test_emit_note_created_data(session):
    event = emit_note_created(session, note_type="candidate", turn_index=5)
    assert event.data["note_type"] == "candidate"
    assert event.data["turn_index"] == 5


# ---------------------------------------------------------------------------
# emit_mission_finished
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_emit_mission_finished_type(session):
    event = emit_mission_finished(session, "completed", "max turns reached")
    assert event.type == EventType.AGENT_MISSION_FINISHED


@pytest.mark.django_db
def test_emit_mission_finished_data(session):
    event = emit_mission_finished(session, "failed", "budget exhausted")
    assert event.data["status"] == "failed"
    assert event.data["reason"] == "budget exhausted"
    assert event.data["mission_profile"] == session.mission_profile


# ---------------------------------------------------------------------------
# Event types registered in EventType
# ---------------------------------------------------------------------------

def test_agent_event_types_exist():
    assert EventType.AGENT_SESSION_STARTED == "agent.session_started"
    assert EventType.AGENT_ACTION_EXECUTED == "agent.action_executed"
    assert EventType.AGENT_ACTION_DENIED == "agent.action_denied"
    assert EventType.AGENT_PHASE_CHANGED == "agent.phase_changed"
    assert EventType.AGENT_NOTE_CREATED == "agent.note_created"
    assert EventType.AGENT_MISSION_FINISHED == "agent.mission_finished"


# ---------------------------------------------------------------------------
# build_budget_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBuildBudgetSnapshot:
    def test_returns_phase_consumed_and_mission_budget(self, create_session):
        session = create_session(
            mission_budget={"max_turns": 25, "max_http_requests": 60},
        )
        session.current_phase = "enumerate"
        consumed = {"mission": {"turns": 4}, "phase": {"turns": 2}}
        result = build_budget_snapshot(session, consumed)
        assert result == {
            "phase": "enumerate",
            "consumed": consumed,
            "mission_budget": {"max_turns": 25, "max_http_requests": 60},
        }


# ---------------------------------------------------------------------------
# summarize_observation
# ---------------------------------------------------------------------------

class TestSummarizeObservation:
    def test_extracts_compact_summary(self):
        obs = {
            "url": "https://juiceshop.cocode.dk/",
            "title": "OWASP Juice Shop",
            "discovered": {
                "routes": ["/", "/rest/products"],
                "assets": ["/main.js"],
            },
            "elements": {
                "links": [{"href": "/"}],
                "buttons": [{"text": "Login"}, {"text": "Search"}],
                "forms": [{"action": "/rest/user/login"}],
            },
            "network": [{"url": "/rest/products"}, {"url": "/api/Challenges"}],
        }
        result = summarize_observation(obs)
        assert result == {
            "url": "https://juiceshop.cocode.dk/",
            "title": "OWASP Juice Shop",
            "route_count": 2,
            "asset_count": 1,
            "element_count": 4,
            "network_count": 2,
        }

    def test_handles_empty_observation(self):
        result = summarize_observation({})
        assert result == {
            "url": "",
            "title": "",
            "route_count": 0,
            "asset_count": 0,
            "element_count": 0,
            "network_count": 0,
        }

    def test_handles_malformed_nested_values(self):
        result = summarize_observation({
            "discovered": None,
            "elements": {"links": None, "buttons": "bad", "forms": []},
            "network": None,
        })
        assert result["route_count"] == 0
        assert result["asset_count"] == 0
        assert result["element_count"] == 0
        assert result["network_count"] == 0
