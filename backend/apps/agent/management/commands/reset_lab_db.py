"""Management command to reset lab DB for clean-slate testing."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agent.models import (
    AgentAction,
    AgentNote,
    AgentObservation,
    AgentSession,
    AgentTurn,
)
from apps.events.models import Event
from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


class Command(BaseCommand):
    help = "Wipe agent/scan/event data and seed a target for clean-slate testing."

    def add_arguments(self, parser):
        parser.add_argument("--host", required=True, help="Target hostname to seed")
        parser.add_argument(
            "--confirm",
            default="",
            help="Must be DELETE_LAB_DB to proceed",
        )

    def handle(self, *args, **options):
        if options["confirm"] != "DELETE_LAB_DB":
            raise CommandError(
                "Safety: pass --confirm DELETE_LAB_DB to proceed"
            )

        host = options["host"]

        with transaction.atomic():
            self._wipe()
            target = self._ensure_target(host)

        self.stdout.write(str(target.pk))

    def _wipe(self) -> None:
        """Delete all transient data; preserve Project and ScanTarget rows."""
        AgentNote.objects.all().delete()
        AgentObservation.objects.all().delete()
        AgentAction.objects.all().delete()
        AgentTurn.objects.all().delete()
        AgentSession.objects.all().delete()
        Event.objects.all().delete()
        ScanTargetRun.objects.all().delete()
        ScanRun.objects.all().delete()

    def _ensure_target(self, host: str) -> ScanTarget:
        """Return existing target or create one under the 'lab' project."""
        targets = ScanTarget.objects.filter(host=host)
        if targets.count() > 1:
            raise CommandError(
                f"Multiple targets with host '{host}'. "
                f"Delete duplicates first or pass a specific UUID."
            )
        target = targets.first()
        if target is not None:
            return target
        project, _ = Project.objects.get_or_create(name="lab")
        return ScanTarget.objects.create(
            host=host,
            base_url=f"https://{host}",
            project=project,
        )
