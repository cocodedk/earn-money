---
slug: clean-slate-mission
status: draft
date: 2026-05-25
---

# Clean Slate Mission Mode

## Problem

When testing the V3 agent end-to-end on h1.cocode.dk, prior mission data accumulates. Warm-start
seeds from old sessions, old candidates clutter the DB, and it's impossible to test the agent's
cold-start behavior. There's no way to reset the lab environment to a known baseline before
running a mission.

## Solution

Add a `CLEAN_SLATE=1` option to `scripts/run-mission.sh` that wipes agent/scan/event data on the
VPS via SSH + a Django management command, re-seeds the target, then runs the mission normally.

## Design

### Management command: `reset_lab_db`

New command at `backend/apps/agent/management/commands/reset_lab_db.py`.

```
python manage.py reset_lab_db --host juiceshop.cocode.dk --confirm DELETE_LAB_DB
```

What it does:

1. Validates `--confirm DELETE_LAB_DB` (refuses without it).
2. Deletes all rows from agent tables: AgentNote, AgentObservation, AgentAction, AgentTurn,
   AgentSession.
3. Deletes all rows from: Event, ScanTargetRun, ScanRun.
4. Keeps: Project, ScanTarget, auth/admin users, Django sessions.
5. Looks up the ScanTarget by `--host`. If it doesn't exist, creates a minimal Project +
   ScanTarget with `base_url=https://{host}`.
6. Prints the target UUID to stdout so the caller can use it.

What it does NOT do:

- Does not call `flush` (preserves admin users and Django framework tables).
- Does not touch Redis/Celery queues (the worker restart during sync-vps handles stale tasks).
- Does not create a public API endpoint.

### Script integration: `run-mission.sh`

When `CLEAN_SLATE=1` is set:

1. Require `CLEAN_SLATE_CONFIRM=DELETE_LAB_DB` (die without it).
2. SSH to `recon-vps` and run `reset_lab_db` inside the backend container.
3. Parse the printed target UUID.
4. Skip the normal target lookup (we already have the UUID from the reset).
5. Continue with the normal mission flow.

When `CLEAN_SLATE` is not set, behavior is unchanged.

### Safety guards

- Double confirmation: both env vars must be set.
- The management command only deletes scan/agent/event data, not the target catalog.
- No public HTTP endpoint. SSH-only.
- The command prints what it deleted (row counts per table) for auditability.

## Files to create/modify

| File | Action |
|------|--------|
| `backend/apps/agent/management/__init__.py` | Create (empty) |
| `backend/apps/agent/management/commands/__init__.py` | Create (empty) |
| `backend/apps/agent/management/commands/reset_lab_db.py` | Create |
| `backend/apps/agent/tests/test_reset_lab_db.py` | Create |
| `scripts/run-mission.sh` | Modify (add CLEAN_SLATE block) |

## Out of scope

- Redis/Celery queue cleanup (handled by worker restart on deploy).
- Wiping admin/auth users.
- Public API endpoint for reset.
- Frontend state reset (browser cache/localStorage).

## Tests

1. Command refuses without `--confirm DELETE_LAB_DB`.
2. Command deletes agent/scan/event rows.
3. Command preserves Project and ScanTarget rows.
4. Command creates target if `--host` not found.
5. Command prints target UUID to stdout.
6. Command is idempotent (running twice on empty DB doesn't crash).
