import pytest
from apps.agent.models import ObservationType, ValidationStatus, ExecutionStatus
from apps.agent.serializers import AgentObservationSerializer


@pytest.mark.django_db
class TestAgentObservationSerializer:
    def test_fields(self, create_action):
        from apps.agent.models import AgentObservation
        action = create_action()
        obs = AgentObservation.objects.create(
            action=action, observation_type=ObservationType.PAGE,
            data={"url": "https://example.com"}, content_hash="abc",
        )
        data = AgentObservationSerializer(obs).data
        assert data["observation_type"] == "page"
        assert data["data"] == {"url": "https://example.com"}
        assert data["content_hash"] == "abc"
        assert "id" in data
        assert "created_at" in data


from apps.agent.serializers import AgentActionSerializer


@pytest.mark.django_db
class TestAgentActionSerializer:
    def test_fields_and_nested_observations(self, create_action):
        from apps.agent.models import AgentObservation, ObservationType
        action = create_action(goal="test goal", reason="test reason")
        AgentObservation.objects.create(
            action=action, observation_type=ObservationType.PAGE,
            data={"url": "https://example.com"},
        )
        data = AgentActionSerializer(action).data
        assert data["action_type"] == "observe_page"
        assert data["goal"] == "test goal"
        assert data["reason"] == "test reason"
        assert len(data["observations"]) == 1
        assert data["observations"][0]["observation_type"] == "page"


from apps.agent.serializers import AgentNoteSerializer, AgentTurnNoteSerializer


@pytest.mark.django_db
class TestAgentNoteSerializer:
    def test_includes_turn_index(self, create_session):
        from apps.agent.models import AgentTurn, AgentNote, TurnStatus, NoteType
        session = create_session()
        turn = AgentTurn.objects.create(
            session=session, index=3, phase="recon", model="mock",
            status=TurnStatus.COMPLETED,
        )
        note = AgentNote.objects.create(
            session=session, turn=turn, note_type=NoteType.HYPOTHESIS,
            content={"text": "test hypothesis"},
        )
        data = AgentNoteSerializer(note).data
        assert data["turn_index"] == 3
        assert data["note_type"] == "hypothesis"
        assert data["content"] == {"text": "test hypothesis"}

    def test_turn_note_compact_shape(self, create_session):
        from apps.agent.models import AgentTurn, AgentNote, TurnStatus, NoteType
        session = create_session()
        turn = AgentTurn.objects.create(
            session=session, index=0, phase="recon", model="mock",
            status=TurnStatus.COMPLETED,
        )
        note = AgentNote.objects.create(
            session=session, turn=turn, note_type=NoteType.ROUTE,
            content={"path": "/api/Users"},
        )
        data = AgentTurnNoteSerializer(note).data
        assert "turn_index" not in data
        assert data["note_type"] == "route"


from apps.agent.serializers import AgentTurnSerializer


@pytest.mark.django_db
class TestAgentTurnSerializer:
    def test_nests_actions_and_notes(self, create_session):
        from apps.agent.models import (
            AgentTurn, AgentAction, AgentNote, AgentObservation,
            TurnStatus, ValidationStatus, ExecutionStatus,
            ObservationType, NoteType,
        )
        session = create_session()
        turn = AgentTurn.objects.create(
            session=session, index=0, phase="recon", model="mock",
            input_tokens=100, output_tokens=50, status=TurnStatus.COMPLETED,
        )
        action = AgentAction.objects.create(
            turn=turn, action_type="observe_page", args_redacted={},
            validation_status=ValidationStatus.VALID,
            execution_status=ExecutionStatus.EXECUTED,
        )
        AgentObservation.objects.create(
            action=action, observation_type=ObservationType.PAGE,
            data={"url": "https://example.com"},
        )
        AgentNote.objects.create(
            session=session, turn=turn, note_type=NoteType.ROUTE,
            content={"path": "/test"},
        )
        data = AgentTurnSerializer(turn).data
        assert data["index"] == 0
        assert data["input_tokens"] == 100
        assert len(data["actions"]) == 1
        assert len(data["actions"][0]["observations"]) == 1
        assert len(data["notes"]) == 1
        assert data["notes"][0]["note_type"] == "route"


from apps.agent.serializers import AgentSessionSerializer


@pytest.mark.django_db
class TestAgentSessionSerializer:
    def test_read_fields_include_active_phases_and_target_url(self, create_session):
        session = create_session(mission_profile="juice_shop_scoreboard")
        data = AgentSessionSerializer(session).data
        assert data["active_phases"] == ["recon", "enumerate", "probe", "report"]
        assert data["target_base_url"] is not None
        assert "scan_run" in data
        assert "scan_target_run" in data

    def test_unknown_profile_returns_all_phases(self, create_session):
        session = create_session(mission_profile="unknown_profile")
        data = AgentSessionSerializer(session).data
        assert data["active_phases"] == [
            "recon", "enumerate", "probe", "verify", "report",
        ]
