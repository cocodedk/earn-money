from __future__ import annotations

import pytest
from django.utils import timezone

from apps.agent.models import (
    AgentPhase,
    NoteType,
    ObservationType,
    SessionStatus,
    TurnStatus,
    ValidationStatus,
)
from apps.agent.persistence import (
    create_session,
    create_turn,
    finish_session,
    finish_turn,
    record_action,
    record_note,
    record_observation,
)
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def db_objects(db):
    project = Project.objects.create(name="persist-test")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    return {"scan_run": scan_run, "target_run": target_run, "target": target}


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_create_session_sets_running_status(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="test_mission",
        model_policy={"primary": "mock"},
        mission_budget={"max_turns": 10},
    )
    assert session.status == SessionStatus.RUNNING


@pytest.mark.django_db
def test_create_session_sets_started_at(db_objects):
    before = timezone.now()
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="test_mission",
        model_policy={},
        mission_budget={},
    )
    assert session.started_at is not None
    assert session.started_at >= before


@pytest.mark.django_db
def test_create_session_stores_profile_and_budget(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="juice_shop",
        model_policy={"model": "claude-sonnet"},
        mission_budget={"max_turns": 25},
    )
    assert session.mission_profile == "juice_shop"
    assert session.model_policy == {"model": "claude-sonnet"}
    assert session.mission_budget == {"max_turns": 25}


# ---------------------------------------------------------------------------
# create_turn
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_create_turn_first_index_is_zero(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={},
    )
    turn = create_turn(session, model="mock-model")
    assert turn.index == 0


@pytest.mark.django_db
def test_create_turn_auto_increments(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={},
    )
    t0 = create_turn(session, model="mock")
    t1 = create_turn(session, model="mock")
    t2 = create_turn(session, model="mock")
    assert t0.index == 0
    assert t1.index == 1
    assert t2.index == 2


@pytest.mark.django_db
def test_create_turn_sets_started_status(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={},
    )
    turn = create_turn(session, model="mock")
    assert turn.status == TurnStatus.STARTED


# ---------------------------------------------------------------------------
# record_action
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_record_action_persisted(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={},
    )
    turn = create_turn(session, model="mock")
    action = record_action(
        turn=turn,
        action_type="observe_page",
        args_redacted={"path": "/"},
        goal="See login",
    )
    assert action.pk is not None
    assert action.turn == turn
    assert action.action_type == "observe_page"
    assert action.goal == "See login"
    assert action.validation_status == ValidationStatus.VALID


# ---------------------------------------------------------------------------
# record_observation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_record_observation_persisted(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={},
    )
    turn = create_turn(session, model="mock")
    action = record_action(turn=turn, action_type="observe_page", args_redacted={})
    obs = record_observation(
        action=action,
        observation_type=ObservationType.PAGE,
        data={"url": "/"},
        content_hash="abc123",
    )
    assert obs.pk is not None
    assert obs.action == action
    assert obs.observation_type == ObservationType.PAGE
    assert obs.content_hash == "abc123"


# ---------------------------------------------------------------------------
# record_note
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_record_note_persisted(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={},
    )
    turn = create_turn(session, model="mock")
    note = record_note(
        session=session,
        turn=turn,
        note_type=NoteType.HYPOTHESIS,
        content={"text": "Login might be at /login"},
        evidence_refs=["obs_0"],
    )
    assert note.pk is not None
    assert note.session == session
    assert note.note_type == NoteType.HYPOTHESIS
    assert note.evidence_refs == ["obs_0"]


# ---------------------------------------------------------------------------
# finish_turn
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_finish_turn_sets_status_and_timestamp(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={},
    )
    turn = create_turn(session, model="mock")
    before = timezone.now()
    finish_turn(turn, TurnStatus.COMPLETED)
    turn.refresh_from_db()
    assert turn.status == TurnStatus.COMPLETED
    assert turn.finished_at is not None
    assert turn.finished_at >= before


# ---------------------------------------------------------------------------
# finish_session
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_finish_session_sets_status_budget_and_timestamp(db_objects):
    session = create_session(
        scan_run=db_objects["scan_run"],
        target_run=db_objects["target_run"],
        target=db_objects["target"],
        mission_profile="t",
        model_policy={},
        mission_budget={"max_turns": 5},
    )
    before = timezone.now()
    finish_session(session, SessionStatus.COMPLETED, {"turns": 3})
    session.refresh_from_db()
    assert session.status == SessionStatus.COMPLETED
    assert session.consumed_budget == {"turns": 3}
    assert session.finished_at is not None
    assert session.finished_at >= before
