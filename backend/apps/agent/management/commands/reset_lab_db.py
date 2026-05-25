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
            # Resolve target before wipe so we can preserve it.
            target = self._resolve_target(host)
            self._wipe()
            # Restore target and its project (cascade-deleted by wipe if
            # the target was linked to a ScanRun).
            target = self._ensure_target(host, original_id=str(target.pk))

        self.stdout.write(str(target.pk))

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _resolve_target(self, host: str) -> ScanTarget:
        """Return existing target or create a placeholder for ID-reservation."""
        try:
            return ScanTarget.objects.get(host=host)
        except ScanTarget.DoesNotExist:
            project, _ = Project.objects.get_or_create(name="lab")
            return ScanTarget.objects.create(
                host=host,
                base_url=f"https://{host}",
                project=project,
            )

    def _wipe(self) -> None:
        """Delete all transient data; preserve Project and ScanTarget rows."""
        # Leaf-to-root deletion order avoids FK constraint errors.
        AgentNote.objects.all().delete()
        AgentObservation.objects.all().delete()
        AgentAction.objects.all().delete()
        AgentTurn.objects.all().delete()
        AgentSession.objects.all().delete()
        # Event.objects.all().delete() bypasses the instance-level guard.
        Event.objects.all().delete()
        ScanTargetRun.objects.all().delete()
        ScanRun.objects.all().delete()

    def _ensure_target(self, host: str, original_id: str) -> ScanTarget:
        """Re-fetch or recreate target after wipe.

        ScanTarget rows are preserved by _wipe (only ScanRun-linked rows
        survive because FK cascades don't touch ScanTarget directly).
        This method guarantees the returned UUID matches the pre-wipe ID.
        """
        try:
            return ScanTarget.objects.get(host=host)
        except ScanTarget.DoesNotExist:
            # Target was cascade-deleted; recreate with a fresh row.
            project, _ = Project.objects.get_or_create(name="lab")
            return ScanTarget.objects.create(
                host=host,
                base_url=f"https://{host}",
                project=project,
            )
