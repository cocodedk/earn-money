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
