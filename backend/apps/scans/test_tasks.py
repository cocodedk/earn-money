"""Tests for the scan-run simulator task — written BEFORE the task.

The simulator proves the control loop works without real scanner logic.
Tests exercise the lifecycle paths:
- happy: all target_runs processed, ScanRun marks done
- stopping on entry: target marked stopped, ScanRun marked stopped
- paused on entry: worker exits, no work happens
- non-running status (queued / failed / done): defensive no-op
- already-done target_run: skipped on resume scenarios
- no target_runs: ScanRun goes straight to done

Direct calls into `_execute_scan` rather than `run_scan.delay()` — the
Celery wrapper is just one line of delegation; the logic lives in the
helper. time.sleep is mocked in every test so the simulator runs
instantly.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.projects.models import Project
from apps.targets.models import ScanTarget

from .models import RunStatus, ScanRun, ScanTargetRun


def _make_run_with_targets(target_count: int = 2) -> ScanRun:
    project = Project.objects.create(name="acme")
    run = ScanRun.objects.create(
        project=project, stub_slug="1.1", status=RunStatus.RUNNING
    )
    for i in range(target_count):
        target = ScanTarget.objects.create(
            project=project,
            base_url=f"https://t{i}.cocode.dk",
            host=f"t{i}.cocode.dk",
        )
        ScanTargetRun.objects.create(scan_run=run, target=target)
    return run


@patch("apps.scans.tasks.time.sleep")
class ExecuteScanHappyPathTests(TestCase):
    def test_processes_all_target_runs(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(2)
        _execute_scan(str(run.id))

        run.refresh_from_db()
        assert run.status == RunStatus.DONE
        assert run.finished_at is not None
        target_runs = list(run.target_runs.all())
        assert all(tr.status == RunStatus.DONE for tr in target_runs)
        assert all(tr.finished_at is not None for tr in target_runs)

    def test_emits_start_done_events_per_target(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(2)
        _execute_scan(str(run.id))

        started_events = Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED, scan_run=run
        ).count()
        done_events = Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_DONE, scan_run=run
        ).count()
        assert started_events == 2
        assert done_events == 2

    def test_emits_scan_run_done_event(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(1)
        _execute_scan(str(run.id))

        assert Event.objects.filter(
            type=EventType.SCAN_RUN_DONE, scan_run=run
        ).exists()

    def test_run_with_no_targets_goes_done_immediately(self, _sleep) -> None:
        from .tasks import _execute_scan

        project = Project.objects.create(name="empty")
        run = ScanRun.objects.create(
            project=project, stub_slug="1.1", status=RunStatus.RUNNING
        )
        _execute_scan(str(run.id))
        run.refresh_from_db()
        assert run.status == RunStatus.DONE


@patch("apps.scans.tasks.time.sleep")
class ExecuteScanStopTests(TestCase):
    def test_status_stopping_on_entry_marks_target_and_run_stopped(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(2)
        run.status = RunStatus.STOPPING
        run.save()
        _execute_scan(str(run.id))

        run.refresh_from_db()
        assert run.status == RunStatus.STOPPED
        # First target should be marked stopped (the one the worker was
        # about to pick up); remaining ones stay queued.
        first_tr = run.target_runs.order_by("created_at").first()
        assert first_tr.status == RunStatus.STOPPED
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_STOPPED_FINAL, scan_run=run
        ).exists()


@patch("apps.scans.tasks.time.sleep")
class ExecuteScanPauseTests(TestCase):
    def test_status_paused_on_entry_exits_clean(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(2)
        run.status = RunStatus.PAUSED
        run.save()
        _execute_scan(str(run.id))

        run.refresh_from_db()
        # Status unchanged; worker just exits — /resume/ will re-enqueue.
        assert run.status == RunStatus.PAUSED
        # No target_run advanced.
        assert all(
            tr.status == RunStatus.QUEUED for tr in run.target_runs.all()
        )


@patch("apps.scans.tasks.time.sleep")
class ExecuteScanDefensiveTests(TestCase):
    def test_status_done_on_entry_is_noop(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(1)
        run.status = RunStatus.DONE
        run.save()
        before_event_count = Event.objects.count()
        _execute_scan(str(run.id))
        # No new events.
        assert Event.objects.count() == before_event_count

    def test_terminal_target_run_is_skipped(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(2)
        first, second = list(run.target_runs.order_by("created_at"))
        first.status = RunStatus.DONE
        first.save()
        _execute_scan(str(run.id))

        first.refresh_from_db()
        second.refresh_from_db()
        # First not re-processed (still done with original timestamps)
        assert first.status == RunStatus.DONE
        # Second processed
        assert second.status == RunStatus.DONE


@patch("apps.scans.tasks.time.sleep")
class StartActionEnqueuesTaskTests(TestCase):
    """The /start/ action must enqueue the simulator. transaction.on_commit
    callbacks fire when the TestCase's atomic block commits — use
    `captureOnCommitCallbacks(execute=True)`."""

    def test_start_action_enqueues_run_scan(self, _sleep) -> None:
        from django.urls import reverse
        from rest_framework.test import APIClient

        project = Project.objects.create(name="acme")
        run = ScanRun.objects.create(project=project, stub_slug="1.1")
        client = APIClient()
        url = reverse("scanrun-start", args=[run.id])

        with patch("apps.scans.views.run_scan.delay") as mock_delay, \
             self.captureOnCommitCallbacks(execute=True):
            response = client.post(url)
        assert response.status_code == 200
        mock_delay.assert_called_once_with(str(run.id))


@patch("apps.scans.tasks.time.sleep")
class StubRunnerDispatchTests(TestCase):
    """When a runner is registered for the stub_slug, the task dispatches
    to it (skipping the simulator sleep). When no runner is registered —
    the typical pre-spec-approval state — the simulator fallback runs."""

    def setUp(self) -> None:
        from apps.stubs.runners import _clear_for_testing

        _clear_for_testing()

    def tearDown(self) -> None:
        from apps.stubs.runners import _clear_for_testing

        _clear_for_testing()

    def test_dispatches_to_registered_runner(self, _sleep) -> None:
        from apps.stubs.runners import register

        from .tasks import _execute_scan

        call_args: list = []

        @register("1.1")
        def runner(scan_run, target_run):
            call_args.append((scan_run.id, target_run.id))

        run = _make_run_with_targets(2)
        _execute_scan(str(run.id))

        # Runner invoked once per target.
        assert len(call_args) == 2
        for scan_run_id, _ in call_args:
            assert scan_run_id == run.id

    def test_unregistered_slug_falls_back_to_simulator(self, mock_sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(2)
        _execute_scan(str(run.id))

        # Simulator path uses time.sleep — registered runners don't.
        # Two targets → two simulator sleeps.
        assert mock_sleep.call_count == 2


@patch("apps.scans.tasks.time.sleep")
class RunScanCeleryWrapperTests(TestCase):
    """The @shared_task wrapper just delegates to _execute_scan. Calling
    the task directly (not .delay) invokes the underlying function."""

    def test_wrapper_delegates_to_execute_scan(self, _sleep) -> None:
        from .tasks import run_scan

        run = _make_run_with_targets(1)
        run_scan(str(run.id))
        run.refresh_from_db()
        assert run.status == RunStatus.DONE


@patch("apps.scans.tasks.time.sleep")
class FinalizeStoppedDefensiveTests(TestCase):
    """If /stop/ fires after a target already completed, _finalize_stopped
    sees a terminal target and skips the per-target stopping work."""

    def test_already_done_target_is_not_re_marked(self, _sleep) -> None:
        from .tasks import _execute_scan

        run = _make_run_with_targets(2)
        first_tr = run.target_runs.order_by("created_at").first()
        first_tr.status = RunStatus.DONE
        first_tr.save()
        run.status = RunStatus.STOPPING
        run.save()

        _execute_scan(str(run.id))

        run.refresh_from_db()
        first_tr.refresh_from_db()
        assert run.status == RunStatus.STOPPED
        assert first_tr.status == RunStatus.DONE  # untouched
        # No scan_target_run.stopped event for the already-done target.
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STOPPED
        ).count() == 0


@patch("apps.scans.tasks.time.sleep")
class RunnerFailureTests(TestCase):
    """When a stub runner raises, the dispatcher must isolate the
    failure: mark the target_run FAILED, emit a SCAN_TARGET_RUN_FAILED
    event, and continue with the next target. Otherwise a single
    httpx.ConnectError would leave the run pinned at RUNNING with no
    DONE event — the SSE stream would never close."""

    def setUp(self) -> None:
        from apps.stubs.runners import _clear_for_testing

        _clear_for_testing()

    def tearDown(self) -> None:
        from apps.stubs.runners import _clear_for_testing

        _clear_for_testing()

    def test_runner_exception_marks_target_failed_and_emits_event(self, _sleep) -> None:
        from apps.stubs.runners import register

        from .tasks import _execute_scan

        @register("1.1")
        def runner(scan_run, target_run):
            raise RuntimeError("boom — fake httpx.ConnectError")

        run = _make_run_with_targets(1)
        _execute_scan(str(run.id))

        tr = run.target_runs.get()
        assert tr.status == RunStatus.FAILED
        assert tr.finished_at is not None
        # started event WAS emitted; done was NOT; failed IS.
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED, scan_run=run
        ).count() == 1
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_DONE, scan_run=run
        ).count() == 0
        failed = Event.objects.get(
            type=EventType.SCAN_TARGET_RUN_FAILED, scan_run=run
        )
        assert failed.data["error"] == "RuntimeError"
        assert "boom" in failed.data["message"]

    def test_runner_failure_does_not_block_other_targets(self, _sleep) -> None:
        from apps.stubs.runners import register

        from .tasks import _execute_scan

        calls: list = []

        @register("1.1")
        def runner(scan_run, target_run):
            calls.append(target_run.id)
            if len(calls) == 1:
                raise RuntimeError("first target explodes")

        run = _make_run_with_targets(2)
        _execute_scan(str(run.id))

        # Both targets attempted — second runs after first fails.
        assert len(calls) == 2
        target_runs = list(run.target_runs.order_by("created_at"))
        assert target_runs[0].status == RunStatus.FAILED
        assert target_runs[1].status == RunStatus.DONE
        # Run still finalises — per-target failure doesn't fail the run.
        run.refresh_from_db()
        assert run.status == RunStatus.DONE


@patch("apps.scans.tasks.time.sleep")
class PostLoopRaceTests(TestCase):
    """If ScanRun.status flips externally between the last target
    completion and the post-loop refresh, the task respects the new
    state and does NOT overwrite it with DONE."""

    def test_post_loop_skips_mark_done_when_status_changed(self, _sleep) -> None:
        from .tasks import _execute_scan, _process_target_run

        run = _make_run_with_targets(1)
        real = _process_target_run

        def flip_status_after(run_arg, tr_arg):
            real(run_arg, tr_arg)
            # Simulate an external /pause/ landing mid-task — after the
            # last target finishes but before the post-loop refresh.
            ScanRun.objects.filter(id=run_arg.id).update(
                status=RunStatus.PAUSED
            )

        with patch(
            "apps.scans.tasks._process_target_run", side_effect=flip_status_after
        ):
            _execute_scan(str(run.id))

        run.refresh_from_db()
        # Post-loop refresh picks up PAUSED → skips _mark_run_done.
        assert run.status == RunStatus.PAUSED
