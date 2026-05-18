"""ScanRunViewSet — list / retrieve / create.

No update or destroy in MVP (scan runs are immutable after create;
state transitions happen via lifecycle action endpoints landing in a
later commit).

Filters on list:
  ?project=<uuid>     scope to one project
  ?status=<value>     filter by run status
  ?stub_slug=<value>  filter by cookbook stub
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Count
from rest_framework import mixins, viewsets

from apps.events.models import Event
from apps.events.types import EventType

from .models import ScanRun
from .serializers import ScanRunSerializer


class ScanRunViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ScanRunSerializer

    def get_queryset(self):  # type: ignore[override]
        qs = ScanRun.objects.annotate(
            target_run_count=Count("target_runs", distinct=True),
        ).order_by("-created_at")
        params = self.request.query_params
        if params.get("project"):
            qs = qs.filter(project_id=params["project"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("stub_slug"):
            qs = qs.filter(stub_slug=params["stub_slug"])
        return qs

    def perform_create(self, serializer: ScanRunSerializer) -> None:  # type: ignore[override]
        with transaction.atomic():
            scan_run = serializer.save()
            Event.log(
                type=EventType.SCAN_RUN_CREATED,
                subject=scan_run,
                scan_run=scan_run,
                data={
                    "id": str(scan_run.id),
                    "project_id": str(scan_run.project_id),
                    "stub_slug": scan_run.stub_slug,
                    "target_ids": [
                        str(tr.target_id) for tr in scan_run.target_runs.all()
                    ],
                    "status": scan_run.status,
                },
            )
