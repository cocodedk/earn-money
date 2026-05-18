"""TargetViewSet — full CRUD with Event.log on every write.

Filter the list by `?project=<uuid>` to scope a Targets page to one
project. No other filters in MVP.
"""
from __future__ import annotations

from django.db import transaction
from rest_framework import viewsets

from apps.events.models import Event
from apps.events.types import EventType

from .models import ScanTarget
from .serializers import ScanTargetSerializer


class ScanTargetViewSet(viewsets.ModelViewSet):
    serializer_class = ScanTargetSerializer

    def get_queryset(self):  # type: ignore[override]
        qs = ScanTarget.objects.all().order_by("-created_at")
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def perform_create(self, serializer: ScanTargetSerializer) -> None:  # type: ignore[override]
        with transaction.atomic():
            instance = serializer.save()
            Event.log(
                type=EventType.TARGET_CREATED,
                subject=instance,
                target=instance,
                data={
                    "id": str(instance.id),
                    "project_id": str(instance.project_id),
                    "base_url": instance.base_url,
                    "host": instance.host,
                    "ip": str(instance.ip) if instance.ip else None,
                    "status": instance.status,
                },
            )

    def perform_update(self, serializer: ScanTargetSerializer) -> None:  # type: ignore[override]
        inst = serializer.instance
        before = {
            "base_url": inst.base_url,
            "host": inst.host,
            "ip": str(inst.ip) if inst.ip else None,
            "status": inst.status,
        }
        with transaction.atomic():
            updated = serializer.save()
            Event.log(
                type=EventType.TARGET_UPDATED,
                subject=updated,
                target=updated,
                data={
                    "id": str(updated.id),
                    "project_id": str(updated.project_id),
                    "before": before,
                    "after": {
                        "base_url": updated.base_url,
                        "host": updated.host,
                        "ip": str(updated.ip) if updated.ip else None,
                        "status": updated.status,
                    },
                },
            )

    def perform_destroy(self, instance: ScanTarget) -> None:  # type: ignore[override]
        snapshot = {
            "id": str(instance.id),
            "project_id": str(instance.project_id),
            "base_url": instance.base_url,
            "host": instance.host,
            "ip": str(instance.ip) if instance.ip else None,
            "status": instance.status,
        }
        with transaction.atomic():
            Event.log(
                type=EventType.TARGET_DELETED,
                subject_type="scantarget",
                subject_id=instance.id,
                data=snapshot,
            )
            instance.delete()
