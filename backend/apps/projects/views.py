"""ProjectViewSet — full CRUD with Event.log on every write.

Every write wraps the state change AND the Event log in
`transaction.atomic()`. If the event log fails (or anything else
inside the block raises), the project mutation rolls back too. The
self-describing `data` payload on each Event is enough to reconstruct
the action without joining other tables — see
[[project-event-log-medium-done-well]].
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Count
from rest_framework import viewsets

from apps.events.models import Event
from apps.events.types import EventType

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    # Explicit order_by — annotated querysets sometimes drop model-level
    # `Meta.ordering`, which makes Django's paginator complain.
    queryset = Project.objects.annotate(
        target_count=Count("targets", distinct=True),
        scan_run_count=Count("scan_runs", distinct=True),
    ).order_by("-created_at")

    def perform_create(self, serializer: ProjectSerializer) -> None:  # type: ignore[override]
        with transaction.atomic():
            instance = serializer.save()
            Event.log(
                type=EventType.PROJECT_CREATED,
                subject=instance,
                data={
                    "id": str(instance.id),
                    "name": instance.name,
                    "description": instance.description,
                },
            )

    def perform_update(self, serializer: ProjectSerializer) -> None:  # type: ignore[override]
        before = {
            "name": serializer.instance.name,
            "description": serializer.instance.description,
        }
        with transaction.atomic():
            updated = serializer.save()
            Event.log(
                type=EventType.PROJECT_UPDATED,
                subject=updated,
                data={
                    "id": str(updated.id),
                    "before": before,
                    "after": {
                        "name": updated.name,
                        "description": updated.description,
                    },
                },
            )

    def perform_destroy(self, instance: Project) -> None:  # type: ignore[override]
        snapshot = {
            "id": str(instance.id),
            "name": instance.name,
            "description": instance.description,
        }
        with transaction.atomic():
            Event.log(
                type=EventType.PROJECT_DELETED,
                subject_type="project",
                subject_id=instance.id,
                data=snapshot,
            )
            instance.delete()
