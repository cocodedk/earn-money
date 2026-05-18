"""Scan-run dispatcher — routes each target_run to its registered stub
runner (apps.stubs.runners), with the simulator as fallback for stubs
whose runner is not yet registered.

Per docs/superpowers/specs/2026-05-18-DOCKERIZED-ENV/07-celery-task.md.
The control loop (status checks, paired started/done/failed events,
cooperative pause/stop) is platform-level and stays the same regardless
of what the runner does in between.

Cooperative pause/stop:
- /pause/ sets ScanRun.status=paused. Worker sees it at the next check
  and exits clean; /resume/ re-enqueues the task.
- /stop/ sets ScanRun.status=stopping. Worker marks the current
  target_run as stopped and moves the run to stopped before exiting.
- Runner exceptions are caught per-target — the target_run transitions
  to FAILED and a scan_target_run.failed event is emitted; the scan_run
  continues with the next target.
"""
from __future__ import annotations

import time
from typing import Any

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.events.models import Event
from apps.events.types import EventType

from .models import RunStatus, ScanRun, ScanTargetRun


# Short delay for simulator only; real runners will have their own pacing.
SIMULATOR_STEP_DELAY = 0.05


_TERMINAL_TR_STATUSES = (
    RunStatus.DONE,
    RunStatus.STOPPED,
    RunStatus.FAILED,
)


@shared_task
def run_scan(scan_run_id: str) -> None:
    """Celery entry point — delegates to the testable helper."""
    _execute_scan(scan_run_id)


def _execute_scan(scan_run_id: str) -> None:
    run = ScanRun.objects.get(id=scan_run_id)

    for tr in run.target_runs.order_by("created_at"):
        run.refresh_from_db()

        if run.status == RunStatus.STOPPING:
            _finalize_stopped(run, tr)
            return
        if run.status != RunStatus.RUNNING:
            # paused / done / failed / queued — nothing to do.
            return
        if tr.status in _TERMINAL_TR_STATUSES:
            continue

        _process_target_run(run, tr)

    run.refresh_from_db()
    if run.status == RunStatus.RUNNING:
        _mark_run_done(run)


def _process_target_run(run: ScanRun, tr: ScanTargetRun) -> None:
    """Run one target through running → done with paired events.

    Dispatch sequence:
    1. Flip target_run to RUNNING + emit scan_target_run.started.
    2. Dispatch to the registered runner for `run.stub_slug`. When no
       runner is registered (typical for stubs whose spec is still
       pending), fall back to the simulator: a brief sleep that proves
       the control loop without doing any HTTP work.
    3. Flip target_run to DONE + emit scan_target_run.done.

    The start/done bracketing is platform-level — every runner gets the
    same lifecycle events regardless of what it does in between.
    """
    from apps.stubs.runners import get as get_runner

    started_payload: dict[str, Any] = {
        "id": str(tr.id),
        "scan_run_id": str(run.id),
        "target_id": str(tr.target_id),
    }

    with transaction.atomic():
        tr.status = RunStatus.RUNNING
        tr.started_at = timezone.now()
        tr.save(update_fields=["status", "started_at", "updated_at"])
        Event.log(
            type=EventType.SCAN_TARGET_RUN_STARTED,
            scan_run=run,
            target=tr.target,
            subject=tr,
            data=started_payload,
        )

    runner = get_runner(run.stub_slug)
    try:
        if runner is None:
            time.sleep(SIMULATOR_STEP_DELAY)  # simulator fallback
        else:
            runner(run, tr)
    except Exception as exc:
        # Isolate per-target runner crashes — without this catch, a
        # single httpx.ConnectError leaves target_run pinned at RUNNING
        # with no terminal event, and the SSE stream never closes.
        _finalize_failed(run, tr, started_payload, exc)
        return

    with transaction.atomic():
        tr.status = RunStatus.DONE
        tr.finished_at = timezone.now()
        tr.save(update_fields=["status", "finished_at", "updated_at"])
        Event.log(
            type=EventType.SCAN_TARGET_RUN_DONE,
            scan_run=run,
            target=tr.target,
            subject=tr,
            data={**started_payload, "finished_at": tr.finished_at},
        )


def _finalize_stopped(run: ScanRun, current_tr: ScanTargetRun) -> None:
    """ScanRun.status was flipped to STOPPING. Mark the target the worker
    was about to pick up as stopped, then move the run to STOPPED."""
    with transaction.atomic():
        if current_tr.status not in _TERMINAL_TR_STATUSES:
            current_tr.status = RunStatus.STOPPED
            current_tr.finished_at = timezone.now()
            current_tr.save(
                update_fields=["status", "finished_at", "updated_at"]
            )
            Event.log(
                type=EventType.SCAN_TARGET_RUN_STOPPED,
                scan_run=run,
                target=current_tr.target,
                subject=current_tr,
                data={
                    "id": str(current_tr.id),
                    "scan_run_id": str(run.id),
                    "target_id": str(current_tr.target_id),
                },
            )
        run.status = RunStatus.STOPPED
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at", "updated_at"])
        Event.log(
            type=EventType.SCAN_RUN_STOPPED_FINAL,
            scan_run=run,
            subject=run,
            data={"id": str(run.id), "transition": "stopping → stopped"},
        )


def _finalize_failed(
    run: ScanRun,
    tr: ScanTargetRun,
    started_payload: dict[str, Any],
    exc: Exception,
) -> None:
    with transaction.atomic():
        tr.status = RunStatus.FAILED
        tr.finished_at = timezone.now()
        tr.save(update_fields=["status", "finished_at", "updated_at"])
        Event.log(
            type=EventType.SCAN_TARGET_RUN_FAILED,
            scan_run=run,
            target=tr.target,
            subject=tr,
            data={
                **started_payload,
                "finished_at": tr.finished_at,
                "error": type(exc).__name__,
                "message": str(exc),
            },
        )


def _mark_run_done(run: ScanRun) -> None:
    with transaction.atomic():
        run.status = RunStatus.DONE
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at", "updated_at"])
        Event.log(
            type=EventType.SCAN_RUN_DONE,
            scan_run=run,
            subject=run,
            data={"id": str(run.id)},
        )
