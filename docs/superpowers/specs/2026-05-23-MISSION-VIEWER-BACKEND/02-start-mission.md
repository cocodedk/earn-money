# Start Mission — POST Endpoint + Celery Task

## POST /api/agent/sessions/

Creates everything needed for a mission and enqueues it.

### Request Body

```json
{
  "target": "<uuid>",
  "mission_profile": "juice_shop_scoreboard"
}
```

- `target`: required, UUID of a ScanTarget
- `mission_profile`: optional, defaults to `"juice_shop_scoreboard"`

### What It Creates (atomic transaction)

1. `ScanRun` with `stub_slug="agent.v3"`, `project` from target, status=QUEUED
2. `ScanTargetRun` linking the scan run to the target
3. `AgentSession` via `persistence.create_session()` — status=RUNNING, phase=RECON
4. Starts the ScanRun (status → RUNNING)
5. Emits `agent.session_started` event

### Post-Commit

`transaction.on_commit(lambda: run_agent_session.delay(str(session.id)))`

### Response (201)

Full AgentSessionSerializer output including `scan_run` UUID for SSE.

### Validation

- `target` must exist
- `mission_profile` must resolve through `mission_profiles.get_profile()`
- Target must not already have an active agent session with status `pending` or `running`

## Celery Task: run_agent_session

New file: `backend/apps/agent/tasks.py`

### Signature

```python
@shared_task(bind=True, max_retries=0)
def run_agent_session(self, session_id: str) -> None:
```

### Lifecycle Management

The task manages three levels of lifecycle state:

**Before controller.run():**
1. Load AgentSession, ScanTargetRun, ScanRun
2. Mark ScanTargetRun as started (status → RUNNING, started_at=now)
3. Emit `EventType.SCAN_TARGET_RUN_STARTED` for the ScanTargetRun
4. Build provider from `session.model_policy`
5. Build PlaywrightDriver (browser created inside the task process)
6. Build MissionController

**After controller.run() completes:**
1. AgentSession is already finished by controller._finish()
2. Mark ScanTargetRun terminal: map session status → target_run status
   - SessionStatus.COMPLETED → RunStatus.DONE
   - SessionStatus.STOPPED → RunStatus.STOPPED
   - SessionStatus.FAILED → RunStatus.FAILED
3. Emit `EventType.SCAN_TARGET_RUN_DONE` / `SCAN_TARGET_RUN_STOPPED` / `SCAN_TARGET_RUN_FAILED`
4. Mark ScanRun terminal (same mapping to RunStatus)
5. Emit `EventType.SCAN_RUN_DONE` / `SCAN_RUN_STOPPED_FINAL` / `SCAN_RUN_FAILED`

`EventType.SCAN_RUN_FAILED = "scan_run.failed"` does not exist yet. Add it in
`backend/apps/events/types.py` with the task implementation, and add the
corresponding migration if Django detects the choice-list change. Use
`SCAN_RUN_STOPPED_FINAL`, not `SCAN_RUN_STOPPED`, for controller-driven terminal
stops; `SCAN_RUN_STOPPED` is the existing operator-request event emitted by
`ScanRun.stop()`.

The SSE stream in `backend/apps/events/views.py:46` closes when
ScanRun.status is terminal. Without step 4-5, the SSE stream
never closes and the frontend never sees mission completion.

**On unhandled exception:**
1. Mark AgentSession as FAILED (if not already finished)
2. Mark ScanTargetRun as FAILED
3. Mark ScanRun as FAILED
4. Emit failure events
5. Re-raise (Celery logs it)

Always call `await driver.stop()` in a `finally` block once the driver has been
started. Finalization should be idempotent: do not overwrite a target run or scan
run that is already in a terminal status.

### Status Mapping

| AgentSession status | ScanTargetRun status | ScanRun status |
|---------------------|----------------------|----------------|
| COMPLETED           | DONE                 | DONE           |
| STOPPED             | STOPPED              | STOPPED        |
| FAILED              | FAILED               | FAILED         |

All ScanTargetRun and ScanRun terminal statuses are values from
`apps.scans.models.RunStatus`.

### Controller Budget Update

Modify the controller turn path to write `consumed_budget` to the session after
every turn, including invalid-action and denied-action branches. This gives the
REST endpoint live budget data for polling.

```python
# Use a helper/finally path, not a single line after _execute(), because
# run_turn() has multiple early returns.
ctrl.session.consumed_budget = ctrl.budget.consumed_snapshot()
ctrl.session.save(update_fields=["consumed_budget"])
```

The persisted `consumed_budget` shape is the current `BudgetTracker`
`consumed_snapshot()` shape:

```json
{
  "mission": {"turns": 4},
  "phase": {"turns": 2}
}
```

## Tests

- Task success path marks ScanTargetRun RUNNING before controller execution,
  then DONE, emits started/done target events, marks ScanRun DONE, and emits
  `scan_run.done`.
- Task stopped path maps SessionStatus.STOPPED to RunStatus.STOPPED and emits
  `scan_target_run.stopped` plus `scan_run.stopped_final`.
- Task failure path marks AgentSession, ScanTargetRun, and ScanRun FAILED,
  emits `scan_target_run.failed` plus `scan_run.failed`, stops the driver, and
  re-raises for Celery logging.
- Task finalization is idempotent for already-terminal target runs and scan
  runs.
- Provider construction uses `session.model_policy["provider"]` and
  `session.model_policy["model"]`, with compatibility for legacy
  `provider_type` / `primary_model` keys if present in old test data.
