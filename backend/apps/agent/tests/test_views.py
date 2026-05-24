from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.agent.models import SessionStatus
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


class AgentSessionListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="test")
        self.target = ScanTarget.objects.create(
            host="test.example.com", project=self.project,
        )
        run = ScanRun.objects.create(
            project=self.project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=self.target)
        from apps.agent.models import AgentSession, AutonomyMode, AgentPhase
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=self.target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="juice_shop_scoreboard",
        )

    def test_list_returns_200_with_paginated_shape(self):
        url = reverse("agent-session-list")
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert "results" in resp.json()
        assert len(resp.json()["results"]) == 1

    def test_filter_by_status(self):
        url = reverse("agent-session-list")
        resp = self.client.get(url, {"status": "running"})
        assert len(resp.json()["results"]) == 1
        resp = self.client.get(url, {"status": "completed"})
        assert len(resp.json()["results"]) == 0

    def test_filter_by_target(self):
        url = reverse("agent-session-list")
        resp = self.client.get(url, {"target": str(self.target.id)})
        assert len(resp.json()["results"]) == 1


class AgentSessionDetailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com",
            base_url="https://test.example.com",
            project=project,
        )
        run = ScanRun.objects.create(
            project=project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=target)
        from apps.agent.models import AgentSession, AutonomyMode, AgentPhase
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="juice_shop_scoreboard",
        )

    def test_detail_includes_active_phases_and_target_url(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        resp = self.client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_phases"] == ["recon", "enumerate", "report"]
        assert data["target_base_url"] == "https://test.example.com"
        assert data["scan_run"] is not None


class AgentSessionTurnsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com", project=project,
        )
        run = ScanRun.objects.create(
            project=project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=target)
        from apps.agent.models import (
            AgentSession, AgentTurn, AgentAction, AgentObservation,
            AgentNote, AutonomyMode, AgentPhase, TurnStatus,
            ValidationStatus, ExecutionStatus, ObservationType, NoteType,
        )
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )
        turn = AgentTurn.objects.create(
            session=self.session, index=0, phase="recon",
            model="mock", status=TurnStatus.COMPLETED,
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
            session=self.session, turn=turn, note_type=NoteType.ROUTE,
            content={"path": "/test"},
        )

    def test_turns_endpoint_nests_actions_observations_notes(self):
        url = reverse("agent-session-turns", args=[self.session.id])
        resp = self.client.get(url)
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        turn = results[0]
        assert turn["index"] == 0
        assert len(turn["actions"]) == 1
        assert len(turn["actions"][0]["observations"]) == 1
        assert len(turn["notes"]) == 1

    def test_turns_ordered_by_index(self):
        from apps.agent.models import AgentTurn, TurnStatus
        AgentTurn.objects.create(
            session=self.session, index=1, phase="recon",
            model="mock", status=TurnStatus.COMPLETED,
        )
        url = reverse("agent-session-turns", args=[self.session.id])
        results = self.client.get(url).json()["results"]
        assert results[0]["index"] == 0
        assert results[1]["index"] == 1


class AgentSessionNotesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com", project=project,
        )
        run = ScanRun.objects.create(
            project=project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=target)
        from apps.agent.models import (
            AgentSession, AgentTurn, AgentNote, AutonomyMode,
            AgentPhase, TurnStatus, NoteType,
        )
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )
        turn = AgentTurn.objects.create(
            session=self.session, index=5, phase="recon",
            model="mock", status=TurnStatus.COMPLETED,
        )
        AgentNote.objects.create(
            session=self.session, turn=turn,
            note_type=NoteType.HYPOTHESIS,
            content={"text": "test"},
        )

    def test_notes_includes_turn_index(self):
        url = reverse("agent-session-notes", args=[self.session.id])
        resp = self.client.get(url)
        assert resp.status_code == 200
        note = resp.json()["results"][0]
        assert note["turn_index"] == 5
        assert note["note_type"] == "hypothesis"


class AgentSessionReadOnlyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com", project=project,
        )
        run = ScanRun.objects.create(
            project=project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(scan_run=run, target=target)
        from apps.agent.models import AgentSession, AutonomyMode, AgentPhase
        self.session = AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )

    def test_put_returns_405(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        assert self.client.put(url, {}).status_code == 405

    def test_patch_returns_405(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        assert self.client.patch(url, {}).status_code == 405

    def test_delete_returns_405(self):
        url = reverse("agent-session-detail", args=[self.session.id])
        assert self.client.delete(url).status_code == 405


class AgentSessionCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="test")
        self.target = ScanTarget.objects.create(
            host="juiceshop.cocode.dk", project=self.project,
            base_url="https://juiceshop.cocode.dk",
        )

    def test_create_returns_201_with_full_session(self):
        url = reverse("agent-session-list")
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            resp = self.client.post(url, {
                "target": str(self.target.id),
                "mission_profile": "juice_shop_scoreboard",
            }, format="json")
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "running"
        assert data["current_phase"] == "recon"
        assert data["mission_profile"] == "juice_shop_scoreboard"
        assert data["scan_run"] is not None
        assert data["scan_target_run"] is not None
        assert len(callbacks) == 1

    def test_create_creates_scan_run_and_target_run(self):
        url = reverse("agent-session-list")
        with self.captureOnCommitCallbacks(execute=False):
            self.client.post(url, {
                "target": str(self.target.id),
            }, format="json")
        assert ScanRun.objects.filter(stub_slug="agent.v3").count() == 1
        assert ScanTargetRun.objects.count() == 1

    def test_create_emits_session_started_event(self):
        from apps.events.models import Event
        from apps.events.types import EventType
        url = reverse("agent-session-list")
        with self.captureOnCommitCallbacks(execute=False):
            self.client.post(url, {
                "target": str(self.target.id),
            }, format="json")
        assert Event.objects.filter(
            type=EventType.AGENT_SESSION_STARTED
        ).exists()


class AgentSessionCreateValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="test")
        self.target = ScanTarget.objects.create(
            host="test.example.com", project=self.project,
        )

    def test_unknown_target_returns_400(self):
        import uuid
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(uuid.uuid4()),
        }, format="json")
        assert resp.status_code == 400

    def test_unknown_profile_returns_400(self):
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(self.target.id),
            "mission_profile": "nonexistent",
        }, format="json")
        assert resp.status_code == 400

    def test_duplicate_active_session_returns_400(self):
        from apps.agent.models import (
            AgentSession, AutonomyMode, AgentPhase, SessionStatus,
        )
        run = ScanRun.objects.create(
            project=self.project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(
            scan_run=run, target=self.target,
        )
        AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=self.target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(self.target.id),
        }, format="json")
        assert resp.status_code == 400
        assert "active" in str(resp.json()).lower()
