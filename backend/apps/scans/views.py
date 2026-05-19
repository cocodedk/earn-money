"""ScanRunViewSet — list / retrieve / create + lifecycle actions.

Lifecycle endpoints delegate to model methods on `ScanRun`. The model
owns the state machine and atomicity; the viewset is a thin wrapper
that translates HTTP → method call → serialized response.

Filters on list:
  ?project=<uuid>     scope to one project
  ?status=<value>     filter by run status
  ?stub_slug=<value>  filter by cookbook stub
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.events.models import Event
from apps.events.serializers import EventSerializer
from apps.events.types import EventType
from apps.evidence.serializers import EvidenceSerializer
from apps.findings.serializers import FindingSerializer

from .models import ScanRun
from .serializers import ScanRunSerializer, ScanTargetRunSerializer
from .tasks import run_scan


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
        # Re-fetch via the annotated queryset so the 201 response carries
        # `target_run_count` — same shape as a list row.
        serializer.instance = self.get_queryset().get(pk=scan_run.pk)

    # --- Lifecycle actions ---
    # POST /api/scan-runs/<id>/<action>/  →  delegates to model method.
    # The model raises InvalidTransition (DRF APIException) on illegal
    # transitions, which auto-becomes 400 with {"detail": "..."}.

    @action(detail=True, methods=["post"])
    def start(self, _request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        run.start()
        # Enqueue the simulator only after the start transaction commits
        # — otherwise the worker could pick up a row that's still
        # mid-write. on_commit is a no-op in tests using TestCase unless
        # `captureOnCommitCallbacks(execute=True)` wraps the call.
        transaction.on_commit(lambda: run_scan.delay(str(run.id)))
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"])
    def pause(self, _request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        run.pause()
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"])
    def resume(self, _request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        run.resume()
        # Paused workers exit clean; resume re-enqueues the simulator.
        transaction.on_commit(lambda: run_scan.delay(str(run.id)))
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"])
    def stop(self, _request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        run.stop()
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["get"])
    def events(self, _request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        qs = run.events.all().order_by("created_at")
        page = self.paginate_queryset(qs)
        serializer = EventSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def findings(self, _request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        qs = run.findings.all().order_by("-created_at")
        page = self.paginate_queryset(qs)
        serializer = FindingSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def evidence(self, _request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        qs = run.evidence.all().order_by("-created_at")
        page = self.paginate_queryset(qs)
        serializer = EvidenceSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"], url_path="target-runs")
    def target_runs(self, _request: Request, pk: str | None = None) -> Response:
        """Per-target status table for the scan-run-detail page.

        Annotates findings_count + evidence_count via Count over the
        scan_run + target join (so other scan runs against the same
        target don't contaminate the per-row counts). Returns paginated
        rows with the target's base_url denormalized for the table."""
        run = self.get_object()
        qs = run.target_runs.select_related("target").annotate(
            findings_count=Count(
                "target__findings",
                filter=Q(target__findings__scan_run=run),
                distinct=True,
            ),
            evidence_count=Count(
                "target__evidence",
                filter=Q(target__evidence__scan_run=run),
                distinct=True,
            ),
        ).order_by("created_at")
        page = self.paginate_queryset(qs)
        serializer = ScanTargetRunSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
