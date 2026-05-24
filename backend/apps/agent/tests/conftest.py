import pytest
from apps.projects.models import Project
from apps.targets.models import ScanTarget
from apps.scans.models import ScanRun, ScanTargetRun


@pytest.fixture
def create_session():
    def _factory(**overrides):
        from apps.agent.models import AgentSession, AutonomyMode, AgentPhase, SessionStatus
        project = Project.objects.create(name="test")
        target = ScanTarget.objects.create(
            host="test.example.com",
            base_url="https://test.example.com",
            project=project,
        )
        scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
        target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
        defaults = dict(
            scan_target_run=target_run, scan_run=scan_run, target=target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON, status=SessionStatus.RUNNING,
            mission_profile="test", model_policy={}, roe_snapshot={},
            mission_budget={}, consumed_budget={}, progress_counters={},
        )
        defaults.update(overrides)
        return AgentSession.objects.create(**defaults)
    return _factory


@pytest.fixture
def create_turn(create_session):
    def _factory(session=None, **overrides):
        from apps.agent.models import AgentTurn, TurnStatus
        session = session or create_session()
        defaults = dict(
            session=session, index=0, phase="recon", model="mock",
            status=TurnStatus.STARTED,
        )
        defaults.update(overrides)
        return AgentTurn.objects.create(**defaults)
    return _factory


@pytest.fixture
def create_action(create_turn):
    def _factory(turn=None, **overrides):
        from apps.agent.models import AgentAction, ValidationStatus, ExecutionStatus
        turn = turn or create_turn()
        defaults = dict(
            turn=turn, action_type="observe_page", args_redacted={},
            validation_status=ValidationStatus.VALID,
            execution_status=ExecutionStatus.PENDING,
        )
        defaults.update(overrides)
        return AgentAction.objects.create(**defaults)
    return _factory
