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

1. `ScanRun` with `stub_slug="agent.v3"`, `project` from target, status=PENDING
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
- `mission_profile` must exist in `mission_profiles._PROFILES`
- Target must not already have an active (RUNNING/PENDING) agent session

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
3. Emit `EventType.TARGET_RUN_STARTED` for the ScanTargetRun
4. Build provider (from session.model_policy)
5. Build PlaywrightDriver (browser created inside the task process)
6. Build MissionController

**After controller.run() completes:**
1. AgentSession is already finished by controller._finish()
2. Mark ScanTargetRun terminal: map session status → target_run status
   - SessionStatus.COMPLETED → TargetRunStatus.DONE
   - SessionStatus.STOPPED → TargetRunStatus.STOPPED
   - SessionStatus.FAILED → TargetRunStatus.FAILED
3. Emit `EventType.TARGET_RUN_DONE` / `TARGET_RUN_STOPPED` / `TARGET_RUN_FAILED`
4. Mark ScanRun terminal (same mapping to RunStatus)
5. Emit `EventType.SCAN_RUN_DONE` / `SCAN_RUN_STOPPED` / `SCAN_RUN_FAILED`

The SSE stream in `backend/apps/events/views.py:46` closes when
ScanRun.status is terminal. Without step 4-5, the SSE stream
never closes and the frontend never sees mission completion.

**On unhandled exception:**
1. Mark AgentSession as FAILED (if not already finished)
2. Mark ScanTargetRun as FAILED
3. Mark ScanRun as FAILED
4. Emit failure events
5. Re-raise (Celery logs it)

### Status Mapping

| AgentSession status | ScanTargetRun status | ScanRun status |
|---------------------|----------------------|----------------|
| COMPLETED           | DONE                 | DONE           |
| STOPPED             | STOPPED              | STOPPED        |
| FAILED              | FAILED               | FAILED         |

### Controller Budget Update

Modify `controller_turn.run_turn()` to write `consumed_budget` to the
session after every turn (not just at finish). This gives the REST
endpoint live budget data for polling.

```python
# At end of run_turn, before return:
ctrl.session.consumed_budget = ctrl.budget.consumed_snapshot()
ctrl.session.save(update_fields=["consumed_budget"])
```
