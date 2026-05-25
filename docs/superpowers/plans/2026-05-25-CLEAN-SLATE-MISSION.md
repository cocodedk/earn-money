# Clean Slate Mission Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `CLEAN_SLATE=1` option to run-mission.sh that wipes agent/scan/event data on the VPS via SSH + Django management command, re-seeds the target, then runs the mission.

**Architecture:** New Django management command `reset_lab_db` handles the DB wipe and target seeding. `run-mission.sh` gains a CLEAN_SLATE block that SSHes to the VPS and runs the command before the normal mission flow.

**Tech Stack:** Django management commands, shell scripting, pytest

---

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/apps/agent/management/__init__.py` | Create | Empty package init |
| `backend/apps/agent/management/commands/__init__.py` | Create | Empty package init |
| `backend/apps/agent/management/commands/reset_lab_db.py` | Create | Management command |
| `backend/apps/agent/tests/test_reset_lab_db.py` | Create | Command tests |
| `scripts/run-mission.sh` | Modify | Add CLEAN_SLATE block |

---

### Task 1: Django management command reset_lab_db

**Files:**
- Create: `backend/apps/agent/management/__init__.py`
- Create: `backend/apps/agent/management/commands/__init__.py`
- Create: `backend/apps/agent/management/commands/reset_lab_db.py`
- Create: `backend/apps/agent/tests/test_reset_lab_db.py`

- [ ] **Step 1: Write failing tests**

Create `backend/apps/agent/tests/test_reset_lab_db.py`:

```python
from __future__ import annotations

import pytest
from io import StringIO

from django.core.management import call_command, CommandError

from apps.agent.models import AgentSession, AgentTurn, AgentAction, AgentNote
from apps.events.models import Event
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


