"""FindingViewSet — read-only list/retrieve + operator-triage @action.

Filters on list:
  ?scan_run=<uuid>    scope to one run
  ?status=<value>     candidate | confirmed | rejected | stale
  ?stub_slug=<slug>   e.g. "1.1"

PATCH /api/findings/<id>/status/ flips the triage status. Body shape
`{"status": "<value>"}` — other fields silently dropped (narrow
serializer).
"""
from __future__ import annotations

from django.db import transaction
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.events.models import Event
from apps.events.types import EventType

from .models import Finding
from .serializers import FindingSerializer, FindingStatusSerializer


class FindingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FindingSerializer

    def get_queryset(self):  # type: ignore[override]
        qs = Finding.objects.all().order_by("-created_at")
        params = self.request.query_params
        if params.get("scan_run"):
            qs = qs.filter(scan_run_id=params["scan_run"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("stub_slug"):
            qs = qs.filter(stub_slug=params["stub_slug"])
        return qs

    @action(detail=True, methods=["patch"])
    def status(self, request: Request, pk: str | None = None) -> Response:
        finding = self.get_object()
        write = FindingStatusSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        new_status = write.validated_data["status"]
        before = finding.status
        with transaction.atomic():
            finding.status = new_status
            finding.save(update_fields=["status", "updated_at"])
            Event.log(
                type=EventType.FINDING_STATUS_CHANGED,
                subject=finding,
                scan_run=finding.scan_run,
                target=finding.target,
                data={
                    "id": str(finding.id),
                    "before": before,
                    "after": new_status,
                },
            )
        return Response(
            FindingSerializer(finding).data, status=http_status.HTTP_200_OK,
        )
