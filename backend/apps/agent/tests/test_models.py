import pytest
from apps.agent.models import AgentSession, AutonomyMode, AgentPhase, SessionStatus
from apps.agent.models import AgentTurn, TurnStatus
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project


@pytest.mark.django_db
def test_agent_session_creation():
    project = Project.objects.create(name="test")
    target = ScanTarget.objects.create(host="juiceshop.cocode.dk", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    session = AgentSession.objects.create(
        scan_target_run=target_run, scan_run=scan_run, target=target,
        autonomy_mode=AutonomyMode.LAB_FREE_RUN,
        current_phase=AgentPhase.RECON, status=SessionStatus.PENDING,
        mission_profile="juice_shop_scoreboard",
        model_policy={"primary_model": "claude-sonnet-4-6"},
        roe_snapshot={}, mission_budget={"max_turns": 25},
        consumed_budget={"turns": 0}, progress_counters={"routes": 0},
    )
    assert session.pk is not None
    assert session.scan_target_run == target_run
    assert session.autonomy_mode == AutonomyMode.LAB_FREE_RUN


@pytest.mark.django_db
def test_agent_turn_unique_index(create_session):
    session = create_session()
    AgentTurn.objects.create(
        session=session, index=0, phase="recon",
        model="claude-sonnet-4-6", prompt_artifact_ref="ref_0",
        response_artifact_ref="ref_1", prompt_hash="h0",
        response_hash="h1", input_tokens=100, output_tokens=50,
        status=TurnStatus.COMPLETED,
    )
    with pytest.raises(Exception):
        AgentTurn.objects.create(
            session=session, index=0, phase="recon",
            model="claude-sonnet-4-6", prompt_artifact_ref="ref_2",
            response_artifact_ref="ref_3", prompt_hash="h2",
            response_hash="h3", input_tokens=100, output_tokens=50,
            status=TurnStatus.COMPLETED,
        )


from apps.agent.models import (  # noqa: E402
    AgentAction, ValidationStatus, ExecutionStatus,
    AgentObservation, ObservationType,
    AgentNote, NoteType,
)


@pytest.mark.django_db
def test_agent_action_creation(create_turn):
    turn = create_turn()
    action = AgentAction.objects.create(
        turn=turn, action_type="observe_page",
        args_redacted={}, goal="See the page",
        validation_status=ValidationStatus.VALID,
        execution_status=ExecutionStatus.EXECUTED,
    )
    assert action.turn == turn
    assert action.action_type == "observe_page"


@pytest.mark.django_db
def test_agent_observation_creation(create_action):
    action = create_action()
    obs = AgentObservation.objects.create(
        action=action, observation_type=ObservationType.PAGE,
        data={"page": {"path": "/"}}, content_hash="abc123",
    )
    assert obs.observation_type == ObservationType.PAGE


@pytest.mark.django_db
def test_agent_note_creation(create_session, create_turn):
    session = create_session()
    turn = create_turn(session=session)
    note = AgentNote.objects.create(
        session=session, turn=turn, note_type=NoteType.HYPOTHESIS,
        content={"text": "This looks interesting"},
    )
    assert note.note_type == NoteType.HYPOTHESIS
