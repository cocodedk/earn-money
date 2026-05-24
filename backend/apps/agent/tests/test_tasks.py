import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from apps.agent.models import AgentSession, SessionStatus
from apps.agent.tasks import run_agent_session
from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project
from apps.scans.models import RunStatus, ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


def _create_session_for_task():
    from apps.agent.models import AutonomyMode, AgentPhase
    project = Project.objects.create(name="test")
    target = ScanTarget.objects.create(
        host="juiceshop.cocode.dk", project=project,
        base_url="https://juiceshop.cocode.dk",
    )
    scan_run = ScanRun.objects.create(
        project=project, stub_slug="agent.v3", status=RunStatus.RUNNING,
    )
    target_run = ScanTargetRun.objects.create(
        scan_run=scan_run, target=target,
    )
    session = AgentSession.objects.create(
        scan_target_run=target_run, scan_run=scan_run, target=target,
        autonomy_mode=AutonomyMode.LAB_FREE_RUN,
        current_phase=AgentPhase.RECON,
        status=SessionStatus.RUNNING,
        mission_profile="juice_shop_scoreboard",
        model_policy={"provider": "mock", "model": "mock"},
        mission_budget={"max_turns": 5},
    )
    return session, target_run, scan_run


@pytest.mark.django_db(transaction=True)
class TestRunAgentSessionSuccess:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_marks_target_run_started_then_done(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value

            async def _set_completed():
                from asgiref.sync import sync_to_async
                await sync_to_async(
                    AgentSession.objects.filter(pk=session.pk).update
                )(status=SessionStatus.COMPLETED)

            ctrl_instance.run = AsyncMock(side_effect=_set_completed)

            run_agent_session(str(session.id))

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.DONE
        assert scan_run.status == RunStatus.DONE
        assert target_run.started_at is not None
        assert target_run.finished_at is not None

    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_emits_target_started_and_done_events(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value

            async def _set_completed():
                from asgiref.sync import sync_to_async
                await sync_to_async(
                    AgentSession.objects.filter(pk=session.pk).update
                )(status=SessionStatus.COMPLETED)

            ctrl_instance.run = AsyncMock(side_effect=_set_completed)

            run_agent_session(str(session.id))

        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED,
        ).exists()
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_DONE,
        ).exists()
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_DONE,
        ).exists()


@pytest.mark.django_db(transaction=True)
class TestRunAgentSessionStopped:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_stopped_maps_to_stopped_status(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value

            async def _set_stopped():
                from asgiref.sync import sync_to_async
                await sync_to_async(
                    AgentSession.objects.filter(pk=session.pk).update
                )(status=SessionStatus.STOPPED)

            ctrl_instance.run = AsyncMock(side_effect=_set_stopped)

            run_agent_session(str(session.id))

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.STOPPED
        assert scan_run.status == RunStatus.STOPPED
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STOPPED,
        ).exists()
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_STOPPED_FINAL,
        ).exists()


@pytest.mark.django_db
class TestRunAgentSessionFailure:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_failure_marks_all_failed_and_stops_driver(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value
            ctrl_instance.run = AsyncMock(
                side_effect=RuntimeError("boom"),
            )

            with pytest.raises(RuntimeError, match="boom"):
                run_agent_session(str(session.id))

        session.refresh_from_db()
        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert session.status == SessionStatus.FAILED
        assert target_run.status == RunStatus.FAILED
        assert scan_run.status == RunStatus.FAILED
        driver.stop.assert_awaited_once()
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_FAILED,
        ).exists()


@pytest.mark.django_db
class TestIdempotentFinalization:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_does_not_overwrite_terminal_target_run(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        target_run.status = RunStatus.DONE
        target_run.save(update_fields=["status"])
        scan_run.status = RunStatus.DONE
        scan_run.save(update_fields=["status"])

        started_before = Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED,
        ).count()

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            run_agent_session(str(session.id))
            MockCtrl.assert_not_called()

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.DONE
        assert scan_run.status == RunStatus.DONE
        mock_provider.assert_not_called()
        mock_driver.assert_not_called()
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED,
        ).count() == started_before

    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_finalizes_terminal_session_without_rerunning_controller(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        session.status = SessionStatus.COMPLETED
        session.save(update_fields=["status"])

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            run_agent_session(str(session.id))
            MockCtrl.assert_not_called()

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.DONE
        assert scan_run.status == RunStatus.DONE
        mock_provider.assert_not_called()
        mock_driver.assert_not_called()


@pytest.mark.django_db
class TestBuildDriver:
    @patch("apps.agent.browser.driver.PlaywrightDriver")
    def test_uses_target_base_url_when_present(self, MockDriver):
        session, _target_run, _scan_run = _create_session_for_task()
        from apps.agent.tasks import _build_driver

        _build_driver(session.target)

        MockDriver.assert_called_once_with(
            target_origin="https://juiceshop.cocode.dk",
        )


@pytest.mark.django_db(transaction=True)
class TestTargetIntelWiring:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    @patch("apps.agent.tasks.build_target_intel")
    def test_passes_intel_to_mission_controller(
        self, mock_intel, mock_provider, mock_driver,
    ):
        session, _target_run, _scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.start = AsyncMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = (driver, "https://juiceshop.cocode.dk")

        fake_intel = object()
        mock_intel.return_value = fake_intel

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value

            async def _set_completed():
                from asgiref.sync import sync_to_async
                await sync_to_async(
                    AgentSession.objects.filter(pk=session.pk).update
                )(status=SessionStatus.COMPLETED)

            ctrl_instance.run = AsyncMock(side_effect=_set_completed)
            run_agent_session(str(session.id))

        mock_intel.assert_called_once_with(
            session.target,
            exclude_session_id=session.pk,
            stale_after_days=7,
        )
        _call_kwargs = MockCtrl.call_args.kwargs
        assert _call_kwargs["target_intel"] is fake_intel