def _seed_full_session(host="test.example.com"):
    from apps.agent.persistence import create_session, create_turn, record_note
    project = Project.objects.create(name="test-project")
    target = ScanTarget.objects.create(host=host, project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    turn = create_turn(session, model="mock")
    record_note(session, turn, "hypothesis", {"text": "test"})
    return target


@pytest.mark.django_db
class TestResetLabDbRefuses:
    def test_refuses_without_confirm(self):
        with pytest.raises(CommandError, match="confirm"):
            call_command("reset_lab_db", "--host", "x.example.com")

    def test_refuses_with_wrong_confirm(self):
        with pytest.raises(CommandError, match="confirm"):
            call_command(
                "reset_lab_db", "--host", "x.example.com",
                "--confirm", "WRONG",
            )


@pytest.mark.django_db
class TestResetLabDbWipes:
    def test_deletes_agent_data(self):
        _seed_full_session("juice.example.com")
        assert AgentSession.objects.exists()
        assert AgentTurn.objects.exists()
        assert AgentNote.objects.exists()

        out = StringIO()
        call_command(
            "reset_lab_db", "--host", "juice.example.com",
            "--confirm", "DELETE_LAB_DB", stdout=out,
        )

        assert not AgentSession.objects.exists()
        assert not AgentTurn.objects.exists()
        assert not AgentNote.objects.exists()

    def test_deletes_scan_data(self):
        _seed_full_session("juice.example.com")
        assert ScanRun.objects.exists()
        assert ScanTargetRun.objects.exists()

        call_command(
            "reset_lab_db", "--host", "juice.example.com",
            "--confirm", "DELETE_LAB_DB",
        )

        assert not ScanRun.objects.exists()
        assert not ScanTargetRun.objects.exists()

    def test_preserves_project_and_target(self):
        _seed_full_session("juice.example.com")
        call_command(
            "reset_lab_db", "--host", "juice.example.com",
            "--confirm", "DELETE_LAB_DB",
        )

        assert Project.objects.exists()
        assert ScanTarget.objects.filter(host="juice.example.com").exists()


@pytest.mark.django_db
class TestResetLabDbSeeds:
    def test_creates_target_if_missing(self):
        out = StringIO()
        call_command(
            "reset_lab_db", "--host", "new.example.com",
            "--confirm", "DELETE_LAB_DB", stdout=out,
        )

        target = ScanTarget.objects.get(host="new.example.com")
        assert str(target.pk) in out.getvalue()

    def test_prints_existing_target_uuid(self):
        target = _seed_full_session("juice.example.com")
        out = StringIO()
        call_command(
            "reset_lab_db", "--host", "juice.example.com",
            "--confirm", "DELETE_LAB_DB", stdout=out,
        )

        assert str(target.pk) in out.getvalue()


@pytest.mark.django_db
class TestResetLabDbIdempotent:
    def test_double_run_does_not_crash(self):
        call_command(
            "reset_lab_db", "--host", "empty.example.com",
            "--confirm", "DELETE_LAB_DB",
        )
        call_command(
            "reset_lab_db", "--host", "empty.example.com",
            "--confirm", "DELETE_LAB_DB",
        )
        assert ScanTarget.objects.filter(host="empty.example.com").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/test.sh backend apps/agent/tests/test_reset_lab_db.py -v`
Expected: FAIL — command not found

- [ ] **Step 3: Create package directories**

```bash
mkdir -p backend/apps/agent/management/commands
touch backend/apps/agent/management/__init__.py
touch backend/apps/agent/management/commands/__init__.py
```

- [ ] **Step 4: Implement reset_lab_db command**

Create `backend/apps/agent/management/commands/reset_lab_db.py`:

```python
"""Management command to reset lab DB for clean-slate testing."""
from __future__ import annotations

import sys

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Wipe agent/scan/event data and seed a target for clean-slate testing."

    def add_arguments(self, parser):
        parser.add_argument("--host", required=True, help="Target hostname to seed")
        parser.add_argument(
            "--confirm", default="",
            help="Must be DELETE_LAB_DB to proceed",
        )

    def handle(self, *args, **options):
        if options["confirm"] != "DELETE_LAB_DB":
            raise CommandError(
                "Safety: pass --confirm DELETE_LAB_DB to proceed"
            )

        host = options["host"]
        counts = self._wipe()
        for table, count in counts.items():
            self.stderr.write(f"  deleted {count} rows from {table}")

        target = self._ensure_target(host)
        self.stdout.write(str(target.pk))

    def _wipe(self) -> dict[str, int]:
        from apps.agent.models import (
            AgentNote, AgentObservation, AgentAction, AgentTurn, AgentSession,
        )
        from apps.events.models import Event
        from apps.scans.models import ScanTargetRun, ScanRun

        tables = [
            ("AgentNote", AgentNote),
            ("AgentObservation", AgentObservation),
            ("AgentAction", AgentAction),
            ("AgentTurn", AgentTurn),
            ("AgentSession", AgentSession),
            ("Event", Event),
            ("ScanTargetRun", ScanTargetRun),
            ("ScanRun", ScanRun),
        ]
        counts = {}
        for name, model in tables:
            count, _ = model.objects.all().delete()
            counts[name] = count
        return counts

    def _ensure_target(self, host: str):
        from apps.projects.models import Project
        from apps.targets.models import ScanTarget

        target = ScanTarget.objects.filter(host=host).first()
        if target is not None:
            return target

        project, _ = Project.objects.get_or_create(
            name="lab", defaults={"name": "lab"},
        )
        return ScanTarget.objects.create(
            host=host,
            base_url=f"https://{host}",
            project=project,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/test.sh backend apps/agent/tests/test_reset_lab_db.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/agent/management/ backend/apps/agent/tests/test_reset_lab_db.py
git commit -m "feat(agent): add reset_lab_db management command"
```

---

### Task 2: Wire CLEAN_SLATE into run-mission.sh

**Files:**
- Modify: `scripts/run-mission.sh`

- [ ] **Step 1: Add CLEAN_SLATE block after env var setup**

After the `DRY_RUN` variable (line 33), add:

```sh
CLEAN_SLATE="${CLEAN_SLATE:-0}"
CLEAN_SLATE_CONFIRM="${CLEAN_SLATE_CONFIRM:-}"
VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money/}"
```

After the TIMEOUT validation (line 40), add the clean-slate block:

```sh
# --- Clean slate (optional) ---
if [ "$CLEAN_SLATE" = "1" ]; then
  [ "$CLEAN_SLATE_CONFIRM" = "DELETE_LAB_DB" ] || \
    die "CLEAN_SLATE=1 requires CLEAN_SLATE_CONFIRM=DELETE_LAB_DB"

  log "CLEAN SLATE: wiping agent/scan/event data on ${VPS_HOST}"
  RESET_OUTPUT=$(ssh "${VPS_HOST}" "cd '${VPS_PATH}' && \
    docker compose exec -T backend python manage.py reset_lab_db \
      --host '${TARGET_ARG}' --confirm DELETE_LAB_DB" 2>&1) \
    || die "Clean slate failed: ${RESET_OUTPUT}"

  # Parse target UUID from command output (last non-empty line of stdout)
  TARGET_ID=$(echo "$RESET_OUTPUT" | grep -E '^[0-9a-f-]{36}$' | tail -1)
  [ -n "$TARGET_ID" ] && log "target seeded: $TARGET_ID"

  # Log deletion stats (stderr lines from the command)
  echo "$RESET_OUTPUT" | grep "deleted" | while read -r line; do
    log "$line"
  done
fi
```

Then modify the target resolution block to skip lookup when TARGET_ID is already set:

```sh
# --- Resolve target (UUID or host lookup) ---
if [ -n "${TARGET_ID:-}" ]; then
  log "target ID (from clean slate): $TARGET_ID"
elif ...
```

- [ ] **Step 2: Test manually with DRY_RUN**

```bash
CLEAN_SLATE=1 CLEAN_SLATE_CONFIRM=DELETE_LAB_DB DRY_RUN=1 \
  API_BASE=https://h1.cocode.dk ./scripts/run-mission.sh juiceshop.cocode.dk
```

- [ ] **Step 3: Commit**

```bash
git add scripts/run-mission.sh
git commit -m "feat(scripts): add CLEAN_SLATE option to run-mission.sh"
```
